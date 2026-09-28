"""Агрегаты для дашборда/объектов/аналитики. Считаются на бэкенде (фронт ничего не выводит сам)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectorObject, MaintenanceTicket, PredictionRecord, SensorChannel
from app.ml.predictor import MODEL_DOMAIN_BY_SENSOR_TYPE, predictor

RISK_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}
OBJECT_TYPE_LABELS = {"district": "Эксплуатационный район", "controlHouse": "Диспетчерский пункт", "guardObject": "Охраняемый объект"}


@dataclass
class ObjectStats:
    object_id: int
    channels_total: int = 0
    ml_supported: int = 0
    active: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    max_probability: float | None = None
    open_tickets: int = 0
    risk_level: str | None = None
    predictions: list[PredictionRecord] = field(default_factory=list)

    def finalize(self) -> "ObjectStats":
        if self.critical:
            self.risk_level = "critical"
        elif self.high:
            self.risk_level = "high"
        elif self.medium:
            self.risk_level = "medium"
        elif self.active:
            self.risk_level = "low"
        else:
            self.risk_level = None
        return self


def is_active(p: PredictionRecord) -> bool:
    """Активный прогноз = поддерживаемый моделью и не закрытый наряд (completed/rejected снимают его из активных)."""
    return bool(p.prediction_supported and p.risk_category is not None)


async def load_objects(session: AsyncSession) -> dict[int, CollectorObject]:
    return {o.id: o for o in (await session.scalars(select(CollectorObject))).all()}


def collector_of(obj: CollectorObject, objects: dict[int, CollectorObject]) -> CollectorObject | None:
    """Коллектор (уровень 2), к которому относится объект любого уровня."""
    cur = obj
    while cur is not None and cur.level > 2:
        cur = objects.get(cur.parent_id) if cur.parent_id else None
    return cur if cur is not None and cur.level == 2 else None


async def object_stats(session: AsyncSession, objects: dict[int, CollectorObject] | None = None) -> dict[int, ObjectStats]:
    """Статистика по каждому объекту. Каналы привязаны к объектам 3 уровня и суммируются вверх по дереву."""
    objects = objects or await load_objects(session)
    channels = (await session.scalars(select(SensorChannel))).all()
    predictions = (await session.scalars(select(PredictionRecord))).all()
    ticket_rows = (
        await session.execute(
            select(MaintenanceTicket.object_id, func.count())
            .where(MaintenanceTicket.status.in_(("draft", "approved")))
            .group_by(MaintenanceTicket.object_id)
        )
    ).all()
    open_by_obj = {oid: n for oid, n in ticket_rows}
    pred_by_channel = {p.channel_id: p for p in predictions}
    ch_by_id = {c.id: c for c in channels}

    stats: dict[int, ObjectStats] = {oid: ObjectStats(object_id=oid) for oid in objects}

    def add_channel(st: ObjectStats, ch: SensorChannel) -> None:
        st.channels_total += 1
        if predictor.supports(ch.sensor_type):
            st.ml_supported += 1
        p = pred_by_channel.get(ch.id)
        if p and is_active(p):
            st.active += 1
            st.predictions.append(p)
            if p.risk_category == "critical":
                st.critical += 1
            elif p.risk_category == "high":
                st.high += 1
            elif p.risk_category == "medium":
                st.medium += 1
            if p.failure_probability is not None:
                st.max_probability = max(st.max_probability or 0.0, p.failure_probability)

    ancestors: dict[int, list[int]] = {}
    for oid, obj in objects.items():
        chain, cur = [], obj
        while cur is not None:
            chain.append(cur.id)
            cur = objects.get(cur.parent_id) if cur.parent_id else None
        ancestors[oid] = chain

    for ch in channels:
        for oid in ancestors.get(ch.object_id, []):  # канал считается у своего объекта и у всех предков
            add_channel(stats[oid], ch)

    for oid, st in stats.items():
        st.open_tickets = open_by_obj.get(oid, 0)
        st.finalize()
    return stats


def coverage_percent(supported: int, total: int) -> float:
    return round(100.0 * supported / total, 1) if total else 0.0


def domain_of(ch: SensorChannel) -> str | None:
    return MODEL_DOMAIN_BY_SENSOR_TYPE.get(ch.sensor_type)
