"""AQI + weather ingestion.

Design rules from the brief:
* raw readings stored with `recorded_at` exactly as reported — no cleanup on ingest
* dedup / upsert on the natural key (station_id, pollutant, recorded_at)
* a station that stops reporting is logged as `station_silent`, never a silent hole
* no Celery / Redis — this is called from the in-process asyncio scheduler
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AqiReading, IngestionEvent, Station, WeatherDaily

POLLUTANTS = ["pm25", "pm10", "no2", "o3"]
_SILENT_AFTER = timedelta(hours=3)


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# upsert helpers (dialect-aware so tests on SQLite still work)
# --------------------------------------------------------------------------- #
def _upsert_reading(
    db: Session,
    station_id: int,
    pollutant: str,
    value: float,
    recorded_at: datetime,
    unit: str = "ug/m3",
) -> bool:
    if db.bind.dialect.name == "postgresql":
        stmt = (
            pg_insert(AqiReading)
            .values(
                station_id=station_id,
                pollutant=pollutant,
                value=value,
                unit=unit,
                recorded_at=recorded_at,
            )
            .on_conflict_do_update(
                constraint="uq_reading_natural_key",
                set_={"value": value, "unit": unit, "ingested_at": _now()},
            )
        )
        db.execute(stmt)
        return True
    # SQLite / generic path
    existing = db.execute(
        select(AqiReading).where(
            AqiReading.station_id == station_id,
            AqiReading.pollutant == pollutant,
            AqiReading.recorded_at == recorded_at,
        )
    ).scalar_one_or_none()
    if existing:
        existing.value = value
        existing.unit = unit
        existing.ingested_at = _now()
        return False
    db.add(
        AqiReading(
            station_id=station_id,
            pollutant=pollutant,
            value=value,
            unit=unit,
            recorded_at=recorded_at,
        )
    )
    return True


# --------------------------------------------------------------------------- #
# synthetic feed — deliberate gaps so the exposure pipeline has to be honest
# --------------------------------------------------------------------------- #
def synthetic_readings_for_station(
    station: Station,
    since: datetime,
    until: datetime,
    *,
    gap_prob: float = 0.18,
    seed: int | None = None,
) -> list[tuple[str, float, datetime]]:
    """Diurnal PM curve + noise, with ~`gap_prob` of slots dropped entirely to
    mimic an intermittently-reporting sensor."""
    rng = random.Random(seed if seed is not None else hash((station.id, since)))
    step = timedelta(minutes=station.nominal_cadence_minutes)
    out: list[tuple[str, float, datetime]] = []
    t = since
    while t < until:
        if rng.random() > gap_prob:
            hod = t.hour + t.minute / 60
            # two rush-hour humps
            diurnal = (
                40 + 30 * math.exp(-((hod - 9) ** 2) / 6) + 35 * math.exp(-((hod - 20) ** 2) / 8)
            )
            for pol in POLLUTANTS:
                base = {
                    "pm25": diurnal,
                    "pm10": diurnal * 1.7,
                    "no2": diurnal * 0.6,
                    "o3": max(5, 60 - diurnal * 0.4),
                }[pol]
                val = max(0.0, base * rng.uniform(0.75, 1.3) + rng.gauss(0, 4))
                out.append((pol, round(val, 2), t))
        t += step
    return out


def ingest_synthetic(db: Session, lookback_hours: int = 6, seed: int | None = None) -> int:
    total = 0
    until = _now()
    since = until - timedelta(hours=lookback_hours)
    for station in db.execute(select(Station)).scalars().all():
        rows = synthetic_readings_for_station(station, since, until, seed=seed)
        inserted = 0
        for pol, val, ts in rows:
            if _upsert_reading(db, station.id, pol, val, ts):
                inserted += 1
        station.last_seen_at = until if rows else station.last_seen_at
        db.add(
            IngestionEvent(
                station_id=station.id,
                source="synthetic",
                status="ok" if rows else "gap",
                detail=f"{len(rows)} raw points over {lookback_hours}h window",
                rows_ingested=inserted,
            )
        )
        total += inserted
    _flag_silent_stations(db)
    db.commit()
    return total


# --------------------------------------------------------------------------- #
# OpenAQ v3 (best-effort; falls back to synthetic on any failure)
# --------------------------------------------------------------------------- #
async def ingest_openaq(db: Session, lookback_hours: int = 6) -> int:
    if not settings.openaq_base_url:
        return 0
    total = 0
    since = (_now() - timedelta(hours=lookback_hours)).isoformat()
    async with httpx.AsyncClient(timeout=20) as client:
        for station in (
            db.execute(select(Station).where(Station.source == "openaq")).scalars().all()
        ):
            try:
                resp = await client.get(
                    f"{settings.openaq_base_url}/locations/{station.external_id}/measurements",
                    params={"date_from": since, "limit": 1000},
                )
                resp.raise_for_status()
                payload = resp.json().get("results", [])
            except (httpx.HTTPError, ValueError) as exc:
                db.add(
                    IngestionEvent(
                        station_id=station.id,
                        source="openaq",
                        status="failure",
                        detail=str(exc)[:500],
                    )
                )
                continue
            inserted = 0
            for m in payload:
                pol = str(m.get("parameter", "")).replace(".", "").lower()
                if pol not in POLLUTANTS:
                    continue
                ts = datetime.fromisoformat(
                    m["period"]["datetimeFrom"]["utc"].replace("Z", "+00:00")
                )
                if _upsert_reading(
                    db, station.id, pol, float(m["value"]), ts, m.get("unit", "ug/m3")
                ):
                    inserted += 1
            station.last_seen_at = _now() if payload else station.last_seen_at
            db.add(
                IngestionEvent(
                    station_id=station.id,
                    source="openaq",
                    status="ok" if payload else "gap",
                    detail=f"{len(payload)} measurements",
                    rows_ingested=inserted,
                )
            )
            total += inserted
    _flag_silent_stations(db)
    db.commit()
    return total


def _flag_silent_stations(db: Session) -> None:
    cutoff = _now() - _SILENT_AFTER
    for station in db.execute(select(Station)).scalars().all():
        last = station.last_seen_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last is not None and last < cutoff:
            db.add(
                IngestionEvent(
                    station_id=station.id,
                    source=station.source,
                    status="station_silent",
                    detail=f"no readings since {last.isoformat()} (> {_SILENT_AFTER})",
                )
            )


# --------------------------------------------------------------------------- #
# weather
# --------------------------------------------------------------------------- #
def ingest_weather_synthetic(db: Session, days: int = 5) -> int:
    rng = random.Random(20260828)
    total = 0
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    locations = {s.location_name for s in db.execute(select(Station)).scalars().all()} or {
        "Default City"
    }
    for loc in locations:
        for d in range(days):
            date = today - timedelta(days=d)
            existing = db.execute(
                select(WeatherDaily).where(WeatherDaily.location == loc, WeatherDaily.date == date)
            ).scalar_one_or_none()
            temp = 24 + 8 * math.sin(d / 3) + rng.gauss(0, 1.5)
            humidity = 55 + 20 * math.sin(d / 2 + 1) + rng.gauss(0, 5)
            rain = max(0.0, rng.gauss(2, 6))
            if existing:
                existing.temp_c, existing.humidity_pct, existing.rainfall_mm = temp, humidity, rain
            else:
                db.add(
                    WeatherDaily(
                        location=loc,
                        date=date,
                        temp_c=round(temp, 1),
                        humidity_pct=round(humidity, 1),
                        rainfall_mm=round(rain, 1),
                    )
                )
                total += 1
    db.commit()
    return total
