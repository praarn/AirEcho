"""Exposure-window pipeline — a core deliverable.

The alignment problem: sensor readings arrive on an irregular cadence. A rolling
average computed as if the gaps weren't there is a lie. So every window we
materialize stores, alongside the averages:

    expected_slots     = round(window_minutes / station.nominal_cadence_minutes)
    observed_slots      = # of distinct cadence-sized buckets that actually got >=1 reading
    data_coverage_pct   = 100 * observed_slots / expected_slots      (capped at 100)

The averages themselves are plain means of *the data that exists* — we do not
impute, and we do not divide by the expected count. Coverage travels with the
number everywhere, right through to the dashboard, so a gappy period visibly
looks gappy instead of falsely confident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AqiReading,
    ExposureWindow,
    Station,
    UserLocation,
    WeatherDaily,
)

WINDOW_HOURS = {"6h": 6, "24h": 24, "72h": 72}
_POLLUTANT_COL = {"pm25": "avg_pm25", "pm10": "avg_pm10", "no2": "avg_no2", "o3": "avg_o3"}


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass
class WindowResult:
    window_type: str
    window_start: datetime
    window_end: datetime
    expected_slots: int
    observed_slots: int
    data_coverage_pct: float
    pollutant_means: dict[str, float] = field(default_factory=dict)
    avg_temp: float | None = None
    avg_humidity: float | None = None

    def as_row_kwargs(self) -> dict:
        row = {
            "window_type": self.window_type,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "expected_slots": self.expected_slots,
            "observed_slots": self.observed_slots,
            "data_coverage_pct": self.data_coverage_pct,
            "avg_temp": self.avg_temp,
            "avg_humidity": self.avg_humidity,
        }
        for pol, col in _POLLUTANT_COL.items():
            row[col] = self.pollutant_means.get(pol)
        return row


def compute_exposure_window(
    readings: pd.DataFrame,
    *,
    window_type: str,
    window_start: datetime,
    window_end: datetime,
    cadence_minutes: int,
    weather: pd.DataFrame | None = None,
) -> WindowResult:
    """Pure function — the unit under test in `tests/test_exposure_windows.py`.

    `readings` columns: `pollutant` (str), `value` (float), `recorded_at` (tz-aware).
    Only rows with `window_start <= recorded_at < window_end` are considered; the
    caller may pass a wider frame.
    """
    window_start = _utc(window_start)
    window_end = _utc(window_end)
    window_minutes = (window_end - window_start).total_seconds() / 60
    expected_slots = max(1, round(window_minutes / cadence_minutes))

    if readings.empty:
        in_window = readings
    else:
        rec = pd.to_datetime(readings["recorded_at"], utc=True)
        mask = (rec >= window_start) & (rec < window_end)
        in_window = readings.loc[mask].assign(_rec=rec[mask])

    observed_slots = 0
    pollutant_means: dict[str, float] = {}
    if not in_window.empty:
        slot_idx = (in_window["_rec"] - window_start).dt.total_seconds() // (cadence_minutes * 60)
        slot_idx = slot_idx.astype(int).clip(lower=0, upper=expected_slots - 1)
        observed_slots = int(slot_idx.nunique())
        for pol, grp in in_window.groupby("pollutant"):
            pollutant_means[str(pol)] = float(grp["value"].mean())

    coverage = min(100.0, 100.0 * observed_slots / expected_slots) if expected_slots else 0.0

    avg_temp = avg_humidity = None
    if weather is not None and not weather.empty:
        wdt = pd.to_datetime(weather["date"], utc=True)
        wmask = (wdt >= window_start - timedelta(days=1)) & (wdt < window_end)
        w = weather.loc[wmask]
        if not w.empty:
            avg_temp = float(w["temp_c"].mean()) if w["temp_c"].notna().any() else None
            avg_humidity = (
                float(w["humidity_pct"].mean()) if w["humidity_pct"].notna().any() else None
            )

    return WindowResult(
        window_type=window_type,
        window_start=window_start,
        window_end=window_end,
        expected_slots=expected_slots,
        observed_slots=observed_slots,
        data_coverage_pct=round(coverage, 2),
        pollutant_means={k: round(v, 3) for k, v in pollutant_means.items()},
        avg_temp=round(avg_temp, 2) if avg_temp is not None else None,
        avg_humidity=round(avg_humidity, 2) if avg_humidity is not None else None,
    )


def _readings_frame(db: Session, station_id: int, start: datetime, end: datetime) -> pd.DataFrame:
    rows = db.execute(
        select(AqiReading.pollutant, AqiReading.value, AqiReading.recorded_at).where(
            AqiReading.station_id == station_id,
            AqiReading.recorded_at >= start,
            AqiReading.recorded_at < end,
        )
    ).all()
    if not rows:
        return pd.DataFrame(columns=["pollutant", "value", "recorded_at"])
    return pd.DataFrame(rows, columns=["pollutant", "value", "recorded_at"])


def _weather_frame(db: Session, location_name: str) -> pd.DataFrame:
    rows = db.execute(
        select(WeatherDaily.date, WeatherDaily.temp_c, WeatherDaily.humidity_pct).where(
            WeatherDaily.location == location_name
        )
    ).all()
    if not rows:
        return pd.DataFrame(columns=["date", "temp_c", "humidity_pct"])
    return pd.DataFrame(rows, columns=["date", "temp_c", "humidity_pct"])


def materialize_for_location(
    db: Session,
    loc: UserLocation,
    *,
    reference_time: datetime | None = None,
    window_types: list[str] | None = None,
) -> list[ExposureWindow]:
    """Recompute + upsert exposure windows for one user-location, anchored at
    `reference_time` (defaults to now). Fully reproducible from raw readings."""
    ref = _utc(reference_time or datetime.now(UTC))
    window_types = window_types or list(WINDOW_HOURS)

    if loc.nearest_station_id is None:
        return []
    station = db.get(Station, loc.nearest_station_id)
    if station is None:
        return []

    weather = _weather_frame(db, station.location_name)
    widest = max(WINDOW_HOURS[w] for w in window_types)
    readings = _readings_frame(db, station.id, ref - timedelta(hours=widest), ref)

    out: list[ExposureWindow] = []
    for wt in window_types:
        start = ref - timedelta(hours=WINDOW_HOURS[wt])
        result = compute_exposure_window(
            readings,
            window_type=wt,
            window_start=start,
            window_end=ref,
            cadence_minutes=station.nominal_cadence_minutes,
            weather=weather,
        )
        existing = db.execute(
            select(ExposureWindow).where(
                ExposureWindow.user_id == loc.user_id,
                ExposureWindow.location_id == loc.id,
                ExposureWindow.window_type == wt,
                ExposureWindow.window_end == ref,
            )
        ).scalar_one_or_none()
        kwargs = result.as_row_kwargs()
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            existing.computed_at = datetime.now(UTC)
            out.append(existing)
        else:
            row = ExposureWindow(user_id=loc.user_id, location_id=loc.id, **kwargs)
            db.add(row)
            out.append(row)
    db.flush()
    return out


def materialize_all(db: Session, reference_time: datetime | None = None) -> int:
    n = 0
    for loc in db.execute(select(UserLocation)).scalars().all():
        n += len(materialize_for_location(db, loc, reference_time=reference_time))
    db.commit()
    return n


def coverage_summary(windows: list[ExposureWindow]) -> dict:
    if not windows:
        return {
            "overall_coverage_pct": 0.0,
            "by_window_type": {},
            "n_windows": 0,
            "worst_window": None,
        }
    by_type: dict[str, list[float]] = {}
    for w in windows:
        by_type.setdefault(w.window_type, []).append(w.data_coverage_pct)
    worst = min(windows, key=lambda w: w.data_coverage_pct)
    overall = sum(w.data_coverage_pct for w in windows) / len(windows)
    return {
        "overall_coverage_pct": round(overall, 2),
        "by_window_type": {k: round(sum(v) / len(v), 2) for k, v in by_type.items()},
        "n_windows": len(windows),
        "worst_window": worst,
    }
