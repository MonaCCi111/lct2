from __future__ import annotations

import time
from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import insert, select

from app.api.deps import DbSession, Role
from app.api.errors import bad_request, not_found
from app.core.config import settings
from app.core.timeutil import combine_csv_datetime, db_dt, iso_msk, now_msk, parse_iso
from app.db.models import AuditLog, SensorChannel, TelemetryEvent
from app.schemas.contracts import TelemetryIngestRequest, TelemetryIngestResponse, TelemetryPointDto, TelemetryResponseDto
from app.services import normalize
from app.services.scoring import score_channel

router = APIRouter(tags=["sensors"])

NUMERIC_TYPES = {"Датчик температуры": "°C", "Газовый датчик": "об.%"}
CHATTER_WINDOW_SEC = 120


def downsample(events: list[TelemetryEvent], limit: int) -> list[TelemetryEvent]:
    """INTEGRATION_SPEC §3.1: точки смены статуса включаются всегда, остальное - равномерным шагом."""
    if len(events) <= limit:
        return events
    keep = [False] * len(events)
    keep[0] = keep[-1] = True
    for i in range(1, len(events)):
        if events[i].status_code != events[i - 1].status_code or events[i].is_alarm != events[i - 1].is_alarm:
            keep[i] = True
    changes = sum(keep)
    if changes >= limit:
        # переходов больше лимита - берём равномерно среди самих переходов
        idxs = [i for i, k in enumerate(keep) if k]
        step = len(idxs) / limit
        chosen = {idxs[int(j * step)] for j in range(limit - 1)}
        chosen.add(len(events) - 1)
        return [events[i] for i in sorted(chosen)][:limit]
    rest = [i for i, k in enumerate(keep) if not k]
    budget = limit - changes
    step = len(rest) / budget if budget else 0
    chosen = {i for i, k in enumerate(keep) if k}
    for j in range(budget):
        chosen.add(rest[int(j * step)])
    return [events[i] for i in sorted(chosen)][:limit]


def mark_chatter(events: list[TelemetryEvent]) -> list[bool]:
    """Дребезг: смена статуса, при которой предыдущая смена была менее CHATTER_WINDOW_SEC назад."""
    flags = [False] * len(events)
    last_change_ts = None
    for i in range(1, len(events)):
        changed = events[i].status_code != events[i - 1].status_code or events[i].is_alarm != events[i - 1].is_alarm
        if changed:
            if last_change_ts is not None and (events[i].ts - last_change_ts).total_seconds() <= CHATTER_WINDOW_SEC:
                flags[i] = True
                flags[i - 1] = True
            last_change_ts = events[i].ts
    return flags


@router.get("/sensors/{channel_id}/telemetry", response_model=TelemetryResponseDto)
async def channel_telemetry(
    channel_id: int,
    db: DbSession,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=1000, ge=1),
) -> TelemetryResponseDto:
    ch = await db.get(SensorChannel, channel_id)
    if ch is None:
        raise not_found(f"Датчик с указанным channel_id={channel_id} не найден в реестре")
    limit = min(limit, settings.telemetry_max_points)
    try:
        t_to = parse_iso(date_to) if date_to else now_msk()
        t_from = parse_iso(date_from) if date_from else t_to - timedelta(hours=24)
    except ValueError as exc:
        raise bad_request(f"Некорректная дата: {exc}")
    if t_from >= t_to:
        raise bad_request("date_from должен быть раньше date_to")
    events = (
        await db.scalars(
            select(TelemetryEvent)
            .where(TelemetryEvent.channel_id == channel_id, TelemetryEvent.ts >= db_dt(t_from), TelemetryEvent.ts <= db_dt(t_to))
            .order_by(TelemetryEvent.ts, TelemetryEvent.id)
        )
    ).all()
    raw_count = len(events)
    chatter = dict(zip((e.id for e in events), mark_chatter(events)))
    sampled = downsample(events, limit)
    unit = NUMERIC_TYPES.get(ch.sensor_type)
    numeric_share = sum(1 for e in events if e.numeric_value is not None) / raw_count if raw_count else 0.0
    # Тип ряда - по фактическим данным окна: датчик температуры может отдавать только статусы (Норма/Неисправен)
    value_type = "numeric" if (numeric_share > 0.5 if raw_count else unit is not None) else "state"
    if value_type == "state":
        unit = None
    return TelemetryResponseDto(
        channel_id=ch.id,
        sensor_name=ch.sensor_name,
        sensor_type=ch.sensor_type,
        value_type=value_type,
        unit=unit,
        points_count=len(sampled),
        raw_points_count=raw_count,
        telemetry=[
            TelemetryPointDto(
                timestamp=iso_msk(e.ts) or "",
                raw_value=e.raw_value,
                numeric_value=e.numeric_value,
                status_code=e.status_code,
                is_alarm=e.is_alarm,
                is_chatter=chatter.get(e.id, False),
            )
            for e in sampled
        ],
    )


@router.post("/telemetry/ingest", response_model=TelemetryIngestResponse)
async def ingest_telemetry(body: TelemetryIngestRequest, db: DbSession, role: Role) -> TelemetryIngestResponse:
    """Пакетная загрузка телеметрии (ARCHITECTURE_AND_ROLES §3.5) с нормализацией и пересчётом прогноза
    по затронутым каналам."""
    started = time.perf_counter()
    rows = []
    for r in body.records:
        if r.date.strip() == "дата" or r.date.startswith("1970-01-01"):
            continue
        raw = r.value.strip()
        is_alarm = r.alarm if isinstance(r.alarm, bool) else normalize.parse_bool(str(r.alarm))
        numeric = normalize.parse_numeric(raw)
        try:
            ts = combine_csv_datetime(r.date, r.time)
        except ValueError as exc:
            raise bad_request(f"Некорректная дата/время в записи {r.event_id}: {exc}")
        rows.append(
            {
                "event_id": r.event_id, "channel_id": r.channel_id, "ts": ts, "is_alarm": is_alarm,
                "raw_value": raw, "numeric_value": numeric, "status_code": normalize.status_code(raw, numeric, is_alarm),
            }
        )
    if rows:
        await db.execute(insert(TelemetryEvent), rows)
    anomalies = 0
    touched = {r["channel_id"] for r in rows}
    generated_at = now_msk()
    for cid in touched:
        ch = await db.get(SensorChannel, cid)
        if ch is None:
            continue
        rec = await score_channel(db, ch, generated_at)
        if rec.risk_category in ("high", "critical"):
            anomalies += 1
    db.add(AuditLog(ts=generated_at, role=role, action="telemetry_ingest", entity_type="batch", entity_id=body.batch_id,
                    payload=f'{{"records": {len(rows)}, "channels": {len(touched)}}}'))
    await db.commit()
    return TelemetryIngestResponse(
        processed_count=len(rows), anomalies_detected=anomalies,
        inference_duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
