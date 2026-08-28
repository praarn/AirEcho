from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbDep
from app.ml.predict import predict_for_user
from app.ml.train import train_personal, train_population
from app.models import RiskModel
from app.schemas import RiskModelOut, RiskPredictionOut, TrainResult

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/score", response_model=RiskPredictionOut)
def score(user: CurrentUser, db: DbDep):
    return predict_for_user(db, user.id)


@router.get("/explain")
def explain(user: CurrentUser, db: DbDep):
    """The 'why this score' payload: active model metadata + ranked feature
    importances + the current lag-feature values."""
    result = predict_for_user(db, user.id, persist=False)
    return {
        "model_type": result["model_type"],
        "algorithm": result["algorithm"],
        "model_version": result["model_version"],
        "is_personalized": result["is_personalized"],
        "disclaimer": result["disclaimer"],
        "data_coverage_pct": result["data_coverage_pct"],
        "explanation": result["explanation"],
        "lag_features": result["lag_features"],
    }


@router.get("/models", response_model=list[RiskModelOut])
def models(user: CurrentUser, db: DbDep):
    """This user's personal model versions + the shared population fallback."""
    rows = (
        db.execute(
            select(RiskModel)
            .where((RiskModel.user_id == user.id) | (RiskModel.user_id.is_(None)))
            .order_by(desc(RiskModel.trained_at))
        )
        .scalars()
        .all()
    )
    return rows


@router.post("/train", response_model=TrainResult)
def train(user: CurrentUser, db: DbDep):
    """Attempt a personal retrain; fall back to (and report) the population model
    when the user is below the minimum-data threshold."""
    personal = train_personal(db, user.id)
    if personal.trained:
        return TrainResult(
            model_type="personal",
            algorithm=personal.algorithm,
            n_train=personal.n_train,
            n_test=personal.n_test,
            mae=personal.mae,
            baseline_mae=personal.baseline_mae,
            feature_importance=personal.feature_importance,
            note=f"personal RandomForest v{personal.model_version}; "
            f"linear baseline MAE {personal.linear_mae:.3f}",
        )
    pop = train_population(db)
    return TrainResult(
        model_type="population_fallback",
        algorithm=pop.algorithm or "none",
        n_train=pop.n_train,
        n_test=pop.n_test,
        mae=pop.mae,
        baseline_mae=pop.baseline_mae,
        feature_importance=pop.feature_importance,
        note=f"personal skipped ({personal.reason}); "
        + ("population model trained" if pop.trained else f"population skipped ({pop.reason})"),
    )
