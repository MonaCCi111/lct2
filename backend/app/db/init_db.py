"""Сидинг справочников и среза телеметрии при старте (BACKEND_SANYA_GUIDE §3).

Идемпотентно: каждая таблица наполняется только если пуста.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from datetime import timedelta

from app.core.timeutil import combine_csv_datetime, now_msk
from app.db.models import CollectorObject, SensorChannel, StateDictionaryRow, TelemetryEvent
from app.services import normalize

log = logging.getLogger("seed")


def _find(path_dir: Path, name: str) -> Path | None:
    for candidate in (path_dir / name, path_dir / "catalog" / name, path_dir / "representative_slice" / name):
        if candidate.exists():
            return candidate
    return None


async def _is_empty(session: AsyncSession, model) -> bool:
    count = await session.scalar(select(func.count()).select_from(model))
    return (count or 0) == 0


async def seed_objects(session: AsyncSession) -> int:
    if not await _is_empty(session, CollectorObject):
        return 0
    path = _find(settings.data_dir, settings.objects_csv)
    if path is None:
        log.warning("objects csv not found in %s", settings.data_dir)
        return 0
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = r["диспетчерское_название_объекта"].strip()
            pk_from, pk_to = normalize.parse_piket_range(name)
            rows.append(
                CollectorObject(
                    id=int(r["ид_объект"]),
                    name=name,
                    level=int(r["иерархия_уровень"]),
                    parent_id=int(r["родитель"]) if r.get("родитель") else None,
                    object_type=r["вид_объекта"].strip(),
                    piket_from=pk_from,
                    piket_to=pk_to,
                )
            )
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def seed_channels(session: AsyncSession) -> int:
    """Справочник каналов. Колонка ид_объект (объект 3 уровня) есть в версии справочника из пакета ML."""
    if not await _is_empty(session, SensorChannel):
        return 0
    path = _find(settings.data_dir, settings.channels_csv)
    if path is None:
        log.warning("channels csv not found in %s", settings.data_dir)
        return 0
    known_objects = set((await session.scalars(select(CollectorObject.id))).all())
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = r["название_датчика"].strip()
            tag = r["тег_инженерной_системы"].strip()
            piket, piket_value = normalize.parse_piket(name)
            raw_obj = (r.get("ид_объект") or "").strip()
            object_id = int(raw_obj) if raw_obj.isdigit() and int(raw_obj) in known_objects else None
            rows.append(
                SensorChannel(
                    id=int(r["ид_канала_данных"]),
                    subsystem=r["тип_инж_системы"].strip(),
                    sensor_type=r["тип_датчика"].strip(),
                    tag=tag,
                    sensor_name=name,
                    tag_root=normalize.tag_root(tag),
                    piket=piket,
                    piket_value=piket_value,
                    object_id=object_id,
                    object_map_source="catalog" if object_id else None,
                )
            )
    session.add_all(rows)
    await session.commit()
    log.info("channels seeded: %d (with object: %d)", len(rows), sum(1 for c in rows if c.object_id))
    return len(rows)


async def seed_state_dictionary(session: AsyncSession) -> int:
    if not await _is_empty(session, StateDictionaryRow):
        return 0
    path = _find(settings.data_dir, settings.states_csv)
    if path is None:
        return 0
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            alarm_raw = (r.get("тревожное") or "").strip()
            rows.append(
                StateDictionaryRow(
                    sensor_type=(r.get("тип_датчика") or "").strip(),
                    state_text=(r.get("название_состояния") or "").strip(),
                    is_alarm=normalize.parse_bool(alarm_raw) if alarm_raw else None,
                    state_set=(r.get("ид_набор_состояний") or "").strip() or None,
                    raw=json.dumps(r, ensure_ascii=False),
                )
            )
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def seed_telemetry(session: AsyncSession) -> int:
    if not await _is_empty(session, TelemetryEvent):
        return 0
    path = _find(settings.data_dir, settings.telemetry_csv)
    if path is None:
        log.warning("telemetry sample not found in %s", settings.data_dir)
        return 0
    batch: list[dict] = []
    total = 0

    async def flush() -> None:
        nonlocal batch, total
        if batch:
            await session.execute(insert(TelemetryEvent), batch)
            total += len(batch)
            batch = []

    shift = timedelta(0)
    if settings.telemetry_replay_shift:
        with path.open(encoding="utf-8-sig", newline="") as f:
            last = None
            for r in csv.DictReader(f):
                if r["дата"].strip() == "дата" or r["дата"].startswith("1970-01-01"):
                    continue
                ts = combine_csv_datetime(r["дата"], r["время"])
                if last is None or ts > last:
                    last = ts
        if last is not None:
            shift = now_msk() - last
            log.info("telemetry replay shift: +%s (last sample %s -> now)", shift, last.isoformat())

    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["дата"].strip() == "дата" or r["дата"].startswith("1970-01-01"):
                continue  # повторные заголовки и сброс часов контроллера (§1.4)
            raw = (r["значение_датчика"] or "").strip()
            is_alarm = normalize.parse_bool(r["тревожное"])
            numeric = normalize.parse_numeric(raw)
            batch.append(
                {
                    "event_id": int(r["ид_события"]),
                    "channel_id": int(r["ид_канала_данных"]),
                    "ts": combine_csv_datetime(r["дата"], r["время"]) + shift,
                    "is_alarm": is_alarm,
                    "raw_value": raw,
                    "numeric_value": numeric,
                    "status_code": normalize.status_code(raw, numeric, is_alarm),
                }
            )
            if len(batch) >= 10000:
                await flush()
    await flush()
    await session.commit()
    return total


async def seed_all(session: AsyncSession) -> dict[str, int]:
    result = {
        "objects": await seed_objects(session),
        "channels": await seed_channels(session),
        "state_dictionary": await seed_state_dictionary(session),
        "telemetry": await seed_telemetry(session),
    }
    log.info("seed result: %s", result)
    return result
