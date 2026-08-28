from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import desc

from app.api.deps import CurrentUser, DbDep, get_owned_or_404, scoped
from app.ml.predict import predict_for_user
from app.models import AdvisoryLog, ExposureWindow, UserLocation
from app.rag.advisory import generate_advisory
from app.schemas import AdvisoryIn, AdvisoryOut

router = APIRouter(prefix="/advisory", tags=["advisory"])


def _context_for(db, user_id: int, location_id: int | None) -> dict:
    q = scoped(db, ExposureWindow, user_id).where(ExposureWindow.window_type == "24h")
    if location_id:
        q = q.where(ExposureWindow.location_id == location_id)
    win = db.execute(q.order_by(desc(ExposureWindow.window_end))).scalars().first()
    risk = predict_for_user(db, user_id, persist=False)
    return {
        "pm25": win.avg_pm25 if win else None,
        "data_coverage_pct": win.data_coverage_pct if win else None,
        "risk_score": risk["risk_score"],
        "is_personalized": risk["is_personalized"],
    }


@router.post("/ask", response_model=AdvisoryOut)
def ask(body: AdvisoryIn, user: CurrentUser, db: DbDep):
    if body.location_id:
        get_owned_or_404(db, UserLocation, user.id, body.location_id)
    context = _context_for(db, user.id, body.location_id)
    return generate_advisory(db, user_id=user.id, question=body.question, context=context)


@router.get("/history", response_model=list[AdvisoryOut])
def history(user: CurrentUser, db: DbDep, limit: int = 50):
    rows = (
        db.execute(
            scoped(db, AdvisoryLog, user.id).order_by(desc(AdvisoryLog.created_at)).limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        AdvisoryOut(
            response_text=r.response_text,
            citations=r.citations_json,
            refused=r.refused,
            context_used={},
            created_at=r.created_at,
        )
        for r in rows
    ]
