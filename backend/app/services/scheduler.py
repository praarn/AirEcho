"""In-process ingestion scheduler — a plain asyncio loop, no Celery / Redis.

Started from the FastAPI lifespan when SCHEDULER_ENABLED is true. Each tick:
  ingest AQI (+weather)  ->  materialize exposure_windows  ->  retrain models
All DB work is sync and runs in the default threadpool so it never blocks the
event loop / WebSocket broadcasts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import SessionLocal

log = logging.getLogger("aq.scheduler")

_task: asyncio.Task | None = None
_last_run: dict = {"at": None, "aqi_rows": 0, "windows": 0, "error": None}


def last_run() -> dict:
    return _last_run


def _tick_sync() -> dict:
    from app.ml.train import retrain_everything
    from app.services.exposure_pipeline import materialize_all
    from app.services.ingestion import ingest_synthetic, ingest_weather_synthetic

    db = SessionLocal()
    try:
        if settings.synthetic_ingest:
            rows = ingest_synthetic(db, lookback_hours=settings.ingest_interval_minutes / 60 + 6)
            ingest_weather_synthetic(db)
        else:
            rows = 0  # OpenAQ path is async; handled in _tick()
        windows = materialize_all(db)
        retrain_everything(db)
        return {"aqi_rows": rows, "windows": windows}
    finally:
        db.close()


async def _tick() -> None:
    global _last_run
    try:
        if settings.synthetic_ingest:
            result = await run_in_threadpool(_tick_sync)
        else:
            from app.services.ingestion import ingest_openaq

            db = SessionLocal()
            try:
                rows = await ingest_openaq(db)
            finally:
                db.close()
            result = await run_in_threadpool(_tick_sync)
            result["aqi_rows"] = rows
        from app.api.ws_manager import evaluate_and_push_alerts, manager

        alerts = await evaluate_and_push_alerts()
        await manager.broadcast_admin(
            {
                "type": "tick",
                "aqi_rows": result.get("aqi_rows", 0),
                "windows": result.get("windows", 0),
                "alerts": alerts,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        _last_run = {
            "at": datetime.now(UTC).isoformat(),
            **result,
            "alerts": alerts,
            "error": None,
        }
        log.info("scheduler tick ok: %s", _last_run)
    except Exception as exc:  # keep the loop alive
        _last_run = {"at": datetime.now(UTC).isoformat(), "error": repr(exc)}
        log.exception("scheduler tick failed")


async def _loop() -> None:
    interval = max(60, settings.ingest_interval_minutes * 60)
    # small delay so the app finishes booting / migrations settle
    await asyncio.sleep(5)
    while True:
        await _tick()
        await asyncio.sleep(interval)


def start(app) -> None:
    global _task
    if not settings.scheduler_enabled:
        log.info("scheduler disabled (SCHEDULER_ENABLED=false)")
        return
    _task = asyncio.create_task(_loop())


async def stop() -> None:
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
