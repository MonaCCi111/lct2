from __future__ import annotations

import json

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, Role, UserId
from app.api.errors import bad_request, conflict, not_found, unprocessable
from app.core.timeutil import now_msk
from app.db.models import AuditLog, CollectorObject, MaintenanceTicket, PredictionRecord, SensorChannel
from app.schemas.contracts import CreateTicketRequestDto, TicketDto, TicketFeedbackRequestDto, UpdateTicketStatusRequestDto
from app.services.aggregates import load_objects
from app.services.serializers import ticket_dto

router = APIRouter(tags=["tickets"])

TRANSITIONS = {"draft": {"approved", "rejected"}, "approved": {"completed"}, "rejected": set(), "completed": set()}
STATUSES = ("draft", "approved", "rejected", "completed")


async def _next_ticket_id(db: DbSession) -> str:
    year = now_msk().year
    n = await db.scalar(select(func.count()).select_from(MaintenanceTicket))
    return f"WO-{year}-{(n or 0) + 1:04d}"


async def _dto(db: DbSession, t: MaintenanceTicket) -> TicketDto:
    obj = await db.get(CollectorObject, t.object_id)
    ch = await db.get(SensorChannel, t.channel_id) if t.channel_id else None
    return ticket_dto(t, obj, ch)


def _audit(db: DbSession, role: str, user: str, action: str, t: MaintenanceTicket, extra: dict | None = None) -> None:
    payload = {"user": user, "status": t.status, **(extra or {})}
    db.add(AuditLog(ts=now_msk(), role=role, action=action, entity_type="ticket", entity_id=t.id,
                    payload=json.dumps(payload, ensure_ascii=False)))


@router.get("/tickets", response_model=list[TicketDto])
async def list_tickets(
    db: DbSession,
    status: str | None = None,
    search: str | None = None,
    prediction_id: str | None = None,
    object_id: int | None = None,
) -> list[TicketDto]:
    if status is not None and status not in STATUSES:
        raise bad_request(f"Недопустимый status '{status}'")
    q = select(MaintenanceTicket)
    if status:
        q = q.where(MaintenanceTicket.status == status)
    if prediction_id:
        q = q.where(MaintenanceTicket.prediction_id == prediction_id)
    if object_id is not None:
        q = q.where(MaintenanceTicket.object_id == object_id)
    q = q.order_by(MaintenanceTicket.updated_at.desc(), MaintenanceTicket.id)
    rows = (await db.scalars(q)).all()
    objects = await load_objects(db)
    ch_ids = {t.channel_id for t in rows if t.channel_id}
    channels = {c.id: c for c in (await db.scalars(select(SensorChannel).where(SensorChannel.id.in_(ch_ids)))).all()} if ch_ids else {}
    out = [ticket_dto(t, objects.get(t.object_id), channels.get(t.channel_id) if t.channel_id else None) for t in rows]
    if search:
        s = search.strip().lower()
        out = [
            d for d in out
            if s in d.ticket_id.lower() or s in d.title.lower() or s in d.object_name.lower()
            or (d.prediction_id and s in d.prediction_id.lower()) or (d.assignee and s in d.assignee.lower())
        ]
    return out


@router.get("/tickets/{ticket_id}", response_model=TicketDto)
async def ticket_detail(ticket_id: str, db: DbSession) -> TicketDto:
    t = await db.get(MaintenanceTicket, ticket_id)
    if t is None:
        raise not_found(f"Наряд {ticket_id} не найден")
    return await _dto(db, t)


@router.post("/tickets", response_model=TicketDto, status_code=201)
async def create_ticket(body: CreateTicketRequestDto, db: DbSession, role: Role, user: UserId, response: Response) -> TicketDto:
    """Создание наряда на превентивное ТО. Контекст (объект, канал, пикет, приоритет) берётся из прогноза, а не
    из тела запроса; для ручного наряда (prediction_id=null) обязателен object_id."""
    pred: PredictionRecord | None = None
    ch: SensorChannel | None = None
    if body.prediction_id:
        pred = await db.get(PredictionRecord, body.prediction_id)
        if pred is None:
            raise not_found(f"Прогноз {body.prediction_id} не найден")
        ch = await db.get(SensorChannel, pred.channel_id)
        existing = await db.scalar(select(MaintenanceTicket).where(MaintenanceTicket.prediction_id == pred.id))
        if existing is not None:
            raise conflict(f"Для прогноза уже создан наряд {existing.id}.", "TICKET_ALREADY_EXISTS", {"ticket_id": existing.id})
        object_id = pred.object_id or body.object_id
    else:
        object_id = body.object_id
    if object_id is None:
        raise unprocessable("Для ручного наряда обязателен object_id")
    obj = await db.get(CollectorObject, object_id)
    if obj is None:
        raise not_found(f"Объект {object_id} не найден в справочнике")
    if body.channel_id and ch is None:
        ch = await db.get(SensorChannel, body.channel_id)

    title = (body.title or body.work_type or (f"Проверка: {ch.sensor_name}" if ch else "Наряд на обслуживание")).strip()
    description = (body.description or body.comment or (pred.recommended_action if pred else "") or "").strip()
    if not description and pred is not None:
        description = pred.recommended_action or ""
    if not (3 <= len(title) <= 120):
        raise unprocessable("Заголовок наряда должен быть от 3 до 120 символов")
    if not (10 <= len(description) <= 2000):
        raise unprocessable("Описание наряда должно быть от 10 до 2000 символов")

    now = now_msk()
    t = MaintenanceTicket(
        id=await _next_ticket_id(db),
        prediction_id=pred.id if pred else None,
        channel_id=ch.id if ch else None,
        object_id=object_id,
        piket=(ch.piket if ch else None) or body.piket,
        title=title,
        description=description,
        work_type=body.work_type or (body.title if body.title else None),
        priority=(pred.risk_category if pred and pred.prediction_supported else None) or (body.priority if body.priority in ("low", "medium", "high", "critical") else None),
        target_hours=body.target_completion_hours or (int(pred.lead_time_hours) if pred and pred.lead_time_hours else None),
        status="draft",
        comment=body.comment,
        assigned_brigade=body.assignee or body.assigned_brigade,
        created_by_role=role,
        created_at=now,
        updated_at=now,
    )
    db.add(t)
    _audit(db, role, user, "ticket_create", t, {"prediction_id": t.prediction_id})
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("Для прогноза уже создан наряд.", "TICKET_ALREADY_EXISTS")
    response.headers["Location"] = f"/api/v1/tickets/{t.id}"
    return await _dto(db, t)


@router.patch("/tickets/{ticket_id}/status", response_model=TicketDto)
async def update_ticket_status(ticket_id: str, body: UpdateTicketStatusRequestDto, db: DbSession, role: Role, user: UserId) -> TicketDto:
    t = await db.get(MaintenanceTicket, ticket_id, with_for_update=True)
    if t is None:
        raise not_found(f"Наряд {ticket_id} не найден")
    if body.status not in TRANSITIONS.get(t.status, set()):
        raise conflict(f"Переход {t.status} -> {body.status} недопустим", "INVALID_TRANSITION", {"current": t.status})
    if body.status == "rejected" and not (body.comment or "").strip():
        raise bad_request("При отклонении наряда обязателен комментарий с причиной (comment)")
    now = now_msk()
    prev = t.status
    t.status = body.status
    t.updated_at = now
    if body.comment:
        t.comment = body.comment.strip()
    if body.status == "completed":
        t.completed_at = now
    _audit(db, role, user, "ticket_status", t, {"from": prev, "to": body.status, "comment": body.comment})
    await db.commit()
    return await _dto(db, t)


@router.post("/tickets/feedback", response_model=TicketDto)
async def ticket_feedback(body: TicketFeedbackRequestDto, db: DbSession, role: Role, user: UserId) -> TicketDto:
    """ARCHITECTURE_AND_ROLES §2.4: подтверждение/отклонение рекомендации по прогнозу с причиной.
    approved -> наряд создаётся (если нет) и утверждается; rejected -> наряд-черновик отклоняется."""
    pred = await db.get(PredictionRecord, body.prediction_id)
    if pred is None:
        raise not_found(f"Прогноз {body.prediction_id} не найден")
    t = await db.scalar(select(MaintenanceTicket).where(MaintenanceTicket.prediction_id == pred.id))
    if t is None:
        ch = await db.get(SensorChannel, pred.channel_id)
        now = now_msk()
        t = MaintenanceTicket(
            id=await _next_ticket_id(db), prediction_id=pred.id, channel_id=pred.channel_id, object_id=pred.object_id or 0,
            piket=ch.piket if ch else None, title=f"Проверка: {ch.sensor_name}" if ch else "Наряд по прогнозу",
            description=pred.recommended_action or "Проверка по рекомендации предиктивной модели",
            work_type=pred.recommended_action, priority=pred.risk_category, status="draft",
            target_hours=int(pred.lead_time_hours) if pred.lead_time_hours else None,
            created_by_role=role, created_at=now, updated_at=now,
        )
        db.add(t)
    if body.decision not in TRANSITIONS.get(t.status, set()):
        raise conflict(f"Переход {t.status} -> {body.decision} недопустим", "INVALID_TRANSITION", {"current": t.status})
    t.status = body.decision
    t.comment = body.reason
    t.updated_at = now_msk()
    pred.review_status = "acknowledged" if body.decision == "approved" else "rejected"
    _audit(db, role, user, "ticket_feedback", t, {"decision": body.decision, "reason": body.reason})
    await db.commit()
    return await _dto(db, t)
