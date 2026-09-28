from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.errors import bad_request
from app.core.timeutil import db_dt, iso_msk, now_msk
from app.db.models import MaintenanceTicket, PredictionRecord, RiskSnapshot, SensorChannel
from app.ml.predictor import MODEL_DOMAIN_BY_SENSOR_TYPE, predictor
from app.schemas.contracts import (
    AnalyticsMlDomainCoverageDto,
    AnalyticsObjectRiskDto,
    AnalyticsRiskTimelinePointDto,
    AnalyticsSummaryDto,
    AnalyticsTicketStatusDto,
    AnalyticsTotals,
    AnalyticsUrgencyDistributionDto,
)
from app.services.aggregates import coverage_percent, is_active, load_objects, object_stats

router = APIRouter(tags=["analytics"])
RANGES = {"24h": 24, "7d": 168, "30d": 720}
DOMAIN_SENSORS: dict[str, set[str]] = {}
for _stype, _dom in MODEL_DOMAIN_BY_SENSOR_TYPE.items():
    DOMAIN_SENSORS.setdefault(_dom, set()).add(_stype)


@router.get("/analytics/summary", response_model=AnalyticsSummaryDto)
async def analytics_summary(db: DbSession, range_: str = Query(default="7d", alias="range")) -> AnalyticsSummaryDto:
    if range_ not in RANGES:
        raise bad_request(f"Недопустимый range '{range_}'. Допустимо: 24h, 7d, 30d")
    now = now_msk()
    since = now - timedelta(hours=RANGES[range_])

    preds = [p for p in (await db.scalars(select(PredictionRecord))).all() if is_active(p)]
    channels = (await db.scalars(select(SensorChannel))).all()
    tickets = (await db.scalars(select(MaintenanceTicket))).all()
    objects = await load_objects(db)
    stats = await object_stats(db, objects)

    supported_total = sum(1 for c in channels if predictor.supports(c.sensor_type))
    open_tickets = sum(1 for t in tickets if t.status in ("draft", "approved"))
    completed_in_range = sum(
        1 for t in tickets
        if t.status == "completed" and t.completed_at is not None
        and (t.completed_at if t.completed_at.tzinfo else t.completed_at.replace(tzinfo=now.tzinfo)) >= since
    )

    snaps = (await db.scalars(select(RiskSnapshot).where(RiskSnapshot.ts >= db_dt(since)).order_by(RiskSnapshot.ts))).all()
    # прореживание до ~24 точек
    if len(snaps) > 24:
        step = len(snaps) / 24
        snaps = [snaps[int(i * step)] for i in range(24)] + [snaps[-1]]
    timeline = [AnalyticsRiskTimelinePointDto(timestamp=iso_msk(s.ts) or "", critical=s.critical, high=s.high, medium=s.medium) for s in snaps]
    # последняя точка = текущие значения
    timeline.append(
        AnalyticsRiskTimelinePointDto(
            timestamp=iso_msk(now) or "",
            critical=sum(1 for p in preds if p.risk_category == "critical"),
            high=sum(1 for p in preds if p.risk_category == "high"),
            medium=sum(1 for p in preds if p.risk_category == "medium"),
        )
    )

    urgency = [
        AnalyticsUrgencyDistributionDto(urgency=u, count=sum(1 for p in preds if p.maintenance_urgency == u))
        for u in ("FLASH_1_6H", "URGENT_6_24H", "PLANNED_24_48H", "NORMAL")
    ]
    collectors = sorted(
        [s for oid, s in stats.items() if objects[oid].level == 2 and s.active],
        key=lambda s: (-s.critical, -s.high, -s.active, objects[s.object_id].name),
    )[:8]
    top_objects = [
        AnalyticsObjectRiskDto(
            object_id=s.object_id, object_name=objects[s.object_id].name, risk_level=s.risk_level or "low",
            active_predictions=s.active, critical_predictions=s.critical, high_predictions=s.high, open_tickets=s.open_tickets,
        )
        for s in collectors
    ]
    ticket_dist = [AnalyticsTicketStatusDto(status=st, count=sum(1 for t in tickets if t.status == st)) for st in ("draft", "approved", "rejected", "completed")]
    domain_cov = []
    for dom, stypes in DOMAIN_SENSORS.items():
        total = sum(1 for c in channels if c.sensor_type in stypes)
        domain_cov.append(AnalyticsMlDomainCoverageDto(domain=dom, channels_total=total, channels_supported=total, coverage_percent=100.0 if total else 0.0))

    return AnalyticsSummaryDto(
        generated_at=iso_msk(now) or "",
        range=range_,
        totals=AnalyticsTotals(
            active_predictions=len(preds),
            critical_predictions=sum(1 for p in preds if p.risk_category == "critical"),
            high_predictions=sum(1 for p in preds if p.risk_category == "high"),
            open_tickets=open_tickets,
            completed_tickets=completed_in_range,
            ml_coverage_percent=coverage_percent(supported_total, len(channels)),
        ),
        risk_timeline=timeline,
        urgency_distribution=urgency,
        top_objects=top_objects,
        ticket_status_distribution=ticket_dist,
        ml_domain_coverage=domain_cov,
    )
