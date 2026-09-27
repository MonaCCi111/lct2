"""ORM-модели. Имена таблиц - по INTEGRATION_SPEC §1.5: objects, channels, predictions, tickets, audit_logs
(+ telemetry для среза 100k и state_dictionary из пакета ML)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CollectorObject(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    object_type: Mapped[str] = mapped_column(String(64))
    # Диапазон пикетов, распарсенный из названия объекта 3 уровня ("объект Кси ПК0-ПК202")
    piket_from: Mapped[float | None] = mapped_column(Float, nullable=True)
    piket_to: Mapped[float | None] = mapped_column(Float, nullable=True)


class SensorChannel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subsystem: Mapped[str] = mapped_column(String(128), index=True)
    sensor_type: Mapped[str] = mapped_column(String(128), index=True)
    tag: Mapped[str] = mapped_column(String(64))
    sensor_name: Mapped[str] = mapped_column(String(255))
    tag_root: Mapped[str] = mapped_column(String(16), index=True)
    piket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    piket_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Привязка к коллектору (объект 2 уровня). Источник: channel_current.parquet ML-пакета,
    # fallback - соответствие tag_root -> объект (см. init_db.py). Может быть NULL.
    object_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("objects.id"), nullable=True, index=True)
    object_map_source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class StateDictionaryRow(Base):
    __tablename__ = "state_dictionary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_type: Mapped[str] = mapped_column(String(128), index=True)
    state_text: Mapped[str] = mapped_column(String(255))
    is_alarm: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    state_set: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)


class TelemetryEvent(Base):
    """Срез телеметрии (dataset/representative_slice/telemetry_sample_100k.csv), нормализованный по спеку §1.2-1.4."""

    __tablename__ = "telemetry"
    __table_args__ = (Index("ix_telemetry_channel_ts", "channel_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_alarm: Mapped[bool] = mapped_column(Boolean)
    raw_value: Mapped[str] = mapped_column(String(255))
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[str] = mapped_column(String(16))  # normal | failure | alarm | unknown


class PredictionRecord(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("channels.id"), index=True)
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    prediction_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    model_domain: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str] = mapped_column(String(32))
    failure_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_category: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)  # low|medium|high|critical
    maintenance_urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lead_time_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    health_index_its: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_horizon_hours: Mapped[int] = mapped_column(Integer, default=24)
    primary_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_risk_factors: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class MaintenanceTicket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    prediction_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_id: Mapped[int] = mapped_column(Integer, index=True)
    piket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    work_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft|approved|rejected|completed
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_brigade: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_role: Mapped[str] = mapped_column(String(32), default="dispatcher")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskSnapshot(Base):
    """Почасовые срезы числа активных рисков (для analytics.risk_timeline)."""

    __tablename__ = "risk_snapshots"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    critical: Mapped[int] = mapped_column(Integer, default=0)
    high: Mapped[int] = mapped_column(Integer, default=0)
    medium: Mapped[int] = mapped_column(Integer, default=0)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
