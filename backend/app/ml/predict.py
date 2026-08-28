"""Serving. Pick the best available model for a user, build the current feature
row, predict severity, and explain it via feature importances × current values.

Selection order:
  1. active personal RandomForest (user cleared the threshold)
  2. active population-fallback RandomForest
  3. heuristic (current PM2.5 vs WHO 24h guideline) — clearly labelled, never
     presented as a model output
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import joblib
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.config import (
    DISCLAIMER_HEURISTIC,
    DISCLAIMER_PERSONAL,
    DISCLAIMER_POPULATION,
    LAG_HOURS,
    SUBWINDOW_HOURS,
)
from app.ml.features import _primary_location, _readings_frame, _weather_frame, build_feature_row
from app.models import RiskModel, RiskPrediction, Station

WHO_PM25_24H = 15.0  # µg/m³ — WHO 2021 AQG; heuristic reference only


def _active_model(db: Session, user_id: int) -> RiskModel | None:
    personal = (
        db.execute(
            select(RiskModel).where(
                RiskModel.user_id == user_id,
                RiskModel.model_type == "personal",
                RiskModel.algorithm == "random_forest",
                RiskModel.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if personal:
        return personal
    return (
        db.execute(
            select(RiskModel).where(
                RiskModel.user_id.is_(None),
                RiskModel.model_type == "population_fallback",
                RiskModel.algorithm == "random_forest",
                RiskModel.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )


def _current_feature_row(db: Session, user_id: int) -> tuple[dict[str, float] | None, float | None]:
    loc = _primary_location(db, user_id)
    if loc is None or loc.nearest_station_id is None:
        return None, None
    station = db.get(Station, loc.nearest_station_id)
    if station is None:
        return None, None
    now = datetime.now(UTC)
    earliest = now - timedelta(hours=max(LAG_HOURS) + SUBWINDOW_HOURS)
    readings = _readings_frame(db, station.id, earliest, now)
    weather = _weather_frame(db, station.location_name)
    row = build_feature_row(
        db, station=station, symptom_time=now, readings=readings, weather=weather
    )
    return row, row.get("coverage_lag0")


def _explain(model: RiskModel, feature_row: dict[str, float], top: int = 6) -> list[dict]:
    importances: dict[str, float] = model.feature_importance_json.get("importances", {})
    if not importances:  # linear fallback
        importances = {
            k: abs(v) for k, v in model.feature_importance_json.get("coefficients", {}).items()
        }
    ranked = sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [
        {
            "feature": name,
            "importance": round(weight, 4),
            "current_value": round(float(feature_row.get(name, 0.0)), 2),
            "reads_as": _humanize(name),
        }
        for name, weight in ranked
    ]


def _humanize(feature: str) -> str:
    if feature.startswith("coverage_lag"):
        return f"data coverage of the exposure window {feature.split('lag')[1]}h before"
    if "_lag" in feature:
        pol, lag = feature.split("_lag")
        pretty = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO₂", "o3": "O₃"}.get(pol, pol)
        return (
            f"{pretty} exposure {lag}h before the symptom"
            if lag != "0"
            else f"recent {pretty} exposure"
        )
    return {"temp": "temperature", "humidity": "humidity"}.get(feature, feature)


def predict_for_user(db: Session, user_id: int, *, persist: bool = True) -> dict:
    feature_row, coverage = _current_feature_row(db, user_id)
    model = _active_model(db, user_id)
    now = datetime.now(UTC)

    if model is None or feature_row is None:
        pm25 = (feature_row or {}).get("pm25_lag0", 0.0) if feature_row else 0.0
        score = float(np.clip(2.0 + 4.0 * (pm25 / WHO_PM25_24H), 0, 10)) if pm25 else 2.0
        return {
            "risk_score": round(score, 2),
            "model_type": "heuristic",
            "algorithm": "who_pm25_ratio",
            "model_version": 0,
            "is_personalized": False,
            "disclaimer": DISCLAIMER_HEURISTIC,
            "lag_features": feature_row or {},
            "explanation": [
                {
                    "feature": "pm25_lag0",
                    "importance": 1.0,
                    "current_value": round(pm25, 2),
                    "reads_as": "current PM2.5 vs WHO 24h guideline (15 µg/m³)",
                }
            ],
            "data_coverage_pct": coverage,
            "predicted_at": now,
        }

    payload = joblib.load(model.artifact_path)
    rf = payload["rf"]
    feats = payload["features"]
    x = np.array([[feature_row.get(f, 0.0) for f in feats]], dtype=float)
    score = float(np.clip(rf.predict(x)[0], 0, 10))
    is_personal = model.model_type == "personal"

    result = {
        "risk_score": round(score, 2),
        "model_type": model.model_type,
        "algorithm": model.algorithm,
        "model_version": model.model_version,
        "is_personalized": is_personal,
        "disclaimer": DISCLAIMER_PERSONAL if is_personal else DISCLAIMER_POPULATION,
        "lag_features": {k: round(float(v), 3) for k, v in feature_row.items()},
        "explanation": _explain(model, feature_row),
        "data_coverage_pct": coverage,
        "predicted_at": now,
    }

    if persist:
        db.add(
            RiskPrediction(
                user_id=user_id,
                model_id=model.id,
                risk_score=result["risk_score"],
                lag_features_json=result["lag_features"],
                explanation_json={"top": result["explanation"]},
            )
        )
        db.commit()
    return result
