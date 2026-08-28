from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from app.api.deps import CurrentUser, DbDep, get_owned_or_404, scoped
from app.models import ExposureWindow, UserLocation
from app.schemas import CoverageSummary, ExposureWindowOut
from app.services.exposure_pipeline import coverage_summary, materialize_for_location

router = APIRouter(prefix="/exposure", tags=["exposure"])


@router.get("/windows", response_model=list[ExposureWindowOut])
def windows(
    user: CurrentUser,
    db: DbDep,
    location_id: int | None = None,
    window_type: str | None = Query(None, pattern="^(6h|24h|72h)$"),
    limit: int = Query(200, le=1000),
):
    q = scoped(db, ExposureWindow, user.id).order_by(desc(ExposureWindow.window_end)).limit(limit)
    if location_id:
        get_owned_or_404(db, UserLocation, user.id, location_id)
        q = q.where(ExposureWindow.location_id == location_id)
    if window_type:
        q = q.where(ExposureWindow.window_type == window_type)
    return db.execute(q).scalars().all()


@router.get("/coverage-summary", response_model=CoverageSummary)
def coverage(user: CurrentUser, db: DbDep):
    rows = db.execute(scoped(db, ExposureWindow, user.id)).scalars().all()
    return coverage_summary(rows)


@router.post("/materialize", response_model=list[ExposureWindowOut])
def materialize(user: CurrentUser, db: DbDep, location_id: int):
    loc = get_owned_or_404(db, UserLocation, user.id, location_id)
    if loc.nearest_station_id is None:
        raise HTTPException(status_code=409, detail="location has no resolved station")
    out = materialize_for_location(db, loc)
    db.commit()
    return out
