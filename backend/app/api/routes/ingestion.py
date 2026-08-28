"""Admin / demo endpoints for the ingestion pipeline — useful for showing the
feed is genuinely live and that station gaps are recorded, not hidden."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbDep
from app.models import AqiReading, IngestionEvent, Station
from app.schemas import AqiReadingOut, StationOut

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/stations", response_model=list[StationOut])
def stations(db: DbDep, _: CurrentUser):
    return db.execute(select(Station).order_by(Station.id)).scalars().all()


@router.get("/readings", response_model=list[AqiReadingOut])
def readings(
    db: DbDep,
    _: CurrentUser,
    station_id: int | None = None,
    pollutant: str | None = None,
    limit: int = Query(200, le=2000),
):
    q = select(AqiReading).order_by(desc(AqiReading.recorded_at)).limit(limit)
    if station_id:
        q = q.where(AqiReading.station_id == station_id)
    if pollutant:
        q = q.where(AqiReading.pollutant == pollutant)
    return db.execute(q).scalars().all()


@router.get("/events")
def events(db: DbDep, _: CurrentUser, limit: int = Query(100, le=1000)):
    rows = (
        db.execute(select(IngestionEvent).order_by(desc(IngestionEvent.created_at)).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": e.id,
            "station_id": e.station_id,
            "source": e.source,
            "status": e.status,
            "detail": e.detail,
            "rows_ingested": e.rows_ingested,
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.post("/run")
async def run_now(db: DbDep, _: CurrentUser):
    """Trigger one ingestion + materialization + retrain tick on demand, then
    evaluate + push live alerts to any connected sockets."""
    from starlette.concurrency import run_in_threadpool

    from app.api.ws_manager import evaluate_and_push_alerts
    from app.services.scheduler import _tick_sync

    result = await run_in_threadpool(_tick_sync)
    alerts = await evaluate_and_push_alerts()
    return {"ran": True, **result, "alerts": alerts}
