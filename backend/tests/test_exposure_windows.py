"""Centerpiece suite #1 — the exposure-window pipeline is honest about gaps.

Synthetic readings with deliberate holes; assert `data_coverage_pct` and the
rolling averages are computed against the data that ACTUALLY exists, never as if
the gap weren't there.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.services.exposure_pipeline import compute_exposure_window

T0 = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


def _readings(rows: list[tuple[str, float, datetime]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["pollutant", "value", "recorded_at"])


def test_full_coverage_no_gaps():
    rows = [("pm25", 10.0 + i, T0 + timedelta(hours=i)) for i in range(6)]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.expected_slots == 6
    assert res.observed_slots == 6
    assert res.data_coverage_pct == 100.0
    assert res.pollutant_means["pm25"] == pytest.approx(12.5)  # mean(10..15)


def test_half_coverage_only_counts_available_data():
    # readings only in the first 3 of 6 hourly slots
    rows = [("pm25", v, T0 + timedelta(hours=h)) for h, v in [(0, 10), (1, 20), (2, 30)]]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.observed_slots == 3
    assert res.data_coverage_pct == 50.0
    # average is over the 3 real points, NOT divided by the 6 expected slots
    assert res.pollutant_means["pm25"] == pytest.approx(20.0)


def test_multiple_readings_in_one_slot_count_once():
    rows = [
        ("pm25", 10.0, T0 + timedelta(minutes=5)),
        ("pm25", 30.0, T0 + timedelta(minutes=40)),  # same 60-min slot
        ("pm25", 50.0, T0 + timedelta(hours=2, minutes=1)),
    ]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.observed_slots == 2  # slot 0 and slot 2
    assert res.data_coverage_pct == pytest.approx(33.33, abs=0.01)
    assert res.pollutant_means["pm25"] == pytest.approx(30.0)  # mean(10,30,50)


def test_readings_outside_window_are_ignored():
    rows = [
        ("pm25", 999.0, T0 - timedelta(hours=1)),  # before
        ("pm25", 10.0, T0 + timedelta(hours=1)),
        ("pm25", 888.0, T0 + timedelta(hours=7)),  # after
    ]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.observed_slots == 1
    assert res.pollutant_means["pm25"] == pytest.approx(10.0)


def test_no_readings_zero_coverage_no_means():
    res = compute_exposure_window(
        _readings([]),
        window_type="24h",
        window_start=T0,
        window_end=T0 + timedelta(hours=24),
        cadence_minutes=60,
    )
    assert res.expected_slots == 24
    assert res.observed_slots == 0
    assert res.data_coverage_pct == 0.0
    assert res.pollutant_means == {}


def test_coarser_cadence_changes_expected_slots():
    # 24h window, station reports every 2h → only 12 expected slots
    rows = [("pm25", 20.0, T0 + timedelta(hours=2 * i)) for i in range(6)]  # 12h of data
    res = compute_exposure_window(
        _readings(rows),
        window_type="24h",
        window_start=T0,
        window_end=T0 + timedelta(hours=24),
        cadence_minutes=120,
    )
    assert res.expected_slots == 12
    assert res.observed_slots == 6
    assert res.data_coverage_pct == 50.0


def test_coverage_capped_at_100_when_oversampled():
    # station reports every 30min but window cadence assumed 60 → 12 readings, 6 slots
    rows = [("pm25", 15.0, T0 + timedelta(minutes=30 * i)) for i in range(12)]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.data_coverage_pct == 100.0
    assert res.observed_slots == 6


def test_per_pollutant_means_independent():
    rows = [
        ("pm25", 10.0, T0),
        ("pm25", 20.0, T0 + timedelta(hours=1)),
        ("no2", 4.0, T0),
        ("o3", 60.0, T0 + timedelta(hours=1)),
    ]
    res = compute_exposure_window(
        _readings(rows),
        window_type="6h",
        window_start=T0,
        window_end=T0 + timedelta(hours=6),
        cadence_minutes=60,
    )
    assert res.pollutant_means["pm25"] == pytest.approx(15.0)
    assert res.pollutant_means["no2"] == pytest.approx(4.0)
    assert res.pollutant_means["o3"] == pytest.approx(60.0)


def test_weather_joined_into_window():
    weather = pd.DataFrame(
        [(T0 + timedelta(hours=3), 28.0, 55.0)], columns=["date", "temp_c", "humidity_pct"]
    )
    res = compute_exposure_window(
        _readings([("pm25", 10.0, T0)]),
        window_type="24h",
        window_start=T0,
        window_end=T0 + timedelta(hours=24),
        cadence_minutes=60,
        weather=weather,
    )
    assert res.avg_temp == pytest.approx(28.0)
    assert res.avg_humidity == pytest.approx(55.0)


def test_materialize_persists_and_is_reproducible(client, auth):
    # build a location + station + readings through the API/DB, then materialize
    from app.database import SessionLocal
    from app.models import AqiReading, Station, UserLocation

    db = SessionLocal()
    try:
        st = Station(
            source="synthetic",
            external_id="t1",
            location_name="TestSt",
            lat=10.0,
            lng=10.0,
            nominal_cadence_minutes=60,
        )
        db.add(st)
        db.flush()
        base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        for h in range(24):
            if h % 2 == 0:  # every other hour → ~50% coverage on 24h window
                db.add(
                    AqiReading(
                        station_id=st.id,
                        pollutant="pm25",
                        value=40.0,
                        recorded_at=base - timedelta(hours=h),
                    )
                )
        db.commit()
        loc = UserLocation(
            user_id=_uid(db),
            label="home",
            lat=10.0,
            lng=10.0,
            nearest_station_id=st.id,
            distance_km=0.0,
        )
        db.add(loc)
        db.commit()

        from app.services.exposure_pipeline import materialize_for_location

        first = {
            w.window_type: w.data_coverage_pct
            for w in materialize_for_location(db, loc, reference_time=base)
        }
        db.commit()
        second = {
            w.window_type: w.data_coverage_pct
            for w in materialize_for_location(db, loc, reference_time=base)
        }
        db.commit()
        assert first == second  # deterministic re-materialization
        assert 40.0 <= first["24h"] <= 60.0
    finally:
        db.close()


def _uid(db) -> int:
    from app.models import User

    return db.query(User).first().id
