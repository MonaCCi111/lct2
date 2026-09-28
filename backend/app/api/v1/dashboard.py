from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.core.timeutil import iso_msk, now_msk
from app.db.models import MaintenanceTicket, PredictionRecord, SensorChannel
from app.ml.predictor import predictor
from app.schemas.contracts import (
    DashboardChannels,
    DashboardObjects,
    DashboardPredictions,
    DashboardSummaryDto,
    DashboardTickets,
)
from app.services.aggregates import coverage_percent, is_active, load_objects, object_stats

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummaryDto)
async def dashboard_summary(db: DbSession) -> DashboardSummaryDto:
    now = now_msk()
    channels = (await db.scalars(select(SensorChannel))).all()
    supported = sum(1 for c in channels if predictor.supports(c.sensor_type))
    preds = [p for p in (await db.scalars(select(PredictionRecord))).all() if is_active(p)]
    objects = await load_objects(db)
    stats = await object_stats(db, objects)
    collectors = [s for oid, s in stats.items() if objects[oid].level == 2]

    day_start = now.replace(hour=0, minute=0, second=0)
    tickets = (await db.scalars(select(MaintenanceTicket))).all()
    completed_today = sum(
        1 for t in tickets if t.status == "completed" and t.completed_at is not None and (t.completed_at.replace(tzinfo=now.tzinfo) if t.completed_at.tzinfo is None else t.completed_at) >= day_start
    )
    model_version = preds[0].model_version if preds else predictor.model_version
    return DashboardSummaryDto(
        generated_at=iso_msk(now) or "",
        model_version=model_version,
        channels=DashboardChannels(
            total=len(channels),
            ml_supported=supported,
            ml_unsupported=len(channels) - supported,
            coverage_percent=coverage_percent(supported, len(channels)),
        ),
        predictions=DashboardPredictions(
            active=len(preds),
            critical=sum(1 for p in preds if p.risk_category == "critical"),
            high=sum(1 for p in preds if p.risk_category == "high"),
            medium=sum(1 for p in preds if p.risk_category == "medium"),
            flash_1_6h=sum(1 for p in preds if p.maintenance_urgency == "FLASH_1_6H"),
            urgent_6_24h=sum(1 for p in preds if p.maintenance_urgency == "URGENT_6_24H"),
            planned_24_48h=sum(1 for p in preds if p.maintenance_urgency == "PLANNED_24_48H"),
        ),
        objects=DashboardObjects(
            total=len(collectors),
            affected=sum(1 for s in collectors if s.active),
            critical=sum(1 for s in collectors if s.risk_level == "critical"),
        ),
        tickets=DashboardTickets(
            draft=sum(1 for t in tickets if t.status == "draft"),
            approved=sum(1 for t in tickets if t.status == "approved"),
            completed_today=completed_today,
        ),
    )
