from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import desc

from app.api.deps import CurrentUser, DbDep, get_owned_or_404, scoped
from app.config import settings
from app.models import SymptomLog
from app.schemas import OcrResult, SymptomConfirmIn, SymptomIn, SymptomOut
from app.services.ocr import CONFIDENCE_THRESHOLD, extract_peak_flow

router = APIRouter(prefix="/symptoms", tags=["symptoms"])


def _to_out(row: SymptomLog) -> SymptomOut:
    needs = (
        row.peak_flow_value is not None
        and not row.manually_confirmed
        and (row.ocr_confidence or 0) < CONFIDENCE_THRESHOLD
    )
    return SymptomOut(
        id=row.id,
        severity=row.severity,
        notes=row.notes,
        peak_flow_value=row.peak_flow_value,
        peak_flow_photo_url=row.peak_flow_photo_url,
        ocr_confidence=row.ocr_confidence,
        manually_confirmed=row.manually_confirmed,
        logged_at=row.logged_at,
        needs_confirmation=needs,
    )


@router.get("", response_model=list[SymptomOut])
def list_symptoms(user: CurrentUser, db: DbDep, limit: int = 365):
    rows = (
        db.execute(
            scoped(db, SymptomLog, user.id).order_by(desc(SymptomLog.logged_at)).limit(limit)
        )
        .scalars()
        .all()
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=SymptomOut, status_code=201)
def create_symptom(body: SymptomIn, user: CurrentUser, db: DbDep):
    row = SymptomLog(
        user_id=user.id,
        severity=body.severity,
        notes=body.notes,
        peak_flow_value=body.peak_flow_value,
        manually_confirmed=body.peak_flow_value is not None,  # typed by hand → trusted
        logged_at=body.logged_at or datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/ocr-preview", response_model=OcrResult)
async def ocr_preview(_: CurrentUser, file: UploadFile = File(...)):
    """Extract a peak-flow number from a photo WITHOUT saving anything — the UI
    shows this in the confirm-or-correct step."""
    outcome = extract_peak_flow(await file.read())
    return OcrResult(
        raw_text=outcome.raw_text,
        extracted_value=outcome.extracted_value,
        confidence=outcome.confidence,
        needs_confirmation=outcome.needs_confirmation,
        engine=outcome.engine,
    )


@router.post("/with-photo", response_model=SymptomOut, status_code=201)
async def create_with_photo(
    user: CurrentUser,
    db: DbDep,
    severity: int = Form(..., ge=0, le=10),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
):
    image = await file.read()
    outcome = extract_peak_flow(image)

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    name = f"{user.id}_{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, name), "wb") as fh:
        fh.write(image)

    row = SymptomLog(
        user_id=user.id,
        severity=severity,
        notes=notes,
        # low-confidence OCR value is stored but NOT confirmed → excluded from
        # models/charts until the user acts on it
        peak_flow_value=outcome.extracted_value,
        peak_flow_photo_url=f"/uploads/{name}",
        ocr_confidence=outcome.confidence,
        manually_confirmed=not outcome.needs_confirmation,
        logged_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/{symptom_id}/confirm-peak-flow", response_model=SymptomOut)
def confirm_peak_flow(symptom_id: int, body: SymptomConfirmIn, user: CurrentUser, db: DbDep):
    row = get_owned_or_404(db, SymptomLog, user.id, symptom_id)
    row.peak_flow_value = body.peak_flow_value
    row.manually_confirmed = True
    row.ocr_confidence = 1.0
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{symptom_id}", status_code=204)
def delete_symptom(symptom_id: int, user: CurrentUser, db: DbDep):
    row = get_owned_or_404(db, SymptomLog, user.id, symptom_id)
    db.delete(row)
    db.commit()
