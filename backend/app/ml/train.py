"""Model training.

Pipeline per model:
  1. build feature frame (personal) or pooled anonymized frame (population)
  2. gate on the minimum-data thresholds (app/ml/config.py)
  3. TIME-BASED split (never random)
  4. fit lagged LinearRegression (interpretable baseline) + RandomForestRegressor
  5. MAE on the held-out (future) fold, plus a predict-the-mean baseline MAE
  6. persist joblib artifact + a versioned `risk_models` row; RF is marked active

`train_personal` returns None when the user is below threshold — the caller then
serves the population fallback.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.config import (
    ARTIFACT_DIR,
    MIN_PERSONAL_DAYS,
    MIN_PERSONAL_SAMPLES,
    MIN_POPULATION_SAMPLES,
    RF_PARAMS,
    TEST_FRACTION,
)
from app.ml.features import (
    aggregate_training_frame,
    build_training_frame,
    feature_names,
    time_based_split,
)
from app.models import RiskModel


@dataclass
class TrainOutcome:
    trained: bool
    reason: str = ""
    model_type: str = ""
    algorithm: str = ""
    n_train: int = 0
    n_test: int = 0
    mae: float | None = None
    baseline_mae: float | None = None
    linear_mae: float | None = None
    feature_importance: dict = field(default_factory=dict)
    model_id: int | None = None
    model_version: int = 1


def _span_days(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    lo, hi = frame["logged_at"].min(), frame["logged_at"].max()
    return (hi - lo).total_seconds() / 86400


def _fit_and_score(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    feats = feature_names()
    x_tr, y_tr = train[feats].to_numpy(float), train["severity"].to_numpy(float)
    x_te, y_te = test[feats].to_numpy(float), test["severity"].to_numpy(float)

    linear = Pipeline([("scale", StandardScaler()), ("lr", LinearRegression())])
    linear.fit(x_tr, y_tr)
    linear_mae = float(mean_absolute_error(y_te, np.clip(linear.predict(x_te), 0, 10)))

    rf = RandomForestRegressor(**RF_PARAMS)
    rf.fit(x_tr, y_tr)
    rf_mae = float(mean_absolute_error(y_te, np.clip(rf.predict(x_te), 0, 10)))

    baseline_mae = float(mean_absolute_error(y_te, np.full_like(y_te, y_tr.mean())))

    rf_importance = {
        f: round(float(w), 5) for f, w in zip(feats, rf.feature_importances_, strict=True)
    }
    linear_coef = {
        f: round(float(c), 5) for f, c in zip(feats, linear.named_steps["lr"].coef_, strict=True)
    }
    return {
        "rf": rf,
        "linear": linear,
        "rf_mae": rf_mae,
        "linear_mae": linear_mae,
        "baseline_mae": baseline_mae,
        "rf_importance": rf_importance,
        "linear_coef": linear_coef,
    }


def _persist_artifact(tag: str, payload: dict) -> str:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    path = os.path.join(ARTIFACT_DIR, f"{tag}.joblib")
    joblib.dump(payload, path)
    return path


def _next_version(db: Session, *, user_id: int | None, model_type: str) -> int:
    q = select(RiskModel).where(RiskModel.model_type == model_type)
    q = (
        q.where(RiskModel.user_id == user_id)
        if user_id is not None
        else q.where(RiskModel.user_id.is_(None))
    )
    prev = db.execute(q.order_by(RiskModel.model_version.desc())).scalars().first()
    return (prev.model_version + 1) if prev else 1


def _deactivate_previous(db: Session, *, user_id: int | None, model_type: str) -> None:
    q = db.query(RiskModel).filter(RiskModel.model_type == model_type)
    q = (
        q.filter(RiskModel.user_id == user_id)
        if user_id is not None
        else q.filter(RiskModel.user_id.is_(None))
    )
    q.update({"is_active": False})


def _store_models(
    db: Session,
    *,
    user_id: int | None,
    model_type: str,
    scored: dict,
    frame: pd.DataFrame,
    n_train: int,
    n_test: int,
    version: int,
    artifact_path: str,
) -> RiskModel:
    _deactivate_previous(db, user_id=user_id, model_type=model_type)
    # interpretable baseline row (kept for the metrics story, not served)
    db.add(
        RiskModel(
            user_id=user_id,
            model_type=model_type,
            algorithm="linear_regression",
            model_version=version,
            n_train=n_train,
            n_test=n_test,
            mae=scored["linear_mae"],
            baseline_mae=scored["baseline_mae"],
            feature_importance_json={"coefficients": scored["linear_coef"]},
            artifact_path=artifact_path,
            is_active=False,
        )
    )
    rf_row = RiskModel(
        user_id=user_id,
        model_type=model_type,
        algorithm="random_forest",
        model_version=version,
        n_train=n_train,
        n_test=n_test,
        mae=scored["rf_mae"],
        baseline_mae=scored["baseline_mae"],
        feature_importance_json={
            "importances": scored["rf_importance"],
            "_baseline_linear_mae": scored["linear_mae"],
        },
        artifact_path=artifact_path,
        is_active=True,
    )
    db.add(rf_row)
    db.flush()
    return rf_row


def train_personal(db: Session, user_id: int) -> TrainOutcome:
    frame = build_training_frame(db, user_id)
    n = len(frame)
    span = _span_days(frame)
    if n < MIN_PERSONAL_SAMPLES or span < MIN_PERSONAL_DAYS:
        return TrainOutcome(
            trained=False,
            reason=(
                f"below personal threshold: {n}/{MIN_PERSONAL_SAMPLES} feature-complete logs, "
                f"{span:.1f}/{MIN_PERSONAL_DAYS} day span"
            ),
        )
    train, test = time_based_split(frame, TEST_FRACTION)
    scored = _fit_and_score(train, test)
    version = _next_version(db, user_id=user_id, model_type="personal")
    artifact = _persist_artifact(
        f"personal_u{user_id}_v{version}",
        {"rf": scored["rf"], "linear": scored["linear"], "features": feature_names()},
    )
    row = _store_models(
        db,
        user_id=user_id,
        model_type="personal",
        scored=scored,
        frame=frame,
        n_train=len(train),
        n_test=len(test),
        version=version,
        artifact_path=artifact,
    )
    db.commit()
    return TrainOutcome(
        trained=True,
        model_type="personal",
        algorithm="random_forest",
        n_train=len(train),
        n_test=len(test),
        mae=scored["rf_mae"],
        baseline_mae=scored["baseline_mae"],
        linear_mae=scored["linear_mae"],
        feature_importance=scored["rf_importance"],
        model_id=row.id,
        model_version=version,
    )


def train_population(db: Session) -> TrainOutcome:
    frame = aggregate_training_frame(db)  # anonymized — no user_id column
    n = len(frame)
    if n < MIN_POPULATION_SAMPLES:
        return TrainOutcome(
            trained=False,
            reason=f"below population threshold: {n}/{MIN_POPULATION_SAMPLES} pooled rows",
        )
    train, test = time_based_split(frame, TEST_FRACTION)
    scored = _fit_and_score(train, test)
    version = _next_version(db, user_id=None, model_type="population_fallback")
    artifact = _persist_artifact(
        f"population_v{version}",
        {"rf": scored["rf"], "linear": scored["linear"], "features": feature_names()},
    )
    row = _store_models(
        db,
        user_id=None,
        model_type="population_fallback",
        scored=scored,
        frame=frame,
        n_train=len(train),
        n_test=len(test),
        version=version,
        artifact_path=artifact,
    )
    db.commit()
    return TrainOutcome(
        trained=True,
        model_type="population_fallback",
        algorithm="random_forest",
        n_train=len(train),
        n_test=len(test),
        mae=scored["rf_mae"],
        baseline_mae=scored["baseline_mae"],
        linear_mae=scored["linear_mae"],
        feature_importance=scored["rf_importance"],
        model_id=row.id,
        model_version=version,
    )


def retrain_everything(db: Session) -> dict:
    """Called by the scheduler and the seed script."""
    from app.models import User

    pop = train_population(db)
    personal: dict[int, str] = {}
    for (uid,) in db.execute(select(User.id)).all():
        out = train_personal(db, uid)
        personal[uid] = "trained" if out.trained else out.reason
    return {
        "population": pop.reason if not pop.trained else f"trained mae={pop.mae:.3f}",
        "personal": personal,
        "at": datetime.now(UTC).isoformat(),
    }


def write_metrics_doc(db: Session, path: str = "../docs/METRICS.md") -> None:  # pragma: no cover
    rows = db.execute(select(RiskModel).where(RiskModel.is_active.is_(True))).scalars().all()
    lines = ["# Measured metrics (generated)\n"]
    for r in rows:
        who = "population fallback" if r.user_id is None else f"user {r.user_id}"
        lines.append(
            f"- **{who}** ({r.algorithm} v{r.model_version}): "
            f"MAE {r.mae:.3f} vs predict-the-mean {r.baseline_mae:.3f} "
            f"(train {r.n_train} / test {r.n_test})"
        )
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps({"metrics_written": path, "models": len(rows)}))
