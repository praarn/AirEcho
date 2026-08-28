"""Centerpiece suite #2 — lag-feature construction.

Assert t-0 / t-6h / t-24h features are pulled from the correct historical
sub-windows, and cover the edge cases: insufficient history and a lag window that
straddles a data gap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.ml.config import MIN_T0_COVERAGE_PCT
from app.ml.features import (
    build_feature_row,
    build_training_frame,
    feature_names,
    time_based_split,
)
from app.models import AqiReading, Station, SymptomLog, User, UserLocation

T = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _station(db) -> Station:
    st = Station(
        source="synthetic",
        external_id="lagtest",
        location_name="LagSt",
        lat=0.0,
        lng=0.0,
        nominal_cadence_minutes=60,
    )
    db.add(st)
    db.flush()
    return st


def _piecewise_pm25(db, station_id: int, at: datetime):
    """pm25 = 10 in [at-6h,at), 20 in [at-12h,at-6h), 40 in [at-30h,at-24h),
    5 everywhere else back to at-90h. Hourly cadence."""
    for h in range(1, 91):
        ts = at - timedelta(hours=h)
        delta = (at - ts).total_seconds() / 3600
        if delta <= 6:
            v = 10.0
        elif delta <= 12:
            v = 20.0
        elif 24 < delta <= 30:
            v = 40.0
        else:
            v = 5.0
        db.add(AqiReading(station_id=station_id, pollutant="pm25", value=v, recorded_at=ts))
    db.flush()


def test_each_lag_pulls_its_own_historical_window(db):
    st = _station(db)
    _piecewise_pm25(db, st.id, T)
    row = build_feature_row(db, station=st, symptom_time=T)

    assert row["pm25_lag0"] == pytest.approx(10.0)
    assert row["pm25_lag6"] == pytest.approx(20.0)
    assert row["pm25_lag24"] == pytest.approx(40.0)
    # lag72 window [T-78h, T-72h) falls in the "5 everywhere else" region
    assert row["pm25_lag72"] == pytest.approx(5.0)
    assert set(feature_names()) == set(row.keys())


def test_insufficient_history_yields_zero_coverage(db):
    st = _station(db)
    # only 2h of data, far too little for any lag window ending at T
    for h in (1, 2):
        db.add(
            AqiReading(
                station_id=st.id, pollutant="pm25", value=12.0, recorded_at=T - timedelta(hours=h)
            )
        )
    db.flush()
    row = build_feature_row(db, station=st, symptom_time=T)
    # t-0 window [T-6h,T) saw 2 of 6 slots
    assert 0 < row["coverage_lag0"] <= 40
    # t-24h window saw nothing
    assert row["coverage_lag24"] == 0.0
    assert row["pm25_lag24"] == 0.0


def test_training_frame_drops_rows_with_no_t0_signal(db):
    user = User(email="lag@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    st = _station(db)
    loc = UserLocation(
        user_id=user.id, label="home", lat=0.0, lng=0.0, nearest_station_id=st.id, distance_km=0.0
    )
    db.add(loc)
    # one symptom WITH exposure data, one WAY in the past with none
    _piecewise_pm25(db, st.id, T)
    db.add(SymptomLog(user_id=user.id, severity=5, logged_at=T))
    db.add(SymptomLog(user_id=user.id, severity=3, logged_at=T - timedelta(days=60)))
    db.flush()

    frame = build_training_frame(db, user.id)
    assert len(frame) == 1
    assert (frame["coverage_lag0"] >= MIN_T0_COVERAGE_PCT).all()


def test_gap_straddling_lag_window_is_flagged_not_faked(db):
    st = _station(db)
    # dense data except a hole exactly over the lag-24h window [T-30h, T-24h)
    for h in range(1, 91):
        delta = h
        if 24 < delta <= 30:
            continue  # the gap
        v = 10.0 if delta <= 6 else 8.0
        db.add(
            AqiReading(
                station_id=st.id, pollutant="pm25", value=v, recorded_at=T - timedelta(hours=h)
            )
        )
    db.flush()

    row = build_feature_row(db, station=st, symptom_time=T)
    assert row["coverage_lag0"] > 50  # recent window healthy
    assert row["coverage_lag24"] == 0.0  # honestly reported as empty
    assert row["pm25_lag24"] == 0.0  # not back-filled from neighbours


def test_time_based_split_never_leaks_future():
    frame = pd.DataFrame(
        {
            "logged_at": pd.date_range("2026-08-01", periods=20, freq="12h", tz="UTC"),
            "severity": range(20),
            **{f: 0.0 for f in feature_names()},
        }
    )
    train, test = time_based_split(frame, test_fraction=0.25)
    assert len(train) == 15 and len(test) == 5
    assert train["logged_at"].max() <= test["logged_at"].min()
