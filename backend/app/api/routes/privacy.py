"""Data export + deletion for the caller's own health data. A real privacy
feature, appropriate for health-adjacent data — not a nice-to-have."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, scoped
from app.api.routes.symptoms import _to_out as symptom_to_out
from app.core.security import revoke_all_for_user
from app.models import (
    AdvisoryLog,
    AuditLog,
    ExposureWindow,
    RiskModel,
    RiskPrediction,
    SymptomLog,
    UserLocation,
)
from app.schemas import (
    AdvisoryOut,
    DataExport,
    ExposureWindowOut,
    LocationOut,
    RiskPredictionOut,
    UserOut,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/export", response_model=DataExport)
def export_data(user: CurrentUser, db: DbDep):
    locs = db.execute(scoped(db, UserLocation, user.id)).scalars().all()
    symptoms = db.execute(scoped(db, SymptomLog, user.id)).scalars().all()
    windows = db.execute(scoped(db, ExposureWindow, user.id)).scalars().all()
    preds = db.execute(scoped(db, RiskPrediction, user.id)).scalars().all()
    advisories = db.execute(scoped(db, AdvisoryLog, user.id)).scalars().all()

    db.add(
        AuditLog(
            actor_id=user.id, action="data_export", target_table="users", target_id=str(user.id)
        )
    )
    db.commit()

    return DataExport(
        exported_at=datetime.now(UTC),
        user=UserOut.model_validate(user),
        locations=[LocationOut.model_validate(x) for x in locs],
        symptom_logs=[symptom_to_out(x) for x in symptoms],
        exposure_windows=[ExposureWindowOut.model_validate(x) for x in windows],
        risk_predictions=[
            RiskPredictionOut(
                risk_score=p.risk_score,
                model_type="",
                algorithm="",
                model_version=0,
                is_personalized=False,
                disclaimer="",
                lag_features=p.lag_features_json,
                explanation=p.explanation_json.get("top", []),
                data_coverage_pct=None,
                predicted_at=p.predicted_at,
            )
            for p in preds
        ],
        advisory_log=[
            AdvisoryOut(
                response_text=a.response_text,
                citations=a.citations_json,
                refused=a.refused,
                context_used={},
                created_at=a.created_at,
            )
            for a in advisories
        ],
    )


@router.delete("/delete", status_code=200)
def delete_data(user: CurrentUser, db: DbDep):
    """Hard-delete the caller's health data and revoke all sessions. The `users`
    row itself is kept only as a tombstone-free full delete here."""
    counts = {}
    for model in (RiskPrediction, ExposureWindow, SymptomLog, AdvisoryLog, UserLocation):
        rows = db.execute(scoped(db, model, user.id)).scalars().all()
        counts[model.__tablename__] = len(rows)
        for r in rows:
            db.delete(r)
    # personal models (population fallback, user_id IS NULL, is untouched)
    personal_models = (
        db.execute(select(RiskModel).where(RiskModel.user_id == user.id)).scalars().all()
    )
    counts["risk_models"] = len(personal_models)
    for m in personal_models:
        db.delete(m)

    revoke_all_for_user(db, user.id)
    db.add(
        AuditLog(
            actor_id=user.id, action="data_delete", target_table="users", target_id=str(user.id)
        )
    )
    db.delete(user)
    db.commit()
    return {"deleted": counts, "sessions_revoked": True}
