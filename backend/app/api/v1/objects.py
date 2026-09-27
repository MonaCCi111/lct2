from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.errors import not_found
from app.core.timeutil import iso_msk, now_msk
from app.db.models import CollectorObject, PredictionRecord, SensorChannel
from app.schemas.contracts import ObjectDetailDto, ObjectDto, ObjectStatusSummaryDto, ObjectTopologyDto, TopologySegmentDto
from app.services.aggregates import OBJECT_TYPE_LABELS, is_active, load_objects, object_stats

router = APIRouter(tags=["objects"])


def _status_for(risk: str | None) -> str:
    return {"critical": "critical", "high": "warning", "medium": "warning"}.get(risk or "", "normal")


@router.get("/objects", response_model=list[ObjectDto])
async def list_objects(db: DbSession, level: int | None = None) -> list[ObjectDto]:
    """Плоский справочник объектов (95 записей). level=2 - только 16 коллекторов."""
    q = select(CollectorObject).order_by(CollectorObject.level, CollectorObject.name)
    if level is not None:
        q = q.where(CollectorObject.level == level)
    objs = (await db.scalars(q)).all()
    return [
        ObjectDto(
            object_id=o.id,
            object_name=o.name,
            parent_object_id=o.parent_id,
            subsystem=OBJECT_TYPE_LABELS.get(o.object_type, o.object_type),
        )
        for o in objs
    ]


@router.get("/objects/status-summary", response_model=list[ObjectStatusSummaryDto])
async def objects_status_summary(db: DbSession, scope: str = "collectors") -> list[ObjectStatusSummaryDto]:
    """Сводка по 16 коллекторам (scope=collectors, по умолчанию) или по всем объектам (scope=all)."""
    now = iso_msk(now_msk()) or ""
    objects = await load_objects(db)
    stats = await object_stats(db, objects)
    rows = []
    for oid, st in stats.items():
        o = objects[oid]
        if scope != "all" and o.level != 2:
            continue
        rows.append(
            ObjectStatusSummaryDto(
                object_id=oid,
                object_name=o.name,
                risk_level=st.risk_level,
                active_predictions=st.active,
                critical_predictions=st.critical,
                high_predictions=st.high,
                ml_supported_channels=st.ml_supported,
                channels_total=st.channels_total,
                updated_at=now,
            )
        )
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    rows.sort(key=lambda r: (order.get(r.risk_level, 4), -r.critical_predictions, -r.active_predictions, r.object_name))
    return rows


@router.get("/objects/{object_id}", response_model=ObjectDetailDto)
async def object_detail(object_id: int, db: DbSession) -> ObjectDetailDto:
    objects = await load_objects(db)
    o = objects.get(object_id)
    if o is None:
        raise not_found(f"Объект {object_id} не найден в справочнике")
    st = (await object_stats(db, objects))[object_id]
    return ObjectDetailDto(
        object_id=o.id,
        object_name=o.name,
        parent_object_id=o.parent_id,
        object_type=OBJECT_TYPE_LABELS.get(o.object_type, o.object_type),
        channels_total=st.channels_total,
        ml_supported_channels=st.ml_supported,
        risk_level=st.risk_level,
        active_predictions=st.active,
        critical_predictions=st.critical,
        high_predictions=st.high,
        updated_at=iso_msk(now_msk()) or "",
    )


@router.get("/objects/{object_id}/topology", response_model=ObjectTopologyDto)
async def object_topology(object_id: int, db: DbSession) -> ObjectTopologyDto:
    """Линейная схема коллектора по пикетам (INTEGRATION_SPEC §3.2). Сегменты - дочерние объекты 3 уровня
    с диапазоном ПК в названии; если их нет - равные отрезки по 100 пикетов по фактическому диапазону каналов."""
    objects = await load_objects(db)
    o = objects.get(object_id)
    if o is None:
        raise not_found(f"Объект {object_id} не найден в справочнике")
    # для объекта 3 уровня показываем схему его коллектора
    collector = o
    while collector.level > 2 and collector.parent_id in objects:
        collector = objects[collector.parent_id]
    channels = (
        await db.scalars(select(SensorChannel).where(SensorChannel.object_id == collector.id, SensorChannel.piket_value.is_not(None)))
    ).all()
    preds = {p.channel_id: p for p in (await db.scalars(select(PredictionRecord))).all() if is_active(p)}
    now = iso_msk(now_msk()) or ""
    if not channels:
        return ObjectTopologyDto(
            object_id=o.id, object_name=o.name, piket_min=None, piket_max=None, updated_at=now, segments=[],
            collector_id=collector.id, collector_name=collector.name,
        )
    pk_min = min(c.piket_value for c in channels)
    pk_max = max(c.piket_value for c in channels)
    ranges: list[tuple[str, str, float, float]] = []
    children = sorted(
        [c for c in objects.values() if c.parent_id == collector.id and c.piket_from is not None and c.piket_to is not None],
        key=lambda c: c.piket_from,
    )
    if children:
        for c in children:
            ranges.append((f"SEG-{collector.id}-{c.id}", c.name, c.piket_from, c.piket_to))
        # хвост за последним известным сегментом
        if pk_max > children[-1].piket_to:
            ranges.append((f"SEG-{collector.id}-tail", f"ПК{int(children[-1].piket_to)}-ПК{int(pk_max) + 1}", children[-1].piket_to, float(int(pk_max) + 1)))
    else:
        start = float(int(pk_min // 100) * 100)
        idx = 1
        while start <= pk_max:
            end = start + 100
            ranges.append((f"SEG-{collector.id}-{idx:02d}", f"ПК{int(start)}-ПК{int(end)}", start, end))
            start = end
            idx += 1
    segments: list[TopologySegmentDto] = []
    for seg_id, label, a, b in ranges:
        seg_ch = [c for c in channels if a <= c.piket_value <= b]
        seg_preds = [preds[c.id] for c in seg_ch if c.id in preds]
        crit = sum(1 for p in seg_preds if p.risk_category == "critical")
        high = sum(1 for p in seg_preds if p.risk_category == "high")
        med = sum(1 for p in seg_preds if p.risk_category == "medium")
        risk = "critical" if crit else "high" if high else "medium" if med else ("low" if seg_preds else None)
        probs = [p.failure_probability for p in seg_preds if p.failure_probability is not None]
        segments.append(
            TopologySegmentDto(
                segment_id=seg_id, label=label, piket_from=a, piket_to=b, risk_level=risk,
                active_predictions=len(seg_preds), critical_predictions=crit, high_predictions=high,
                max_failure_probability=max(probs) if probs else None, status=_status_for(risk),
            )
        )
    return ObjectTopologyDto(
        object_id=o.id, object_name=o.name,
        piket_min=min(pk_min, ranges[0][2]), piket_max=max(pk_max, ranges[-1][3]),
        updated_at=now, segments=segments, collector_id=collector.id, collector_name=collector.name,
    )
