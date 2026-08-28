"""Lag-feature construction.

For a symptom logged at time `t`, build one feature row:

    pm25_lag0 ... o3_lag72     mean pollutant level over [anchor-6h, anchor)
                               where anchor = t - LAG_HOURS[i]
    coverage_lag0 ... _lag72   data coverage % of that same sub-window
    temp, humidity             weather over the t-0 sub-window

`coverage_lag*` is a real feature, not bookkeeping: it lets the model learn to
trust a lag less when the sensor was quiet. Rows whose t-0 window saw no data at
all are dropped by `build_training_frame`.

`tests/test_lag_features.py` is a centerpiece suite — it checks the right
historical window is pulled for each lag, plus the insufficient-history and
gap-straddling edge cases.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.config import (
    LAG_HOURS,
    MIN_T0_COVERAGE_PCT,
    POLLUTANTS,
    SUBWINDOW_HOURS,
)
from app.models import AqiReading, Station, SymptomLog, UserLocation, WeatherDaily
from app.services.exposure_pipeline import compute_exposure_window


def feature_names() -> list[str]:
    names: list[str] = []
    for lag in LAG_HOURS:
        for pol in POLLUTANTS:
            names.append(f"{pol}_lag{lag}")
        names.append(f"coverage_lag{lag}")
    names += ["temp", "humidity"]
    return names


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _readings_frame(db: Session, station_id: int, start: datetime, end: datetime) -> pd.DataFrame:
    rows = db.execute(
        select(AqiReading.pollutant, AqiReading.value, AqiReading.recorded_at).where(
            AqiReading.station_id == station_id,
            AqiReading.recorded_at >= start,
            AqiReading.recorded_at < end,
        )
    ).all()
    return (
        pd.DataFrame(rows, columns=["pollutant", "value", "recorded_at"])
        if rows
        else pd.DataFrame(columns=["pollutant", "value", "recorded_at"])
    )


def _weather_frame(db: Session, location_name: str) -> pd.DataFrame:
    rows = db.execute(
        select(WeatherDaily.date, WeatherDaily.temp_c, WeatherDaily.humidity_pct).where(
            WeatherDaily.location == location_name
        )
    ).all()
    return (
        pd.DataFrame(rows, columns=["date", "temp_c", "humidity_pct"])
        if rows
        else pd.DataFrame(columns=["date", "temp_c", "humidity_pct"])
    )


def build_feature_row(
    db: Session,
    *,
    station: Station,
    symptom_time: datetime,
    readings: pd.DataFrame | None = None,
    weather: pd.DataFrame | None = None,
) -> dict[str, float]:
    """One row of `feature_names()`. `readings`/`weather` may be pre-fetched
    (wider than needed) to avoid a query per symptom log."""
    symptom_time = _utc(symptom_time)
    cadence = station.nominal_cadence_minutes

    if readings is None:
        earliest = symptom_time - timedelta(hours=max(LAG_HOURS) + SUBWINDOW_HOURS)
        readings = _readings_frame(db, station.id, earliest, symptom_time)
    if weather is None:
        weather = _weather_frame(db, station.location_name)

    row: dict[str, float] = {}
    for lag in LAG_HOURS:
        anchor = symptom_time - timedelta(hours=lag)
        sub_start = anchor - timedelta(hours=SUBWINDOW_HOURS)
        res = compute_exposure_window(
            readings,
            window_type=f"lag{lag}",
            window_start=sub_start,
            window_end=anchor,
            cadence_minutes=cadence,
            weather=weather if lag == 0 else None,
        )
        for pol in POLLUTANTS:
            row[f"{pol}_lag{lag}"] = float(res.pollutant_means.get(pol, 0.0))
        row[f"coverage_lag{lag}"] = float(res.data_coverage_pct)
        if lag == 0:
            row["temp"] = float(res.avg_temp) if res.avg_temp is not None else 0.0
            row["humidity"] = float(res.avg_humidity) if res.avg_humidity is not None else 0.0
    return row


def _primary_location(db: Session, user_id: int) -> UserLocation | None:
    locs = db.execute(select(UserLocation).where(UserLocation.user_id == user_id)).scalars().all()
    for loc in locs:
        if loc.nearest_station_id is not None:
            return loc
    return locs[0] if locs else None


def build_training_frame(db: Session, user_id: int) -> pd.DataFrame:
    """Feature-complete rows for one user. Columns = feature_names() + severity +
    logged_at. Rows with zero t-0 coverage are dropped (no signal)."""
    loc = _primary_location(db, user_id)
    if loc is None or loc.nearest_station_id is None:
        return pd.DataFrame(columns=[*feature_names(), "severity", "logged_at"])
    station = db.get(Station, loc.nearest_station_id)
    if station is None:
        return pd.DataFrame(columns=[*feature_names(), "severity", "logged_at"])

    logs = db.execute(
        select(SymptomLog.severity, SymptomLog.logged_at)
        .where(SymptomLog.user_id == user_id)
        .order_by(SymptomLog.logged_at)
    ).all()
    if not logs:
        return pd.DataFrame(columns=[*feature_names(), "severity", "logged_at"])

    span_start = _utc(logs[0].logged_at) - timedelta(hours=max(LAG_HOURS) + SUBWINDOW_HOURS)
    span_end = _utc(logs[-1].logged_at) + timedelta(hours=1)
    readings = _readings_frame(db, station.id, span_start, span_end)
    weather = _weather_frame(db, station.location_name)

    records = []
    for sev, logged_at in logs:
        feats = build_feature_row(
            db, station=station, symptom_time=logged_at, readings=readings, weather=weather
        )
        if feats["coverage_lag0"] < MIN_T0_COVERAGE_PCT:
            continue
        feats["severity"] = float(sev)
        feats["logged_at"] = _utc(logged_at)
        records.append(feats)

    if not records:
        return pd.DataFrame(columns=[*feature_names(), "severity", "logged_at"])
    return pd.DataFrame.from_records(records)[[*feature_names(), "severity", "logged_at"]]


def aggregate_training_frame(db: Session) -> pd.DataFrame:
    """Pooled rows across ALL users for the population-fallback model.

    Privacy: `user_id` is never added to the frame. Rows from every user are
    concatenated and shuffled by time only. `tests/test_isolation.py` asserts the
    returned frame has no `user_id` column.
    """
    from app.models import User

    frames = []
    for (uid,) in db.execute(select(User.id)).all():
        f = build_training_frame(db, uid)
        if not f.empty:
            frames.append(f)  # no user_id column — see docstring
    if not frames:
        return pd.DataFrame(columns=[*feature_names(), "severity", "logged_at"])
    pooled = pd.concat(frames, ignore_index=True).sort_values("logged_at").reset_index(drop=True)
    assert "user_id" not in pooled.columns, "population frame must be anonymized"
    return pooled


def time_based_split(
    frame: pd.DataFrame, test_fraction: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split. Never random — see app/ml/config.py."""
    ordered = frame.sort_values("logged_at").reset_index(drop=True)
    cut = int(len(ordered) * (1 - test_fraction))
    cut = max(1, min(cut, len(ordered) - 1)) if len(ordered) > 1 else len(ordered)
    return ordered.iloc[:cut].copy(), ordered.iloc[cut:].copy()
