"""Seed a fresh clone into a demoable state in one command:

    python -m app.seed.seed

Creates:
  * WHO + CPCB guideline documents, chunked & embedded into pgvector
  * 4 stations around a city, with deliberately gappy synthetic AQI history (~35d)
  * synthetic daily weather
  * demo@example.com  — 40+ symptom logs over 25 days, correlated with PM2.5 at
    t-24h → clears the personal-model threshold
  * new@example.com   — 4 symptom logs over 3 days → population fallback only
  * materialized exposure windows + trained models + docs/METRICS.md
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    AqiReading,
    Station,
    SymptomLog,
    User,
    UserLocation,
)
from app.services.geo import resolve_nearest_station
from app.services.ingestion import POLLUTANTS, ingest_weather_synthetic

RNG = random.Random(20260828)
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
HISTORY_DAYS = 35

STATIONS = [
    ("Central Boulevard", 28.6139, 77.2090, 60),
    ("Riverside Park", 28.6500, 77.2300, 60),
    ("Airport Road", 28.5560, 77.1000, 120),  # coarser cadence on purpose
    ("Hill Colony", 28.7000, 77.1700, 60),
]


def _diurnal_pm(ts: datetime, base_shift: float) -> float:
    hod = ts.hour + ts.minute / 60
    day = (NOW - ts).days
    # slow multi-day episode swings so the model sees high AND low regimes
    episode = 1.0 + 0.5 * math.sin(day / 4.0) + 0.25 * math.sin(day / 1.7)
    diurnal = 35 + 28 * math.exp(-((hod - 9) ** 2) / 6) + 32 * math.exp(-((hod - 20) ** 2) / 8)
    return max(3.0, (diurnal + base_shift) * episode)


def seed_stations(db) -> list[Station]:
    out = []
    for i, (name, lat, lng, cadence) in enumerate(STATIONS):
        st = db.execute(select(Station).where(Station.location_name == name)).scalar_one_or_none()
        if not st:
            st = Station(
                source="synthetic",
                external_id=f"syn-{i}",
                location_name=name,
                lat=lat,
                lng=lng,
                nominal_cadence_minutes=cadence,
                last_seen_at=NOW,
            )
            db.add(st)
        out.append(st)
    db.flush()
    return out


def seed_readings(db, stations: list[Station]) -> int:
    start = NOW - timedelta(days=HISTORY_DAYS)
    total = 0
    for si, st in enumerate(stations):
        step = timedelta(minutes=st.nominal_cadence_minutes)
        # each station has its own gappy personality
        gap_prob = [0.10, 0.18, 0.30, 0.14][si]
        # simulate one multi-day outage on station 2
        outage = (NOW - timedelta(days=12), NOW - timedelta(days=10)) if si == 2 else None
        t = start
        while t < NOW:
            in_outage = outage and outage[0] <= t < outage[1]
            if not in_outage and RNG.random() > gap_prob:
                pm25 = _diurnal_pm(t, base_shift=[0, 6, -4, -8][si])
                for pol in POLLUTANTS:
                    factor = {"pm25": 1.0, "pm10": 1.7, "no2": 0.55, "o3": 0.0}[pol]
                    if pol == "o3":
                        val = max(4.0, 70 - pm25 * 0.35 + RNG.gauss(0, 5))
                    else:
                        val = max(0.0, pm25 * factor * RNG.uniform(0.8, 1.25) + RNG.gauss(0, 3))
                    db.add(
                        AqiReading(
                            station_id=st.id,
                            pollutant=pol,
                            value=round(val, 2),
                            unit="ug/m3",
                            recorded_at=t,
                        )
                    )
                    total += 1
            t += step
    db.flush()
    return total


def _pm25_lag_avg(
    db, station_id: int, center: datetime, lag_hours: int, span_hours: int = 6
) -> float:
    hi = center - timedelta(hours=lag_hours)
    lo = hi - timedelta(hours=span_hours)
    rows = (
        db.execute(
            select(AqiReading.value).where(
                AqiReading.station_id == station_id,
                AqiReading.pollutant == "pm25",
                AqiReading.recorded_at >= lo,
                AqiReading.recorded_at < hi,
            )
        )
        .scalars()
        .all()
    )
    return sum(rows) / len(rows) if rows else 0.0


def seed_user(
    db, email: str, *, n_logs: int, span_days: int, station: Station, lat: float, lng: float
) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        user = User(email=email, hashed_password=hash_password("demo-pass-123"))
        db.add(user)
        db.flush()

    loc = db.execute(
        select(UserLocation).where(UserLocation.user_id == user.id)
    ).scalar_one_or_none()
    if not loc:
        loc = UserLocation(user_id=user.id, label="home", lat=lat, lng=lng)
        db.add(loc)
        db.flush()
    sid, dist = resolve_nearest_station(db, loc)
    loc.nearest_station_id, loc.distance_km = sid, dist
    loc.resolved_at = datetime.now(UTC)
    db.flush()

    # symptom severity is generated as a noisy function of PM2.5 24h earlier
    # (plus a little from t-6h) — this is the lag signal the model should recover.
    start = NOW - timedelta(days=span_days)
    for _ in range(n_logs):
        offset_h = RNG.uniform(0, span_days * 24)
        t = start + timedelta(hours=offset_h)
        if t >= NOW:
            continue
        pm_lag24 = _pm25_lag_avg(db, loc.nearest_station_id, t, 24)
        pm_lag6 = _pm25_lag_avg(db, loc.nearest_station_id, t, 6)
        sev = 0.6 + 0.05 * pm_lag24 + 0.02 * pm_lag6 + RNG.gauss(0, 1.1)
        sev_i = int(max(0, min(10, round(sev))))
        pf = None
        conf = None
        confirmed = False
        if RNG.random() < 0.4:  # ~40% of logs include a (typed) peak-flow value
            pf = round(max(150, 430 - 6 * sev_i + RNG.gauss(0, 15)), 0)
            conf = 1.0
            confirmed = True
        db.add(
            SymptomLog(
                user_id=user.id,
                severity=sev_i,
                notes=RNG.choice(
                    [
                        "",
                        "tight chest",
                        "worse on the walk to work",
                        "used inhaler",
                        "fine after rain",
                        "eyes itchy",
                    ]
                ),
                peak_flow_value=pf,
                ocr_confidence=conf,
                manually_confirmed=confirmed,
                logged_at=t,
            )
        )
    db.flush()
    return user


def main() -> None:
    from app.ml.train import retrain_everything, write_metrics_doc
    from app.rag.embed import index_guidelines
    from app.services.exposure_pipeline import materialize_all

    db = SessionLocal()
    try:
        print("· indexing guideline documents (WHO + CPCB) into pgvector …")
        print("  ", index_guidelines(db, reset=True))

        print("· seeding stations + gappy AQI history …")
        stations = seed_stations(db)
        n_readings = seed_readings(db, stations)
        db.commit()
        print(f"   {n_readings} raw readings across {len(stations)} stations")

        print("· seeding weather …")
        ingest_weather_synthetic(db, days=HISTORY_DAYS)

        print("· seeding users …")
        seed_user(
            db,
            "demo@example.com",
            n_logs=48,
            span_days=25,
            station=stations[0],
            lat=28.6150,
            lng=77.2100,
        )
        seed_user(
            db,
            "new@example.com",
            n_logs=4,
            span_days=3,
            station=stations[1],
            lat=28.6490,
            lng=77.2280,
        )
        db.commit()

        print("· materializing exposure windows …")
        print("  ", materialize_all(db), "windows")

        print("· training models (population fallback + per-user) …")
        print("  ", retrain_everything(db))

        try:
            write_metrics_doc(db)
        except OSError:
            pass

        print("\n✓ seed complete")
        print("  demo@example.com / demo-pass-123   (personal model)")
        print("  new@example.com  / demo-pass-123   (population fallback)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
