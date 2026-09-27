from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.errors import bad_request, not_found
from app.core.timeutil import iso_msk, now_msk
from app.db.models import MaintenanceTicket, PredictionRecord, SensorChannel
from app.schemas.contracts import PredictionDto, PredictionsListDto
from app.services.aggregates import RISK_ORDER, is_active, load_objects
from app.services.serializers import prediction_dto

router = APIRouter(tags=["predictions"])
URGENCY_ORDER = {"FLASH_1_6H": 0, "URGENT_6_24H": 1, "PLANNED_24_48H": 2, "NORMAL": 3, None: 4}


async def _collect(
    db: DbSession,
    object_id: int | None,
    risk_level: str | None,
    subsystem: str | None,
    min_probability: float | None,
    operational: bool,
) -> list[PredictionDto]:
    objects = await load_objects(db)
    preds = (await db.scalars(select(PredictionRecord))).all()
    channels = {c.id: c for c in (await db.scalars(select(SensorChannel))).all()}
    tickets = {t.prediction_id: t for t in (await db.scalars(select(MaintenanceTicket))).all() if t.prediction_id}
    out: list[PredictionDto] = []
    for p in preds:
        ch = channels.get(p.channel_id)
        if ch is None:
            continue
        obj = objects.get(p.object_id) if p.object_id else None
        if object_id is not None:
            if obj is None:
                continue
            # фильтр по коллектору или по любому предку
            chain, cur = set(), obj
            while cur is not None:
                chain.add(cur.id)
                cur = objects.get(cur.parent_id) if cur.parent_id else None
            if object_id not in chain:
                continue
        if operational and (not is_active(p) or p.risk_category == "low"):
            continue
        if risk_level and p.risk_category != risk_level:
            continue
        if subsystem and ch.subsystem != subsystem:
            continue
        if min_probability is not None and (p.failure_probability is None or p.failure_probability < min_probability):
            continue
        out.append(prediction_dto(p, ch, obj, tickets.get(p.id)))
    out.sort(
        key=lambda d: (
            URGENCY_ORDER.get(d.maintenance_urgency, 4),
            -(d.failure_probability if d.failure_probability is not None else -1),
            d.prediction_id,
        )
    )
    return out


@router.get("/predictions", response_model=list[PredictionDto])
async def list_predictions(
    db: DbSession,
    view: str | None = Query(default=None, description="operational - только поддерживаемые и не low"),
    object_id: int | None = None,
    risk_level: str | None = None,
    subsystem: str | None = None,
    min_probability: float | None = Query(default=None, ge=0, le=1),
) -> list[PredictionDto]:
    if risk_level is not None and risk_level not in RISK_ORDER:
        raise bad_request(f"Недопустимый risk_level '{risk_level}'")
    if view not in (None, "operational", "all"):
        raise bad_request(f"Недопустимый view '{view}'")
    return await _collect(db, object_id, risk_level, subsystem, min_probability, operational=view == "operational")


@router.get("/predictions/sensors", response_model=PredictionsListDto)
async def list_predictions_spec(
    db: DbSession,
    object_id: int | None = None,
    subsystem: str | None = None,
    min_probability: float = Query(default=0.5, ge=0, le=1),
    horizon_hours: int = Query(default=24, ge=1),
) -> PredictionsListDto:
    """Реестр прогнозируемых отказов по ARCHITECTURE_AND_ROLES §3.2 / INTEGRATION_SPEC (обёртка с total_predictions)."""
    items = await _collect(db, object_id, None, subsystem, min_probability, operational=False)
    items = [i for i in items if i.prediction_supported]
    return PredictionsListDto(total_predictions=len(items), generated_at=iso_msk(now_msk()) or "", items=items)


@router.get("/predictions/{prediction_id}", response_model=PredictionDto)
async def prediction_detail(prediction_id: str, db: DbSession) -> PredictionDto:
    p = await db.get(PredictionRecord, prediction_id)
    if p is None:
        raise not_found(f"Прогноз {prediction_id} не найден")
    ch = await db.get(SensorChannel, p.channel_id)
    if ch is None:
        raise not_found(f"Канал {p.channel_id} прогноза не найден в реестре")
    objects = await load_objects(db)
    ticket = await db.scalar(select(MaintenanceTicket).where(MaintenanceTicket.prediction_id == p.id))
    return prediction_dto(p, ch, objects.get(p.object_id) if p.object_id else None, ticket)
