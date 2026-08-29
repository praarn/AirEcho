"""Seed a fresh clone into a demoable state in one command:

    python -m app.seed.seed

Creates:
  * CPCB (NAQI / NAAQS / GRAP) + WHO guideline documents, chunked & embedded
  * ~16 real monitoring stations spread across India — metros, tier-2 cities and
    genuinely remote sites (Leh, Gangtok, Itanagar, Port Blair, Kavaratti) —
    with deliberately gappy synthetic AQI history (~35d) following each region's
    seasonal PM2.5 climatology
  * synthetic daily weather
  * demo@example.com  — 3 saved locations from Kanpur to Bengaluru to Gangtok
    + 48 symptom logs over 25 days, correlated with PM2.5 at t-24h → clears the
    personal-model threshold
  * new@example.com   — 1 location in Port Blair + 4 symptom logs over 3 days →
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
from app.services.climatology import STUBBLE_REGIONS, region_pm25_mean
from app.services.geo import resolve_nearest_station
from app.services.ingestion import POLLUTANTS, ingest_weather_synthetic

RNG = random.Random(20260828)
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
HISTORY_DAYS = 35

# Real ambient air-quality monitoring stations from across India.
# (name, lat, lng, nominal cadence minutes, region-key). The region key drives
# the seasonal PM2.5 climatology (see app/services/climatology.py) and is also
# carried in the synthetic station's external_id so the live scheduler stays
# region-aware. Remote sites are included on purpose — a Leh or Port Blair
# location must work as well as an Anand Vihar one.
STATIONS = [
    # Indo-Gangetic Plain — the worst air in the country
    ("Anand Vihar, Delhi (CPCB)", 28.6469, 77.3154, 60, "igp"),
    ("Nehru Nagar, Kanpur (CPCB)", 26.4739, 80.3220, 60, "igp"),
    ("Central School, Lucknow (CPCB)", 26.8894, 80.9520, 60, "igp"),
    ("IGSC Planetarium, Patna (BSPCB)", 25.5941, 85.1376, 60, "igp"),
    # East
    ("Rabindra Bharati University, Kolkata (WBPCB)", 22.6289, 88.3800, 60, "east"),
    # West
    ("Bandra Kurla Complex, Mumbai (MPCB)", 19.0662, 72.8686, 60, "west"),
    ("Maninagar, Ahmedabad (GPCB)", 22.9960, 72.6030, 60, "west"),
    ("Adarsh Nagar, Jaipur (RSPCB)", 26.9020, 75.8360, 60, "west"),
    # Central
    ("Civil Lines, Nagpur (MPCB)", 21.1500, 79.0800, 120, "central"),
    # South
    ("Silk Board, Bengaluru (KSPCB)", 12.9177, 77.6233, 60, "south"),
    ("Alandur Bus Depot, Chennai (TNPCB)", 12.9990, 80.2000, 60, "south"),
    ("Sanathnagar, Hyderabad (TSPCB)", 17.4550, 78.4370, 60, "south"),
    # North-East
    ("Railway Colony, Guwahati (PCBA)", 26.1790, 91.7550, 120, "northeast"),
    ("Naharlagun, Itanagar (APSPCB)", 27.1050, 93.6960, 120, "northeast"),
    # Himalaya — very clean, remote
    ("Leh, Ladakh (CPCB)", 34.1526, 77.5771, 120, "himalaya"),
    ("Deorali, Gangtok (Sikkim SPCB)", 27.3250, 88.6160, 120, "himalaya"),
    # Islands / coastal — remote, sea-washed
    ("VSK Nagar, Port Blair (A&N PCC)", 11.6420, 92.7180, 120, "coastal"),
    ("Kavaratti, Lakshadweep (LPCC)", 10.5670, 72.6420, 180, "coastal"),
]


def _diwali_boost(ts: datetime) -> float:
    """Firecracker week: a multiplicative bump if `ts` lands within ~5 days of an
    approximate Diwali date for its year (celebrated nationwide)."""
    approx = {2024: (11, 1), 2025: (10, 21), 2026: (11, 8), 2027: (10, 29)}
    md = approx.get(ts.year)
    if not md:
        return 1.0
    diwali = ts.replace(month=md[0], day=md[1], hour=0, minute=0, second=0, microsecond=0)
    days = abs((ts - diwali).total_seconds()) / 86400
    return 1.0 + 0.9 * math.exp(-(days**2) / 8) if days < 6 else 1.0


def _diurnal_pm(ts: datetime, region: str, base_shift: float) -> float:
    hod = ts.hour + ts.minute / 60
    day = (NOW - ts).days
    clim = region_pm25_mean(region, ts.month)
    # slow multi-day episode swings so the model sees calm AND polluted regimes
    episode = 1.0 + 0.42 * math.sin(day / 4.0) + 0.22 * math.sin(day / 1.7)
    # two rush-hour humps + an early-morning inversion peak, as a fraction of the
    # monthly mean rather than a fixed additive curve
    shape = 0.72 + 0.30 * math.exp(-((hod - 8) ** 2) / 7) + 0.40 * math.exp(-((hod - 21) ** 2) / 9)
    val = (clim * shape * episode + base_shift) * _diwali_boost(ts)
    return max(4.0, val + RNG.gauss(0, clim * 0.05))


def seed_stations(db) -> list[Station]:
    out = []
    for i, (name, lat, lng, cadence, region) in enumerate(STATIONS):
        ext = f"syn-{region}-{i}"
        # key on the stable (source, external_id) so re-seeding after a rename
        # updates the row in place instead of colliding on the unique constraint
        st = db.execute(
            select(Station).where(Station.source == "synthetic", Station.external_id == ext)
        ).scalar_one_or_none()
        if not st:
            st = Station(source="synthetic", external_id=ext)
            db.add(st)
        st.location_name = name
        st.lat, st.lng = lat, lng
        st.nominal_cadence_minutes = cadence
        st.last_seen_at = NOW
        out.append(st)
    db.flush()
    return out


def seed_readings(db, stations: list[Station]) -> int:
    start = NOW - timedelta(days=HISTORY_DAYS)
    regions = [s[4] for s in STATIONS]
    total = 0
    # one deterministically-chosen station has a multi-day outage; another a
    # short calibration gap. Everything else just has its own slot-level rate.
    outages = {
        len(stations) - 2: (NOW - timedelta(days=13), NOW - timedelta(days=11)),
        3: (NOW - timedelta(days=6, hours=8), NOW - timedelta(days=5, hours=14)),
    }
    for si, st in enumerate(stations):
        region = regions[si] if si < len(regions) else "west"
        step = timedelta(minutes=st.nominal_cadence_minutes)
        outage = outages.get(si)
        burst_left = 0  # remaining slots of a short "sensor offline" burst
        # each site gets its own steady dropout rate and a small offset
        gap_prob = 0.08 + 0.24 * (((si * 2654435761) % 101) / 101)
        base_shift = RNG.uniform(-12, 22)
        # a stubble-smoke plume parked over an IGP site for a stretch
        plume = (
            (NOW - timedelta(days=9), NOW - timedelta(days=7))
            if region in STUBBLE_REGIONS and si % 3 == 0
            else None
        )
        t = start
        while t < NOW:
            in_outage = outage and outage[0] <= t < outage[1]
            if burst_left <= 0 and RNG.random() < 0.012:
                burst_left = RNG.randint(3, 9)  # sensor offline for a few hours
            if not in_outage and burst_left <= 0 and RNG.random() > gap_prob:
                pm25 = _diurnal_pm(t, region, base_shift)
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
        # a deliberately pan-India spread: the primary (first) location drives
        # the symptom history, so it sits in a high-PM2.5 IGP city; the others
        # show the model working in a clean southern metro and a remote
        # Himalayan town.
        seed_user(
            db,
            "demo@example.com",
            n_logs=48,
            span_days=25,
            locations=[
                ("Home — Kanpur", 26.4705, 80.3200),
                ("Work — Bengaluru", 12.9180, 77.6230),
                ("Parents — Gangtok", 27.3300, 88.6120),
            ],
        )
        seed_user(
            db,
            "new@example.com",
            n_logs=4,
            span_days=3,
            locations=[("Home — Port Blair", 11.6450, 92.7200)],
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
