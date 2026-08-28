"""Pydantic v2 request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------- auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: int
    email: EmailStr
    created_at: datetime


# ---------------------------------------------------------------- locations ---
class LocationIn(BaseModel):
    label: str = Field(max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class LocationOut(ORM):
    id: int
    label: str
    lat: float
    lng: float
    nearest_station_id: int | None
    distance_km: float | None
    resolved_at: datetime | None


# ----------------------------------------------------------------- stations ---
class StationOut(ORM):
    id: int
    source: str
    location_name: str
    lat: float
    lng: float
    nominal_cadence_minutes: int
    last_seen_at: datetime | None


class AqiReadingOut(ORM):
    id: int
    station_id: int
    pollutant: str
    value: float
    unit: str
    recorded_at: datetime


# ------------------------------------------------------------------ symptoms ---
class SymptomIn(BaseModel):
    severity: int = Field(ge=0, le=10)
    notes: str | None = Field(default=None, max_length=2000)
    peak_flow_value: float | None = Field(default=None, ge=0, le=1000)
    logged_at: datetime | None = None


class SymptomConfirmIn(BaseModel):
    peak_flow_value: float = Field(ge=0, le=1000)


class SymptomOut(ORM):
    id: int
    severity: int
    notes: str | None
    peak_flow_value: float | None
    peak_flow_photo_url: str | None
    ocr_confidence: float | None
    manually_confirmed: bool
    logged_at: datetime
    needs_confirmation: bool = False


class OcrResult(BaseModel):
    raw_text: str
    extracted_value: float | None
    confidence: float
    needs_confirmation: bool
    engine: str


# ------------------------------------------------------------------ exposure ---
class ExposureWindowOut(ORM):
    id: int
    location_id: int
    window_type: str
    window_start: datetime
    window_end: datetime
    avg_pm25: float | None
    avg_pm10: float | None
    avg_no2: float | None
    avg_o3: float | None
    avg_temp: float | None
    avg_humidity: float | None
    data_coverage_pct: float
    expected_slots: int
    observed_slots: int
    computed_at: datetime


class CoverageSummary(BaseModel):
    overall_coverage_pct: float
    by_window_type: dict[str, float]
    n_windows: int
    worst_window: ExposureWindowOut | None


# ---------------------------------------------------------------------- risk ---
class RiskModelOut(ORM):
    id: int
    user_id: int | None
    model_type: str
    algorithm: str
    model_version: int
    trained_at: datetime
    n_train: int
    n_test: int
    mae: float | None
    baseline_mae: float | None
    feature_importance_json: dict


class RiskPredictionOut(BaseModel):
    risk_score: float
    model_type: str
    algorithm: str
    model_version: int
    is_personalized: bool
    disclaimer: str
    lag_features: dict
    explanation: list[dict]
    data_coverage_pct: float | None
    predicted_at: datetime


class TrainResult(BaseModel):
    model_type: str
    algorithm: str
    n_train: int
    n_test: int
    mae: float | None
    baseline_mae: float | None
    feature_importance: dict
    note: str


# ------------------------------------------------------------------ advisory ---
class AdvisoryIn(BaseModel):
    question: str | None = Field(default=None, max_length=800)
    location_id: int | None = None


class Citation(BaseModel):
    marker: str  # "[1]"
    section_ref: str
    document_title: str
    score: float
    snippet: str


class AdvisoryOut(BaseModel):
    response_text: str
    citations: list[Citation]
    refused: bool
    context_used: dict
    created_at: datetime


# ------------------------------------------------------------------- privacy ---
class DataExport(BaseModel):
    exported_at: datetime
    user: UserOut
    locations: list[LocationOut]
    symptom_logs: list[SymptomOut]
    exposure_windows: list[ExposureWindowOut]
    risk_predictions: list[RiskPredictionOut]
    advisory_log: list[AdvisoryOut]
