from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DbSession, Role
from app.api.v1.dashboard import dashboard_summary
from app.api.v1.weather import current_weather
from app.db.models import MaintenanceTicket, PredictionRecord, SensorChannel
from app.reports.builders import build_incidents_xlsx, build_summary_pdf
from app.services.aggregates import is_active, load_objects, object_stats

router = APIRouter(tags=["reports"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _incident_rows(db: DbSession) -> list[dict]:
    objects = await load_objects(db)
    channels = {c.id: c for c in (await db.scalars(select(SensorChannel))).all()}
    tickets = {t.prediction_id: t for t in (await db.scalars(select(MaintenanceTicket))).all() if t.prediction_id}
    manual = [t for t in (await db.scalars(select(MaintenanceTicket))).all() if not t.prediction_id]
    preds = [p for p in (await db.scalars(select(PredictionRecord))).all() if is_active(p)]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    preds.sort(key=lambda p: (order.get(p.risk_category, 4), -(p.failure_probability or 0)))
    rows = []
    for p in preds:
        ch = channels.get(p.channel_id)
        t = tickets.get(p.id)
        obj = objects.get(p.object_id) if p.object_id else None
        rows.append({
            "ticket_id": t.id if t else None, "created_at": (t.created_at if t else p.generated_at),
            "object_name": obj.name if obj else "", "piket": ch.piket if ch else None, "channel_id": p.channel_id,
            "sensor_name": ch.sensor_name if ch else "", "sensor_type": ch.sensor_type if ch else "",
            "failure_probability": p.failure_probability, "risk_level": p.risk_category, "primary_cause": p.primary_cause,
            "recommendation": p.recommended_action, "status": t.status if t else None,
            "assignee": t.assigned_brigade if t else None, "prediction_id": p.id,
        })
    for t in manual:
        obj = objects.get(t.object_id)
        rows.append({"ticket_id": t.id, "created_at": t.created_at, "object_name": obj.name if obj else "", "piket": t.piket,
                     "channel_id": t.channel_id, "sensor_name": "", "sensor_type": "", "failure_probability": None,
                     "risk_level": t.priority, "primary_cause": "Ручной наряд", "recommendation": t.description,
                     "status": t.status, "assignee": t.assigned_brigade, "prediction_id": None})
    return rows


@router.get("/reports/incidents.xlsx")
async def incidents_xlsx(db: DbSession, role: Role) -> StreamingResponse:
    """Реестр прогнозов с вероятностями, пикетами и статусами нарядов (INTEGRATION_SPEC §3.6)."""
    data = build_incidents_xlsx(await _incident_rows(db))
    return StreamingResponse(
        iter([data]), media_type=XLSX_MIME,
        headers={"Content-Disposition": "attachment; filename=incidents_report.xlsx"},
    )


@router.get("/reports/summary.pdf")
async def summary_pdf(db: DbSession, role: Role) -> StreamingResponse:
    """Справка для руководства: ключевые метрики, сводка по 16 коллекторам, список критических рисков."""
    dash = await dashboard_summary(db)
    objects = await load_objects(db)
    stats = await object_stats(db, objects)
    collectors = sorted(
        [(objects[oid], s) for oid, s in stats.items() if objects[oid].level == 2],
        key=lambda x: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x[1].risk_level, 4), -x[1].critical, x[0].name),
    )
    rows = await _incident_rows(db)
    critical = [dict(r, ticket_status=r["status"]) for r in rows if r["risk_level"] == "critical" and r["prediction_id"]]
    tickets = (await db.scalars(select(MaintenanceTicket))).all()
    prevented = sum(1 for t in tickets if t.status == "completed")
    supported = dash.channels.ml_supported
    reliability = round(100.0 * (1 - (dash.predictions.critical + 0.5 * dash.predictions.high) / supported), 1) if supported else None
    try:
        weather = (await current_weather()).model_dump()
    except Exception:  # noqa: BLE001
        weather = None
    summary = {
        "generated_at": dash.generated_at, "model_version": dash.model_version,
        "channels": dash.channels.model_dump(), "predictions": dash.predictions.model_dump(),
        "objects": dash.objects.model_dump(), "tickets": dash.tickets.model_dump(),
        "collectors": [{"name": o.name, "risk_level": s.risk_level, "active": s.active, "critical": s.critical, "high": s.high,
                        "channels_total": s.channels_total} for o, s in collectors],
        "critical_items": critical, "prevented_incidents": prevented,
        "reliability_index": f"{reliability}%" if reliability is not None else "—", "weather": weather,
    }
    data = build_summary_pdf(summary)
    return StreamingResponse(iter([data]), media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=summary_report.pdf"})
