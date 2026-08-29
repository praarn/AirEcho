"""Seed a fresh clone into a demoable state in one command:

    python -m app.seed.seed

Creates:
  * CPCB (NAQI / NAAQS / GRAP) + WHO guideline documents, chunked & embedded
  * 6 real Delhi-NCR monitoring stations, with deliberately gappy synthetic AQI
    history (~35d) following Delhi's seasonal PM2.5 climatology
  * synthetic daily weather
  * demo@example.com  — 3 saved locations across Delhi + 48 symptom logs over
    25 days, correlated with PM2.5 at t-24h → clears the personal-model threshold
  * new@example.com   — 1 location in Dwarka + 4 symptom logs over 3 days →
    population fallback only
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

# Real CPCB continuous ambient air-quality monitoring stations in the Delhi-NCR
# airshed. (name, lat, lng, nominal cadence minutes). Anand Vihar and Punjabi
# Bagh routinely top the national AQI table; the airport reports on a coarser
# cadence on purpose so the coverage accounting has something to chew on.
STATIONS = [
    ("Anand Vihar, Delhi (CPCB)", 28.6469, 77.3154, 60),
    ("R K Puram, Delhi (DPCC)", 28.5636, 77.1866, 60),
    ("Punjabi Bagh, Delhi (DPCC)", 28.6740, 77.1310, 60),
    ("ITO, Delhi (CPCB)", 28.6285, 77.2410, 60),
    ("Dwarka Sector 8, Delhi (DPCC)", 28.5710, 77.0719, 60),
    ("IGI Airport T3, Delhi (IMD)", 28.5562, 77.0999, 120),
]

# Delhi PM2.5 climatology — approximate monthly means (µg/m³). Winter (Nov–Jan)
# is trapped-inversion + stubble-smoke + firecracker season; the monsoon
# (Jul–Sep) washes the air out. The seeded ~35-day window inherits whatever
# months it spans, so a November clone looks Severe and an August one Moderate.
DELHI_PM25_CLIMATOLOGY = {
    1: 200, 2: 130, 3: 95, 4: 88, 5: 82, 6: 70,
    7: 48, 8: 42, 9: 58, 10: 120, 11: 235, 12: 205,
}  # fmt: skip


def _diwali_boost(ts: datetime) -> float:
    """Firecracker week: a multiplicative bump if `ts` lands within ~5 days of an
    approximate Diwali date for its year (late Oct / early Nov)."""
    approx = {2024: (11, 1), 2025: (10, 21), 2026: (11, 8), 2027: (10, 29)}
    md = approx.get(ts.year)
    if not md:
        return 1.0
    diwali = ts.replace(month=md[0], day=md[1], hour=0, minute=0, second=0, microsecond=0)
    days = abs((ts - diwali).total_seconds()) / 86400
    return 1.0 + 0.9 * math.exp(-(days**2) / 8) if days < 6 else 1.0


def _diurnal_pm(ts: datetime, base_shift: float) -> float:
    hod = ts.hour + ts.minute / 60
    day = (NOW - ts).days
    clim = DELHI_PM25_CLIMATOLOGY[ts.month]
    # slow multi-day episode swings so the model sees calm AND smog regimes
    episode = 1.0 + 0.42 * math.sin(day / 4.0) + 0.22 * math.sin(day / 1.7)
    # two rush-hour humps + an early-morning inversion peak, as a fraction of the
    # monthly mean rather than a fixed additive curve
    shape = 0.72 + 0.30 * math.exp(-((hod - 8) ** 2) / 7) + 0.40 * math.exp(-((hod - 21) ** 2) / 9)
    val = (clim * shape * episode + base_shift) * _diwali_boost(ts)
    return max(6.0, val + RNG.gauss(0, clim * 0.04))


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
    # per-station personality, indexed to STATIONS order above
    gap_prob = [0.09, 0.16, 0.12, 0.10, 0.18, 0.34]
    base_shift = [24, 2, 28, 12, -8, -16]
    # multi-day outages: the airport rig drops for ~2 days, one DPCC station has a
    # calibration gap. Everything else just has its slot-level dropout rate.
    outages = {
        5: (NOW - timedelta(days=13), NOW - timedelta(days=11)),
        1: (NOW - timedelta(days=6, hours=8), NOW - timedelta(days=5, hours=14)),
    }
    for si, st in enumerate(stations):
        step = timedelta(minutes=st.nominal_cadence_minutes)
        outage = outages.get(si)
        burst_left = 0  # remaining slots of a short "sensor offline" burst
        # a stubble-smoke plume parked over the NW of the city for a stretch
        plume = (NOW - timedelta(days=9), NOW - timedelta(days=7)) if si in (0, 2) else None
        t = start
        while t < NOW:
            in_outage = outage and outage[0] <= t < outage[1]
            if burst_left <= 0 and RNG.random() < 0.012:
                burst_left = RNG.randint(3, 9)  # sensor offline for a few hours
            if not in_outage and burst_left <= 0 and RNG.random() > gap_prob[si]:
                pm25 = _diurnal_pm(t, base_shift[si])
                if plume and plume[0] <= t < plume[1]:
                    pm25 *= RNG.uniform(1.4, 1.9)
                for pol in POLLUTANTS:
                    if pol == "o3":
                        # ozone runs inverse to PM and peaks in the afternoon
                        hod = t.hour + t.minute / 60
                        afternoon = 26 * math.exp(-((hod - 15) ** 2) / 10)
                        val = max(4.0, 58 - pm25 * 0.22 + afternoon + RNG.gauss(0, 6))
                    else:
                        factor = {"pm25": 1.0, "pm10": 1.9, "no2": 0.5}[pol]
                        # NO2 tracks traffic more than PM: extra rush-hour weight
                        if pol == "no2":
                            hod = t.hour + t.minute / 60
                            factor *= 1.0 + 0.5 * math.exp(-((hod - 9) ** 2) / 5)
                        val = max(0.0, pm25 * factor * RNG.uniform(0.82, 1.22) + RNG.gauss(0, 4))
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
            burst_left = max(0, burst_left - 1)
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
    db,
    email: str,
    *,
    n_logs: int,
    span_days: int,
    locations: list[tuple[str, float, float]],
) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        user = User(email=email, hashed_password=hash_password("demo-pass-123"))
        db.add(user)
        db.flush()

    anchor: UserLocation | None = None
    for label, lat, lng in locations:
        loc = db.execute(
            select(UserLocation).where(UserLocation.user_id == user.id, UserLocation.label == label)
        ).scalar_one_or_none()
        if not loc:
            loc = UserLocation(user_id=user.id, label=label, lat=lat, lng=lng)
            db.add(loc)
            db.flush()
        sid, dist = resolve_nearest_station(db, loc)
        loc.nearest_station_id, loc.distance_km = sid, dist
        loc.resolved_at = datetime.now(UTC)
        db.flush()
        anchor = anchor or loc

    # symptom history is generated against the first (primary) location's station
    loc = anchor

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
        # gentler than a raw linear map so severity stays informative in winter
        # (PM2.5 in the 200s) instead of pinning at 10 all season
        sev = 0.7 + 0.028 * pm_lag24 + 0.012 * pm_lag6 + RNG.gauss(0, 1.2)
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
                        "",
                        "tight chest on the morning walk",
                        "AQI showed 'Very Poor' — took the metro instead",
                        "used the inhaler twice",
                        "eyes and throat itchy, smoky smell outside",
                        "better after the rain cleared the haze",
                        "ran the air purifier all night",
                        "wore an N95 to office",
                        "worse near the flyover traffic",
                        "post-Diwali, everything hazy",
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
        print("· indexing guideline documents (CPCB NAQI/NAAQS/GRAP + WHO) into pgvector …")
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
            locations=[
                ("Home — Mayur Vihar", 28.6089, 77.2930),
                ("Office — ITO", 28.6280, 77.2405),
                ("Parents — Punjabi Bagh", 28.6705, 77.1345),
            ],
        )
        seed_user(
            db,
            "new@example.com",
            n_logs=4,
            span_days=3,
            locations=[("Home — Dwarka", 28.5715, 77.0715)],
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
