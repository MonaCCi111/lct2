"""API v2 по контракту integration/backend_sanya/api_contract_v1.json (dispatcher_api_v1, base_path /api/v2).

Исторические данные - read-only из HistoricalStore; решения и наряды - отдельные append-only сущности в БД.
Исторические метки времени отдаются буквально, без зоны. Серверные (decided_at, created_at) - с +03:00.
"""
from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Query, Response
import pyarrow as pa
import pyarrow.compute as pc
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, Role, UserId
from app.api.errors import ApiError, bad_request, conflict, forbidden, not_found
from app.core.timeutil import iso_msk, now_msk
from app.db.models import CollectorObject, SensorChannel, V2Decision, V2WorkOrder
from app.v2 import store as st

router = APIRouter(tags=["v2"])

DEFAULT_LIMIT, MAX_LIMIT = 50, 200
_HIST_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$")


# ------------------------------------------------------------------ общие помощники
def unprocessable(message: str) -> ApiError:
    return ApiError(422, "UNSUPPORTED_HISTORICAL_TIME", message)


def hist_time(value: str | None, name: str, end_of_day: bool = False) -> str | None:
    """Историческое время без зоны. Значение с Z/смещением - 422 (зона источника неизвестна)."""
    if value is None:
        return None
    v = value.strip()
    if not _HIST_RE.match(v):
        raise unprocessable(f"{name}: ожидается время источника без зоны YYYY-MM-DDTHH:MM:SS, получено '{value}'")
    v = v.replace(" ", "T")
    if len(v) == 10:
        return v + ("T23:59:59" if end_of_day else "T00:00:00")
    return v if len(v) == 19 else v + ":00"


def page_args(limit: int | None, cursor: str | None) -> tuple[int, int]:
    limit = DEFAULT_LIMIT if limit is None else limit
    if not 1 <= limit <= MAX_LIMIT:
        raise bad_request(f"limit должен быть от 1 до {MAX_LIMIT}")
    if not cursor:
        return limit, 0
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
        assert offset >= 0
    except Exception:  # noqa: BLE001
        raise bad_request("Некорректный cursor")
    return limit, offset


def page(items: list[dict], limit: int, offset: int) -> dict:
    # ponytail: offset-курсор - данные неизменяемы; keyset понадобится для живого потока
    chunk = items[offset : offset + limit]
    nxt = offset + limit
    return {"items": chunk, "next_cursor": base64.urlsafe_b64encode(str(nxt).encode()).decode() if nxt < len(items) else None}


def page_table(table, limit: int, offset: int, *sort_keys: str) -> dict:
    if table is None:
        return {"items": [], "next_cursor": None}
    table = st.sort_by(table, *sort_keys)
    chunk = st.rows(table.slice(offset, limit))
    nxt = offset + limit
    return {"items": chunk, "next_cursor": base64.urlsafe_b64encode(str(nxt).encode()).decode() if nxt < table.num_rows else None}


def s() -> st.HistoricalStore:
    return st.get_store()


# ------------------------------------------------------------------ решения
def decision_dto(d: V2Decision) -> dict:
    return {
        "decision_id": d.decision_id, "draft_id": d.draft_id, "decision": d.decision, "reason": d.reason,
        "author_id": d.author_id, "decided_at": iso_msk(d.decided_at), "idempotency_key": d.idempotency_key,
        "supersedes_decision_id": d.supersedes_decision_id, "work_order_id": d.work_order_id,
    }


async def latest_decisions(db: DbSession, draft_ids: list[str] | None = None) -> dict[str, V2Decision]:
    q = select(V2Decision).order_by(V2Decision.seq)
    if draft_ids is not None:
        if not draft_ids:
            return {}
        q = q.where(V2Decision.draft_id.in_(draft_ids))
    out: dict[str, V2Decision] = {}
    for d in (await db.scalars(q)).all():
        out[d.draft_id] = d  # последняя по порядку записи = действующая
    return out


def draft_visible(row: dict, active: set[str]) -> bool:
    """Инвариант контракта: в прогнозные черновики допускаются только действующие модели."""
    return row.get("basis_kind") != "forecast" or row.get("model_version") in active


def draft_dto(row: dict, dec: V2Decision | None) -> dict:
    out = dict(row)
    out["review_state"] = dec.decision if dec else "pending"
    out["decision"] = decision_dto(dec) if dec else None
    out.setdefault("its_value", None)
    return out


async def get_draft_row(draft_id: str, at: str | None = None) -> dict:
    t = st.where_eq(s().table("drafts"), "draft_id", draft_id)
    found = st.rows(t)
    if not found or not draft_visible(found[0], s().active_models):
        raise not_found(f"Черновик {draft_id} не найден")
    if at is not None and (found[0].get("available_at") or "") > at:
        raise not_found(f"Черновик {draft_id} ещё не доступен на {at}")
    return found[0]


# ------------------------------------------------------------------ meta / types / objects
@router.get("/meta")
async def meta() -> dict:
    data = s()
    fb = data.json.get("feedback") or {}
    return {
        "contract_version": (data.json.get("contract") or {}).get("contract_version", "dispatcher_api_v1"),
        "data_version": (data.json.get("contract") or {}).get("data_version", "ml_handoff_v1"),
        "data_cutoff": data.data_cutoff,
        "source_timezone_known": False,
        "real_feedback_available": bool(fb.get("real_feedback_available", False)),
        "live_ingestion_available": False,
        # расширения
        "data_source": data.data_source,
        "active_forecast_models": sorted(data.active_models),
        "server_time": iso_msk(now_msk()),
    }


@router.get("/model-types")
async def model_types() -> list[dict]:
    return s().json["model_types"].get("types", [])


def _channel_counts() -> dict[int, int]:
    t = s().table("channel_current")
    if t is None or "object_id" not in t.column_names:
        return {}
    counts: dict[int, int] = {}
    for oid in t.column("object_id").to_pylist():
        if oid is not None:
            counts[int(oid)] = counts.get(int(oid), 0) + 1
    return counts


async def _object_dtos(db: DbSession) -> list[dict]:
    objs = (await db.scalars(select(CollectorObject))).all()
    counts = _channel_counts()
    if not counts or s().data_source != "ml_handoff_parquet":  # в режиме фикстур - счётчики по справочнику каналов
        counts = dict((await db.execute(select(SensorChannel.object_id, func.count()).group_by(SensorChannel.object_id))).all())
    children: dict[int, list[int]] = {}
    for o in objs:
        if o.parent_id is not None:
            children.setdefault(o.parent_id, []).append(o.id)

    def total(oid: int) -> int:
        return counts.get(oid, 0) + sum(total(c) for c in children.get(oid, []))

    return sorted(
        ({"object_id": o.id, "object_name": o.name, "kind": o.object_type, "parent_id": o.parent_id,
          "channel_count": total(o.id), "level": o.level} for o in objs),
        key=lambda x: (x["level"], x["object_name"], x["object_id"]),
    )


@router.get("/objects")
async def list_objects(db: DbSession, kind: Optional[str] = None, name: Optional[str] = None,
                       limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    items = await _object_dtos(db)
    if kind:
        items = [o for o in items if o["kind"] == kind]
    if name:
        items = [o for o in items if name.strip().lower() in o["object_name"].lower()]
    return page(items, lim, off)


@router.get("/objects/{object_id}")
async def get_object(object_id: int, db: DbSession) -> dict:
    for o in await _object_dtos(db):
        if o["object_id"] == object_id:
            return o
    raise not_found(f"Объект {object_id} не найден в справочнике")


# ------------------------------------------------------------------ overview
@router.get("/overview")
async def overview(from_: str = Query(alias="from"), to: str = Query(), object_id: Optional[int] = None,
                   sensor_type: Optional[str] = None, at: Optional[str] = None) -> dict:
    lo = hist_time(from_, "from")[:10]
    hi = hist_time(to, "to", end_of_day=True)[:10]
    if at is not None:
        hi = min(hi, hist_time(at, "at")[:10])
    name = "overview_object_type_day" if sensor_type else "overview_object_day"
    t = s().table(name)
    t = st.where_between(t, "activity_date", lo, hi)
    if object_id is not None:
        t = st.where_eq(t, "object_id", object_id)
    if sensor_type:
        t = st.where_eq(t, "sensor_type", sensor_type)
    days: dict[str, dict] = {}
    for r in st.rows(t):
        d = days.setdefault(r["activity_date"], {"activity_date": r["activity_date"]})
        for k, v in r.items():
            if k in ("activity_date", "object_id", "object_name", "sensor_type"):
                continue
            if isinstance(v, (int, float)):
                d[k] = d.get(k, 0) + v
    return {"days": [days[k] for k in sorted(days)], "data_cutoff": s().data_cutoff,
            "object_id": object_id, "sensor_type": sensor_type}


# ------------------------------------------------------------------ channels
def _snapshot_at(channel_ids: list[int], at: str) -> dict[int, dict]:
    t = s().table("observation_snapshots")
    if t is None or not channel_ids:
        return {}
    t = t.filter(pc.is_in(t.column("channel_id"), value_set=pa.array(list(channel_ids), type=t.schema.field("channel_id").type)))
    t = st.where_le(t, "available_at", at)
    latest: dict[int, dict] = {}
    for r in st.rows(st.sort_by(t, "channel_id", "available_at")):
        latest[r["channel_id"]] = r
    return latest


def _channel_as_of(row: dict, snap: dict | None, at: str) -> dict:
    out = dict(row)
    if snap is None:  # на момент at у канала ещё нет снимка
        out.update(available_at=at, last_event_time=None, last_recorded_value=None, last_recorded_is_alarm=None,
                   last_source_ref=None, last_text_status=None, last_text_alarm=None, last_text_source_ref=None,
                   detailed_observation_state="no_snapshot_at_time")
        return out
    out.update(
        available_at=snap.get("available_at"), last_event_time=snap.get("last_event_time"),
        last_recorded_value=snap.get("last_value"), last_recorded_is_alarm=snap.get("last_is_alarm"),
        last_source_ref=snap.get("last_source_ref"), last_text_status=snap.get("last_text_status"),
        last_text_alarm=snap.get("last_text_alarm"), last_text_source_ref=snap.get("last_text_source_ref"),
        detailed_observation_state=snap.get("observation_state"), dictionary_state=snap.get("dictionary_state"),
        its_value=snap.get("its_value"), its_status=snap.get("its_status"), its_reason=snap.get("its_reason"),
    )
    return out


@router.get("/channels")
async def list_channels(object_id: Optional[int] = None, sensor_type: Optional[str] = None,
                        forecast_capability: Optional[str] = None, observation_state: Optional[str] = None,
                        in_catalog: Optional[bool] = None, at: Optional[str] = None,
                        limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    at = hist_time(at, "at")
    t = s().table("channel_current")
    for col, val in (("object_id", object_id), ("sensor_type", sensor_type),
                     ("forecast_capability", forecast_capability), ("in_catalog", in_catalog)):
        if val is not None:
            t = st.where_eq(t, col, val)
    items = st.rows(st.sort_by(t, "channel_id")) if t is not None else []

    def as_of(chunk: list[dict]) -> list[dict]:
        snaps = _snapshot_at([r["channel_id"] for r in chunk], at)
        return [_channel_as_of(r, snaps.get(r["channel_id"]), at) for r in chunk]

    if observation_state is None:  # снимки на момент at - только для каналов текущей страницы
        result = page(items, lim, off)
        if at is not None:
            result["items"] = as_of(result["items"])
        return result
    if at is not None:
        items = as_of(items)
    items = [r for r in items if observation_state in (r.get("coverage_observation_state"), r.get("detailed_observation_state"))]
    return page(items, lim, off)


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: int, at: Optional[str] = None) -> dict:
    at = hist_time(at, "at")
    found = st.rows(st.where_eq(s().table("channel_current"), "channel_id", channel_id))
    if not found:
        raise not_found(f"Канал {channel_id} отсутствует в пакете наблюдения")
    row = found[0]
    history = st.where_eq(s().table("observation_snapshots"), "channel_id", channel_id)
    history = st.where_le(history, "available_at", at)
    hist_rows = st.rows(st.sort_by(history, "snapshot_date")) if history is not None else []
    if at is not None:
        row = _channel_as_of(row, hist_rows[-1] if hist_rows else None, at)
    row["history"] = hist_rows
    return row


# ------------------------------------------------------------------ situations
@router.get("/situations")
async def list_situations(object_id: Optional[int] = None, kind: Optional[str] = None,
                          from_: Optional[str] = Query(default=None, alias="from"), to: Optional[str] = None,
                          at: Optional[str] = None, limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    t = s().table("situations")
    if object_id is not None:
        t = st.where_eq(t, "object_id", object_id)
    if kind:
        t = st.where_eq(t, "situation_kind", kind)
    t = st.where_between(t, "source_first_seen", hist_time(from_, "from"), hist_time(to, "to", end_of_day=True))
    t = st.where_le(t, "available_at", hist_time(at, "at"))
    return page_table(t, lim, off, "available_at", "situation_id")


@router.get("/situations/{situation_id}")
async def get_situation(situation_id: str, at: Optional[str] = None) -> dict:
    at = hist_time(at, "at")
    found = st.rows(st.where_eq(s().table("situations"), "situation_id", situation_id))
    if not found or (at is not None and (found[0].get("available_at") or "") > at):
        raise not_found(f"Ситуация {situation_id} не найдена")
    row = found[0]
    row.setdefault("confirmed_physical_incident", None)
    return row


@router.get("/situations/{situation_id}/evidence")
async def situation_evidence(situation_id: str, at: Optional[str] = None,
                             limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    await get_situation(situation_id, at)
    t = st.where_eq(s().table("situation_evidence"), "situation_id", situation_id)
    t = st.where_le(t, "available_at", hist_time(at, "at"))
    return page_table(t, lim, off, "available_at", "source_time", "event_id")


# ------------------------------------------------------------------ drafts
def _filter_drafts(group_id=None, object_id=None, basis_kind=None, lo=None, hi=None, at=None) -> list[dict]:
    t = s().table("drafts")
    for col, val in (("group_id", group_id), ("object_id", object_id), ("basis_kind", basis_kind)):
        if val is not None:
            t = st.where_eq(t, col, val)
    t = st.where_between(t, "source_obs_time", lo, hi)
    t = st.where_le(t, "available_at", at)
    if t is None:
        return []
    active = s().active_models
    return [r for r in st.rows(st.sort_by(t, "available_at", "draft_id")) if draft_visible(r, active)]


@router.get("/drafts")
async def list_drafts(db: DbSession, group_id: Optional[str] = None, object_id: Optional[int] = None,
                      basis_kind: Optional[Literal["forecast", "observed_status"]] = None,
                      review_state: Optional[Literal["pending", "approved", "rejected"]] = None,
                      from_: Optional[str] = Query(default=None, alias="from"), to: Optional[str] = None,
                      at: Optional[str] = None, limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    rows = _filter_drafts(group_id, object_id, basis_kind, hist_time(from_, "from"),
                          hist_time(to, "to", end_of_day=True), hist_time(at, "at"))
    decs = await latest_decisions(db)
    items = [draft_dto(r, decs.get(r["draft_id"])) for r in rows]
    if review_state:
        items = [d for d in items if d["review_state"] == review_state]
    return page(items, lim, off)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str, db: DbSession, at: Optional[str] = None) -> dict:
    row = await get_draft_row(draft_id, hist_time(at, "at"))
    decs = await latest_decisions(db, [draft_id])
    out = draft_dto(row, decs.get(draft_id))
    feats = st.rows(st.where_eq(s().forecast_features, "draft_id", draft_id))
    if feats:
        out["feature_snapshot"] = {k: v for k, v in feats[0].items() if k not in ("draft_id", "group_id")}
    return out


@router.get("/drafts/{draft_id}/evidence")
async def draft_evidence(draft_id: str, at: Optional[str] = None,
                         limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    at = hist_time(at, "at")
    row = await get_draft_row(draft_id, at)
    if row.get("basis_kind") == "forecast":
        t = st.where_eq(s().draft_evidence, "draft_id", draft_id)
    else:
        t = st.where_eq(s().observed_evidence, "draft_id", draft_id)
        if t is None or t.num_rows == 0:  # наблюдаемый черновик: свидетельства исходной ситуации
            t = st.where_eq(s().table("situation_evidence"), "situation_id", row.get("situation_id"))
    t = st.where_le(t, "available_at", at)
    result = page_table(t, lim, off, "available_at", "event_time", "source_time", "event_id")
    for e in result["items"]:  # обязательные поля Evidence; is_alarm и source_alarm не выводятся друг из друга
        e.setdefault("observed_value", e.get("sensor_value"))
        for k in ("event_id", "numeric_value", "numeric_unit", "source_alarm", "dictionary_state"):
            e.setdefault(k, None)
    return result


# ------------------------------------------------------------------ groups
@router.get("/groups")
async def list_groups(db: DbSession, object_id: Optional[int] = None,
                      from_: Optional[str] = Query(default=None, alias="from"), to: Optional[str] = None,
                      review_state: Optional[Literal["pending", "approved", "rejected"]] = None,
                      at: Optional[str] = None, limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    t = s().table("groups")
    if object_id is not None:
        t = st.where_eq(t, "object_id", object_id)
    t = st.where_between(t, "source_first_obs_time", hist_time(from_, "from"), hist_time(to, "to", end_of_day=True))
    t = st.where_le(t, "available_at", hist_time(at, "at"))
    groups = st.rows(st.sort_by(t, "available_at", "group_id")) if t is not None else []
    if review_state:
        decs = await latest_decisions(db)
        states: dict[str, set[str]] = {}
        for d in _filter_drafts():
            states.setdefault(d["group_id"], set()).add(decs[d["draft_id"]].decision if d["draft_id"] in decs else "pending")
        groups = [g for g in groups if review_state in states.get(g["group_id"], set())]
    return page(groups, lim, off)


@router.get("/groups/{group_id}")
async def get_group(group_id: str, db: DbSession, at: Optional[str] = None) -> dict:
    at = hist_time(at, "at")
    found = st.rows(st.where_eq(s().table("groups"), "group_id", group_id))
    if not found or (at is not None and (found[0].get("available_at") or "") > at):
        raise not_found(f"Группа {group_id} не найдена")
    drafts = _filter_drafts(group_id=group_id, at=at)
    decs = await latest_decisions(db, [d["draft_id"] for d in drafts])
    return {**found[0], "drafts": [draft_dto(d, decs.get(d["draft_id"])) for d in drafts]}


# ------------------------------------------------------------------ decisions
class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str
    idempotency_key: str


class DecisionCorrectionRequest(DecisionRequest):
    expected_decision_id: str


def _require_text(value: str, name: str) -> str:
    v = (value or "").strip()
    if not v:
        raise bad_request(f"Поле {name} обязательно и не может быть пустым")
    return v


async def _by_key(db: DbSession, key: str, draft_id: str) -> V2Decision | None:
    prev = await db.scalar(select(V2Decision).where(V2Decision.idempotency_key == key))
    if prev is not None and prev.draft_id != draft_id:
        raise conflict("idempotency_key уже использован для другого черновика", "IDEMPOTENCY_KEY_REUSED")
    return prev


async def _append_decision(db: DbSession, draft_id: str, body: DecisionRequest, user: str, role: str,
                           supersedes: str | None) -> V2Decision:
    d = V2Decision(decision_id=f"dec-{uuid.uuid4().hex[:12]}", draft_id=draft_id, decision=body.decision,
                   reason=_require_text(body.reason, "reason"), author_id=user, author_role=role, decided_at=now_msk(),
                   idempotency_key=body.idempotency_key.strip(), supersedes_decision_id=supersedes)
    db.add(d)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("Конкурентная запись решения, повторите запрос", "STALE_REVISION")
    return d


@router.post("/drafts/{draft_id}/decisions", status_code=201)
async def create_decision(draft_id: str, body: DecisionRequest, db: DbSession, role: Role, user: UserId, response: Response) -> dict:
    _require_text(body.reason, "reason")
    key = _require_text(body.idempotency_key, "idempotency_key")
    await get_draft_row(draft_id)
    prev = await _by_key(db, key, draft_id)
    if prev is not None:
        response.status_code = 200
        return decision_dto(prev)
    current = (await latest_decisions(db, [draft_id])).get(draft_id)
    if current is not None:
        raise conflict(f"По черновику уже принято решение {current.decision}; изменение - только через decision-corrections",
                       "DECISION_CONFLICT", {"current_decision_id": current.decision_id, "decision": current.decision})
    return decision_dto(await _append_decision(db, draft_id, body, user, role, None))


@router.get("/drafts/{draft_id}/decisions")
async def list_decisions(draft_id: str, db: DbSession) -> list[dict]:
    await get_draft_row(draft_id)
    return [decision_dto(d) for d in (await db.scalars(select(V2Decision).where(V2Decision.draft_id == draft_id).order_by(V2Decision.seq))).all()]


@router.post("/drafts/{draft_id}/decision-corrections", status_code=201)
async def correct_decision(draft_id: str, body: DecisionCorrectionRequest, db: DbSession, role: Role, user: UserId, response: Response) -> dict:
    if role != "supervisor":
        raise forbidden("Исправление решения доступно только роли supervisor")
    _require_text(body.reason, "reason")
    key = _require_text(body.idempotency_key, "idempotency_key")
    await get_draft_row(draft_id)
    prev = await _by_key(db, key, draft_id)
    if prev is not None:
        response.status_code = 200
        return decision_dto(prev)
    current = (await latest_decisions(db, [draft_id])).get(draft_id)
    if current is None or current.decision_id != body.expected_decision_id:
        raise conflict("expected_decision_id не совпадает с действующим решением", "STALE_REVISION",
                       {"current_decision_id": current.decision_id if current else None})
    if current.work_order_id and body.decision == "rejected":
        raise conflict(f"По решению уже создан наряд {current.work_order_id}", "WORK_ORDER_EXISTS")
    new = await _append_decision(db, draft_id, body, user, role, current.decision_id)
    if current.work_order_id:  # связь с нарядом переносится на новое действующее решение
        new.work_order_id = current.work_order_id
        await db.commit()
    return decision_dto(new)


# ------------------------------------------------------------------ work orders
class WorkOrderRequest(BaseModel):
    draft_id: str
    work_type: str
    description: str
    idempotency_key: str
    assignee_id: Optional[str] = None
    due_at: Optional[str] = None


def work_order_dto(w: V2WorkOrder) -> dict:
    return {
        "work_order_id": w.work_order_id, "draft_id": w.draft_id, "object_id": w.object_id, "status": w.status,
        "work_type": w.work_type, "description": w.description, "created_at": iso_msk(w.created_at),
        "created_by": w.created_by, "external_work_order_id": w.external_work_order_id,
        "assignee_id": w.assignee_id, "due_at": w.due_at,
    }


@router.get("/work-orders")
async def list_work_orders(db: DbSession, draft_id: Optional[str] = None, object_id: Optional[int] = None,
                           status: Optional[str] = None, limit: Optional[int] = None, cursor: Optional[str] = None) -> dict:
    lim, off = page_args(limit, cursor)
    q = select(V2WorkOrder).order_by(V2WorkOrder.created_at, V2WorkOrder.work_order_id)
    if draft_id:
        q = q.where(V2WorkOrder.draft_id == draft_id)
    if object_id is not None:
        q = q.where(V2WorkOrder.object_id == object_id)
    if status:
        q = q.where(V2WorkOrder.status == status)
    return page([work_order_dto(w) for w in (await db.scalars(q)).all()], lim, off)


@router.post("/work-orders", status_code=201)
async def create_work_order(body: WorkOrderRequest, db: DbSession, role: Role, user: UserId, response: Response) -> dict:
    key = _require_text(body.idempotency_key, "idempotency_key")
    work_type = _require_text(body.work_type, "work_type")
    description = _require_text(body.description, "description")
    if body.due_at is not None and not re.search(r"(Z|[+-]\d{2}:\d{2})$", body.due_at.strip()):
        raise bad_request("due_at должен содержать смещение часового пояса или Z")
    prev = await db.scalar(select(V2WorkOrder).where(V2WorkOrder.idempotency_key == key))
    if prev is not None:
        if prev.draft_id != body.draft_id:
            raise conflict("idempotency_key уже использован для другого черновика", "IDEMPOTENCY_KEY_REUSED")
        response.status_code = 200
        return work_order_dto(prev)
    row = await get_draft_row(body.draft_id)
    current = (await latest_decisions(db, [body.draft_id])).get(body.draft_id)
    if current is None or current.decision != "approved":
        raise conflict("Наряд создаётся только по черновику с утверждённым решением", "DRAFT_NOT_APPROVED",
                       {"review_state": current.decision if current else "pending"})
    if current.work_order_id:
        raise conflict(f"По черновику уже создан наряд {current.work_order_id}", "WORK_ORDER_EXISTS",
                       {"work_order_id": current.work_order_id})
    n = await db.scalar(select(func.count()).select_from(V2WorkOrder))
    w = V2WorkOrder(work_order_id=f"WO2-{now_msk().year}-{(n or 0) + 1:05d}", draft_id=body.draft_id,
                    decision_id=current.decision_id, object_id=int(row["object_id"]), status="created",
                    work_type=work_type, description=description, created_at=now_msk(), created_by=user,
                    idempotency_key=key, assignee_id=body.assignee_id, due_at=body.due_at)
    db.add(w)
    current.work_order_id = w.work_order_id
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("По черновику уже создан наряд", "WORK_ORDER_EXISTS")
    return work_order_dto(w)


@router.get("/work-orders/{work_order_id}")
async def get_work_order(work_order_id: str, db: DbSession) -> dict:
    w = await db.scalar(select(V2WorkOrder).where(V2WorkOrder.work_order_id == work_order_id))
    if w is None:
        raise not_found(f"Наряд {work_order_id} не найден")
    return work_order_dto(w)


# ------------------------------------------------------------------ charts / fire / replays
@router.get("/charts/cases")
async def case_chart(draft_id: Optional[str] = None, situation_id: Optional[str] = None, at: Optional[str] = None) -> dict:
    if bool(draft_id) == bool(situation_id):
        raise bad_request("Укажите ровно один параметр: draft_id или situation_id")
    case_id = draft_id or situation_id
    at = hist_time(at, "at")
    examples = st.where_eq(s().table("chart_examples"), "case_id", case_id)
    if examples is not None and examples.num_rows:
        view_at = at or st.rows(examples.slice(0, 1))[0].get("view_at")
        pts = st.rows(st.sort_by(st.where_le(examples, "event_time", view_at), "event_time"))
        return {"case_id": case_id, "view_at": view_at, "points": pts, "source": "chart_examples",
                "limitations": "fixture_example_case;numeric_and_text_series_separate;gaps_not_interpolated"}
    if draft_id:
        row = await get_draft_row(draft_id, at)
        evidence = (await draft_evidence(draft_id, at=at, limit=MAX_LIMIT, cursor=None))["items"]
        view_at = at or row.get("available_at")
    else:
        sit = await get_situation(situation_id, at)
        t = st.where_le(st.where_eq(s().table("situation_evidence"), "situation_id", situation_id), "available_at", at)
        evidence = st.rows(st.sort_by(t, "source_time")) if t is not None else []
        view_at = at or sit.get("available_at")
    points, prev_t = [], None
    for e in evidence:
        t = e.get("event_time") or e.get("source_time")
        numeric = e.get("numeric_value")
        gap = None
        if prev_t and t:
            gap = round((datetime.fromisoformat(t) - datetime.fromisoformat(prev_t)).total_seconds() / 3600, 3)
        points.append({"event_time": t, "channel_id": e.get("channel_id"), "event_id": e.get("event_id"),
                       "value_kind": "numeric" if numeric is not None else "text",
                       "numeric_value": numeric, "text_value": None if numeric is not None else e.get("observed_value"),
                       "numeric_unit": e.get("numeric_unit"), "source_alarm": e.get("source_alarm", e.get("is_alarm")),
                       "gap_hours": gap, "available_at": e.get("available_at"), "source_ref": e.get("source_ref")})
        prev_t = t or prev_t
    return {"case_id": case_id, "view_at": view_at, "points": points, "source": "evidence",
            "limitations": "saved_evidence_only;numeric_and_text_series_separate;gaps_not_interpolated"}


@router.get("/fire-history")
async def fire_history() -> dict:
    fh = dict(s().json.get("fire_history") or {})
    fh.setdefault("source_status", "NO_CONFIRMED_FIRE_SOURCE")
    fh.setdefault("real_fire_count", None)
    fh.setdefault("smoke_signal_statistics_are_fires", False)
    return fh


@router.get("/replays")
async def list_replays() -> list[dict]:
    data = s()
    return [dict(sc, events_available=sc["id"] in data.replay_timelines) for sc in data.json["replays"]]


@router.get("/replays/{scenario_id}/events")
async def replay_events(scenario_id: str, after_seq: int = Query(default=0, ge=0), limit: Optional[int] = None) -> dict:
    lim, _ = page_args(limit, None)
    data = s()
    if scenario_id not in {sc["id"] for sc in data.json["replays"]}:
        raise not_found(f"Сценарий {scenario_id} не найден")
    t = data.replay_timelines.get(scenario_id)
    if t is None:
        return {"items": [], "next_cursor": None}
    t = st.sort_by(t.filter(pc.greater(t.column("seq"), after_seq)), "seq")
    items = st.rows(t.slice(0, lim))
    return {"items": items, "next_cursor": str(items[-1]["seq"]) if t.num_rows > lim else None}
