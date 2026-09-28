from __future__ import annotations

import json

from app.core.timeutil import iso_msk
from app.db.models import CollectorObject, MaintenanceTicket, PredictionRecord, SensorChannel
from app.schemas.contracts import PredictionDto, TicketDto


def prediction_dto(
    p: PredictionRecord,
    ch: SensorChannel,
    obj: CollectorObject | None,
    ticket: MaintenanceTicket | None,
) -> PredictionDto:
    review = p.review_status
    if ticket is not None:
        review = "ticket_created"
    return PredictionDto(
        prediction_id=p.id,
        channel_id=ch.id,
        sensor_name=ch.sensor_name,
        sensor_type=ch.sensor_type,
        subsystem=ch.subsystem,
        tag=ch.tag,
        object_id=obj.id if obj else (ch.object_id or 0),
        object_name=obj.name if obj else "Объект не определён",
        parent_object_id=obj.parent_id if obj else None,
        piket=ch.piket,
        piket_value=ch.piket_value,
        prediction_supported=p.prediction_supported,
        model_domain=p.model_domain,
        model_version=p.model_version,
        failure_probability=p.failure_probability,
        risk_level=p.risk_category,
        maintenance_urgency=p.maintenance_urgency,
        lead_time_hours=p.lead_time_hours,
        health_index_its=p.health_index_its,
        top_risk_factors=json.loads(p.top_risk_factors or "[]"),
        recommendation=p.recommended_action,
        generated_at=iso_msk(p.generated_at) or "",
        review_status=review,
        ticket_id=ticket.id if ticket else None,
        risk_category=p.risk_category,
        forecast_horizon_hours=p.forecast_horizon_hours or 24,
        primary_cause=p.primary_cause,
        recommended_action=p.recommended_action,
    )


def ticket_dto(t: MaintenanceTicket, obj: CollectorObject | None, ch: SensorChannel | None) -> TicketDto:
    return TicketDto(
        ticket_id=t.id,
        prediction_id=t.prediction_id,
        object_id=t.object_id,
        object_name=obj.name if obj else "Объект не определён",
        sensor_name=ch.sensor_name if ch else None,
        piket=t.piket,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        assignee=t.assigned_brigade,
        created_at=iso_msk(t.created_at) or "",
        updated_at=iso_msk(t.updated_at) or "",
        completed_at=iso_msk(t.completed_at),
        channel_id=t.channel_id,
        work_type=t.work_type,
        target_completion_hours=t.target_hours,
        comment=t.comment,
        assigned_brigade=t.assigned_brigade,
        qr_payload=f"https://moscollector.internal/tickets/{t.id}",
    )
