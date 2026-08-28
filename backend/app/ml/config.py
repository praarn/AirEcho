"""Modeling constants — and, more importantly, *why* each one is what it is.

These numbers are design decisions, not tuning artifacts. Interview talking
points live here.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Lag structure — the whole point of the project
# --------------------------------------------------------------------------- #
# We predict *current / near-term* symptom severity from exposure at several
# points in the past, NOT from same-day co-occurrence. Each lag is the average
# exposure over a 6h sub-window ending `LAG_HOURS[i]` hours before the symptom
# was logged.
LAG_HOURS: tuple[int, ...] = (0, 6, 24, 72)
SUBWINDOW_HOURS: int = 6
POLLUTANTS: tuple[str, ...] = ("pm25", "pm10", "no2", "o3")

# A lag sub-window with coverage below this is still used (we never pretend the
# gap isn't there) but its low `coverage_lag{n}` feature lets the model discount
# it. Rows whose t-0 window has *zero* coverage are dropped — there is simply no
# exposure signal to learn from.
MIN_T0_COVERAGE_PCT: float = 1.0

# --------------------------------------------------------------------------- #
# Personal vs population fallback threshold
# --------------------------------------------------------------------------- #
# A brand-new user with 3 symptom logs does NOT have enough data for a
# meaningful personal model. We require BOTH:
#
#   * MIN_PERSONAL_SAMPLES aligned (feature-complete) symptom logs — enough for a
#     time-based split to leave a non-trivial test fold, and enough for a
#     RandomForest to see each lag/pollutant combination more than once.
#   * MIN_PERSONAL_DAYS of span — 30 logs all from one week describe one
#     pollution episode, not a personal pattern. Two weeks is the minimum that
#     can contain both a high and a low exposure regime.
#
# Below either bar the API serves the population-fallback model, labelled in the
# UI as "general pattern, not yet personalized to you".
MIN_PERSONAL_SAMPLES: int = 30
MIN_PERSONAL_DAYS: int = 14

# Pooled anonymized rows required before we will train a population model at all.
MIN_POPULATION_SAMPLES: int = 40

# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
# TIME-BASED split only. Symptom severity is a time series; a random split leaks
# the future into training and inflates the score. `tests/test_risk_model.py`
# asserts max(train.logged_at) <= min(test.logged_at).
TEST_FRACTION: float = 0.25

# --------------------------------------------------------------------------- #
# RandomForest — kept small and shallow on purpose. With tens-to-hundreds of
# noisy self-reported points, a deep forest just memorizes.
# --------------------------------------------------------------------------- #
RF_PARAMS = dict(n_estimators=200, max_depth=6, min_samples_leaf=3, random_state=42, n_jobs=-1)

ARTIFACT_DIR = "app/ml/artifacts"

DISCLAIMER_PERSONAL = (
    "Personalized model. Trained only on your own confirmed symptom logs and lagged "
    "exposure. This is a correlation in a small, noisy, self-reported sample — not "
    "medical advice and not causal evidence."
)
DISCLAIMER_POPULATION = (
    "General pattern, not yet personalized to you. Trained on anonymized, aggregated "
    "data from all users (no user identifiers). Log more symptoms over at least two "
    "weeks to unlock a personal model."
)
DISCLAIMER_HEURISTIC = (
    "No trained model yet. This is a rule-of-thumb reading of current PM2.5 against the "
    "WHO 24-hour guideline, shown only so the dashboard isn't empty."
)
