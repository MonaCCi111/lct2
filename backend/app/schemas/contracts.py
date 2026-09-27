"""Pydantic v2 схемы API v1.

Формы ответов - 1 в 1 по фактическому потреблению фронтенда (docs/BACKEND_API_CONTRACT_V1.md,
frontend/src/api/dto/*.ts, ветка frontend-dolos) с сохранением имён полей INTEGRATION_SPEC там, где они совпадают.
Имена полей менять нельзя.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high", "critical"]
MaintenanceUrgency = Literal["FLASH_1_6H", "URGENT_6_24H", "PLANNED_24_48H", "NORMAL"]
ModelDomain = Literal["POWER_PHASE", "ANALOG_TEMP", "ANALOG_GAS", "FIRE_SAFETY", "HYDRO_MECHANICS"]
TicketStatus = Literal["draft", "approved", "rejected", "completed"]
ReviewStatus = Literal["pending_review", "acknowledged", "rejected", "ticket_created"]
TelemetryStatusCode = Literal["normal", "failure", "alarm", "unknown"]
AnalyticsRange = Literal["24h", "7d", "30d"]


# --- system / dashboard -------------------------------------------------------------------------
class SystemDto(BaseModel):
    status: Literal["operational", "degraded"]
    updated_at: str


class DashboardChannels(BaseModel):
    total: int
    ml_supported: int
    ml_unsupported: int
    coverage_percent: float


class DashboardPredictions(BaseModel):
    active: int
    critical: int
    high: int
    medium: int
    flash_1_6h: int
    urgent_6_24h: int
    planned_24_48h: int


class DashboardObjects(BaseModel):
    total: int
    affected: int
    critical: int


class DashboardTickets(BaseModel):
    draft: int
    approved: int
    completed_today: int


class DashboardSummaryDto(BaseModel):
    generated_at: str
    model_version: str
    channels: DashboardChannels
    predictions: DashboardPredictions
    objects: DashboardObjects
    tickets: DashboardTickets


# --- objects --------------------------------------------------------------------------------------
class ObjectDto(BaseModel):
    object_id: int
    object_name: str
    parent_object_id: Optional[int]
    subsystem: str


class ObjectStatusSummaryDto(BaseModel):
    object_id: int
    object_name: str
    risk_level: Optional[RiskLevel]
    active_predictions: int
    critical_predictions: int
    high_predictions: int
    ml_supported_channels: int
    channels_total: int
    updated_at: str


class ObjectDetailDto(BaseModel):
    object_id: int
    object_name: str
    parent_object_id: Optional[int]
    object_type: str
    channels_total: int
    ml_supported_channels: int
    risk_level: Optional[RiskLevel]
    active_predictions: int
    critical_predictions: int
    high_predictions: int
    updated_at: str


class TopologySegmentDto(BaseModel):
    segment_id: str
    label: str
    piket_from: float
    piket_to: float
    risk_level: Optional[RiskLevel]
    active_predictions: int
    critical_predictions: int
    high_predictions: int
    max_failure_probability: Optional[float]
    # расширение INTEGRATION_SPEC §3.2 (status сегмента словами) - не ломает фронт
    status: str = "normal"


class ObjectTopologyDto(BaseModel):
    object_id: int
    object_name: str
    piket_min: Optional[float]
    piket_max: Optional[float]
    updated_at: str
    segments: list[TopologySegmentDto]
    # INTEGRATION_SPEC §3.2
    collector_id: int
    collector_name: str
    piket_step_meters: int = 100


# --- predictions ----------------------------------------------------------------------------------
class PredictionDto(BaseModel):
    prediction_id: str
    channel_id: int
    sensor_name: str
    sensor_type: str
    subsystem: str
    tag: str
    object_id: int
    object_name: str
    parent_object_id: Optional[int] = None
    piket: Optional[str]
    piket_value: Optional[float]
    prediction_supported: bool
    model_domain: Optional[ModelDomain]
    model_version: str
    failure_probability: Optional[float]
    risk_level: Optional[RiskLevel]
    maintenance_urgency: Optional[MaintenanceUrgency]
    lead_time_hours: Optional[float]
    health_index_its: Optional[int]
    top_risk_factors: list[str]
    recommendation: Optional[str]
    generated_at: str
    review_status: ReviewStatus
    ticket_id: Optional[str]
    # INTEGRATION_SPEC §2.3 / ARCHITECTURE_AND_ROLES §3.2 (дублирующие имена, чтобы не ломать оба контракта)
    risk_category: Optional[str] = None
    forecast_horizon_hours: int = 24
    primary_cause: Optional[str] = None
    recommended_action: Optional[str] = None


class PredictionsListDto(BaseModel):
    total_predictions: int
    generated_at: str
    items: list[PredictionDto]


# --- telemetry ------------------------------------------------------------------------------------
class TelemetryPointDto(BaseModel):
    timestamp: str
    raw_value: str
    numeric_value: Optional[float]
    status_code: TelemetryStatusCode
    is_alarm: bool
    is_chatter: bool


class TelemetryResponseDto(BaseModel):
    channel_id: int
    sensor_name: str
    sensor_type: str
    value_type: Literal["numeric", "state"]
    unit: Optional[str]
    points_count: int
    telemetry: list[TelemetryPointDto]
    # расширение: сколько записей было до даунсэмплинга
    raw_points_count: int = 0


class TelemetryIngestRecord(BaseModel):
    event_id: int
    channel_id: int
    date: str
    time: str
    alarm: bool | str
    value: str


class TelemetryIngestRequest(BaseModel):
    batch_id: str
    records: list[TelemetryIngestRecord]


class TelemetryIngestResponse(BaseModel):
    processed_count: int
    anomalies_detected: int
    inference_duration_ms: float


# --- tickets --------------------------------------------------------------------------------------
class TicketDto(BaseModel):
    ticket_id: str
    prediction_id: Optional[str]
    object_id: int
    object_name: str
    sensor_name: Optional[str]
    piket: Optional[str]
    title: str
    description: str
    status: TicketStatus
    priority: Optional[RiskLevel]
    assignee: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    # INTEGRATION_SPEC / ARCHITECTURE §3.4
    channel_id: Optional[int] = None
    work_type: Optional[str] = None
    target_completion_hours: Optional[int] = None
    comment: Optional[str] = None
    assigned_brigade: Optional[str] = None
    qr_payload: Optional[str] = None


class CreateTicketRequestDto(BaseModel):
    """Принимает обе формы: фронта (title/description/assignee) и ARCHITECTURE §3.4 (work_type/comment/assigned_brigade)."""

    prediction_id: Optional[str] = None
    object_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    channel_id: Optional[int] = None
    piket: Optional[str] = None
    work_type: Optional[str] = None
    priority: Optional[str] = None
    target_completion_hours: Optional[int] = None
    comment: Optional[str] = None
    assigned_brigade: Optional[str] = None


class UpdateTicketStatusRequestDto(BaseModel):
    status: TicketStatus
    comment: Optional[str] = None


class TicketFeedbackRequestDto(BaseModel):
    prediction_id: str
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=1)


# --- analytics ------------------------------------------------------------------------------------
class AnalyticsRiskTimelinePointDto(BaseModel):
    timestamp: str
    critical: int
    high: int
    medium: int


class AnalyticsUrgencyDistributionDto(BaseModel):
    urgency: MaintenanceUrgency
    count: int


class AnalyticsObjectRiskDto(BaseModel):
    object_id: int
    object_name: str
    risk_level: RiskLevel
    active_predictions: int
    critical_predictions: int
    high_predictions: int
    open_tickets: int


class AnalyticsTicketStatusDto(BaseModel):
    status: TicketStatus
    count: int


class AnalyticsMlDomainCoverageDto(BaseModel):
    domain: ModelDomain
    channels_total: int
    channels_supported: int
    coverage_percent: float


class AnalyticsTotals(BaseModel):
    active_predictions: int
    critical_predictions: int
    high_predictions: int
    open_tickets: int
    completed_tickets: int
    ml_coverage_percent: float


class AnalyticsSummaryDto(BaseModel):
    generated_at: str
    range: AnalyticsRange
    totals: AnalyticsTotals
    risk_timeline: list[AnalyticsRiskTimelinePointDto]
    urgency_distribution: list[AnalyticsUrgencyDistributionDto]
    top_objects: list[AnalyticsObjectRiskDto]
    ticket_status_distribution: list[AnalyticsTicketStatusDto]
    ml_domain_coverage: list[AnalyticsMlDomainCoverageDto]


# --- weather --------------------------------------------------------------------------------------
class WeatherDto(BaseModel):
    city: str = "Moscow"
    temperature_c: float
    relative_humidity: float
    surface_pressure_hpa: float
    precipitation_mm: float
    source: str
