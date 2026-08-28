"""ORM models. Shape follows the brief's data-model spec closely.

Privacy note: every table that holds personal health data (`symptom_logs`,
`exposure_windows`, `user_locations`, `risk_predictions`, `advisory_log`) carries
a non-null `user_id` FK, and the API layer *always* filters by the authenticated
user id (see `app/api/deps.py::scoped`). The population-fallback trainer reads
through `aggregate_training_frame()`, which strips `user_id` before returning.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, EmbeddingType

EMBED_DIM = 384  # all-MiniLM-L6-v2


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    locations: Mapped[list[UserLocation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # audit trail for rotation: which token replaced this one
    rotated_to: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))  # openaq | cpcb | synthetic
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    # nominal reporting cadence in minutes — used as the denominator for
    # data_coverage_pct so a gap can't hide.
    nominal_cadence_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_station_source_ext"),)


class AqiReading(Base):
    __tablename__ = "aqi_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    pollutant: Mapped[str] = mapped_column(String(16))  # pm25 pm10 no2 o3 so2 co
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="ug/m3")
    # stored EXACTLY as reported — never rounded or "cleaned" on ingest
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("station_id", "pollutant", "recorded_at", name="uq_reading_natural_key"),
    )


class WeatherDaily(Base):
    __tablename__ = "weather_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(String(120), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_station: Mapped[str] = mapped_column(String(120), default="synthetic")

    __table_args__ = (UniqueConstraint("location", "date", name="uq_weather_loc_date"),)


class UserLocation(Base):
    __tablename__ = "user_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(80))  # home | work | ...
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    nearest_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), nullable=True
    )
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="locations")


class SymptomLog(Base):
    __tablename__ = "symptom_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    severity: Mapped[int] = mapped_column(Integer)  # 0..10 self-report
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    peak_flow_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_flow_photo_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # low-confidence OCR reads are NOT trusted until the user confirms
    manually_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, default=_utcnow
    )


class ExposureWindow(Base):
    __tablename__ = "exposure_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("user_locations.id", ondelete="CASCADE"), index=True
    )
    window_type: Mapped[str] = mapped_column(String(4))  # 6h | 24h | 72h
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    avg_pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_no2: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_o3: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_humidity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # THE honest-about-gaps field. observed_slots / expected_slots * 100.
    data_coverage_pct: Mapped[float] = mapped_column(Float)
    expected_slots: Mapped[int] = mapped_column(Integer)
    observed_slots: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "location_id",
            "window_type",
            "window_end",
            name="uq_exposure_window_key",
        ),
    )


class RiskModel(Base):
    __tablename__ = "risk_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    model_type: Mapped[str] = mapped_column(String(24))  # personal | population_fallback
    algorithm: Mapped[str] = mapped_column(String(32))  # linear_regression | random_forest
    model_version: Mapped[int] = mapped_column(Integer, default=1)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    n_train: Mapped[int] = mapped_column(Integer, default=0)
    n_test: Mapped[int] = mapped_column(Integer, default=0)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_mae: Mapped[float | None] = mapped_column(Float, nullable=True)  # predict-the-mean
    feature_importance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("risk_models.id", ondelete="CASCADE"))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    risk_score: Mapped[float] = mapped_column(Float)  # predicted symptom severity 0..10
    lag_features_json: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation_json: Mapped[dict] = mapped_column(JSON, default=dict)


class GuidelineDocument(Base):
    __tablename__ = "guideline_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str] = mapped_column(String(40), default="WHO")  # WHO | CPCB
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GuidelineChunk(Base):
    __tablename__ = "guideline_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(
        ForeignKey("guideline_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text)
    section_ref: Mapped[str] = mapped_column(String(160))  # e.g. "WHO AQG 2021 §Table 3.1"
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType(EMBED_DIM), nullable=True)


class AdvisoryLog(Base):
    __tablename__ = "advisory_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_or_context: Mapped[str] = mapped_column(Text)
    retrieved_chunks_json: Mapped[list] = mapped_column(JSON, default=list)
    response_text: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IngestionEvent(Base):
    """A station going silent is itself a signal — recorded here, never left as a
    silent hole."""

    __tablename__ = "ingestion_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24))  # ok | gap | failure | station_silent
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target_table: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
