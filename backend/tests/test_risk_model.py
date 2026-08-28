"""Risk-model tests: time-based evaluation, the personal/population threshold
gate, and the anonymization of the population training frame.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.ml.config import MIN_PERSONAL_SAMPLES
from app.ml.features import aggregate_training_frame, build_training_frame
from app.ml.predict import predict_for_user
from app.ml.train import train_personal, train_population
from app.models import AqiReading, Station, SymptomLog, User, UserLocation

NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


_STATION_SEQ = iter(range(1, 10_000))


def _make_station(db) -> Station:
    n = next(_STATION_SEQ)
    st = Station(
        source="synthetic",
        external_id=f"rm-{n}",
        location_name=f"RM{n}",
        lat=0.0,
        lng=0.0,
        nominal_cadence_minutes=60,
    )
    db.add(st)
    db.flush()
    return st


def _hourly_readings(db, station_id: int, days: int):
    for h in range(days * 24):
        ts = NOW - timedelta(hours=h)
        day = h / 24
        pm = 30 + 25 * math.sin(day / 3.0) + 6 * math.sin((ts.hour - 8) / 3.0)
        for pol, f in (("pm25", 1.0), ("pm10", 1.6), ("no2", 0.5), ("o3", 0.0)):
            val = max(2.0, (70 - pm * 0.4) if pol == "o3" else pm * f)
            db.add(
                AqiReading(
                    station_id=station_id, pollutant=pol, value=round(val, 2), recorded_at=ts
                )
            )
    db.flush()


def _pm_lag24(db, station_id: int, at: datetime) -> float:
    lo, hi = at - timedelta(hours=30), at - timedelta(hours=24)
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


def _seed_user(db, email: str, *, n_logs: int, span_days: int) -> tuple[User, Station]:
    user = User(email=email, hashed_password="x")
    db.add(user)
    db.flush()
    st = _make_station(db)
    db.add(
        UserLocation(
            user_id=user.id,
            label="home",
            lat=0.0,
            lng=0.0,
            nearest_station_id=st.id,
            distance_km=0.0,
        )
    )
    _hourly_readings(db, st.id, days=span_days + 4)
    db.flush()

    for i in range(n_logs):
        t = NOW - timedelta(days=span_days) + timedelta(hours=i * (span_days * 24 / n_logs))
        pm = _pm_lag24(db, st.id, t)
        # strong lagged signal + mild noise → RF should beat predict-the-mean
        sev = int(max(0, min(10, round(0.09 * pm + 0.4 * math.sin(i)))))
        db.add(SymptomLog(user_id=user.id, severity=sev, logged_at=t))
    db.flush()
    db.commit()
    return user, st


def test_personal_model_trains_and_beats_baseline(db):
    user, _ = _seed_user(db, "rich@t.local", n_logs=48, span_days=24)
    out = train_personal(db, user.id)

    assert out.trained, out.reason
    assert out.model_type == "personal"
    assert out.algorithm == "random_forest"
    assert out.n_train >= 1 and out.n_test >= 1
    assert out.n_train + out.n_test == len(build_training_frame(db, user.id))
    assert out.mae is not None and out.mae >= 0
    # the whole point: lagged model < predict-the-mean on the held-out FUTURE fold
    assert out.mae < out.baseline_mae
    assert out.feature_importance
    # importance is over exactly the known feature set
    from app.ml.features import feature_names

    assert set(out.feature_importance).issubset(set(feature_names()))


def test_time_based_split_test_fold_is_strictly_future(db):
    user, _ = _seed_user(db, "split@t.local", n_logs=40, span_days=20)
    frame = build_training_frame(db, user.id)
    from app.ml.config import TEST_FRACTION
    from app.ml.features import time_based_split

    train, test = time_based_split(frame, TEST_FRACTION)
    assert train["logged_at"].max() <= test["logged_at"].min()
    # no timestamp appears in both folds
    assert set(train["logged_at"]).isdisjoint(set(test["logged_at"]))


def test_thin_user_falls_back_to_population(db):
    thin, _ = _seed_user(db, "thin@t.local", n_logs=5, span_days=3)
    out = train_personal(db, thin.id)
    assert out.trained is False
    assert "threshold" in out.reason
    assert f"/{MIN_PERSONAL_SAMPLES}" in out.reason

    # give the population model something to learn from, then predict
    _seed_user(db, "donor@t.local", n_logs=64, span_days=24)
    pop = train_population(db)
    assert pop.trained, pop.reason

    pred = predict_for_user(db, thin.id, persist=False)
    assert pred["is_personalized"] is False
    assert pred["model_type"] == "population_fallback"
    assert "general pattern" in pred["disclaimer"].lower()
    assert 0 <= pred["risk_score"] <= 10


def test_population_training_frame_is_anonymized(db):
    _seed_user(db, "p1@t.local", n_logs=40, span_days=20)
    _seed_user(db, "p2@t.local", n_logs=40, span_days=20)
    frame = aggregate_training_frame(db)
    assert "user_id" not in frame.columns
    assert "email" not in frame.columns
    assert len(frame) > 0
