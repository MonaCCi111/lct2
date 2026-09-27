"""Скоринг каналов: по каждому каналу со срезом телеметрии строится PredictionRecord,
плюс почасовые срезы числа рисков (RiskSnapshot) для аналитики."""
from __future__ import annotations

import asyncio
import json
import logging
from bisect import bisect_right
from datetime import datetime, timedelta

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import now_msk
from app.db.models import PredictionRecord, RiskSnapshot, SensorChannel, TelemetryEvent
from app.ml import predictor as ml
from app.ml.features import build_features

log = logging.getLogger("scoring")


def prediction_id_for(channel: SensorChannel) -> str:
    return f"pred-{channel.tag_root}-{channel.id}"


def apply_output(rec: PredictionRecord, out) -> None:
    rec.model_domain = out.model_domain
    rec.failure_probability = out.failure_probability
    rec.risk_category = out.risk_category
    rec.maintenance_urgency = out.maintenance_urgency
    rec.lead_time_hours = out.lead_time_hours
    rec.health_index_its = out.health_index_its
    rec.forecast_horizon_hours = out.forecast_horizon_hours
    rec.primary_cause = out.primary_cause
    rec.top_risk_factors = json.dumps(out.top_risk_factors or [out.primary_cause], ensure_ascii=False)
    rec.recommended_action = out.recommended_action


async def score_channel(session: AsyncSession, ch: SensorChannel, generated_at: datetime) -> PredictionRecord:
    events = (
        await session.scalars(select(TelemetryEvent).where(TelemetryEvent.channel_id == ch.id).order_by(TelemetryEvent.ts))
    ).all()
    features = build_features(ch, events)
    supported = ml.predictor.supports(ch.sensor_type)
    rec = await session.get(PredictionRecord, prediction_id_for(ch))
    if rec is None:
        rec = PredictionRecord(id=prediction_id_for(ch), channel_id=ch.id, review_status="pending_review")
        session.add(rec)
    rec.object_id = ch.object_id
    rec.model_version = ml.predictor.model_version
    rec.generated_at = generated_at
    rec.features_json = features.model_dump_json()
    rec.prediction_supported = supported
    if supported:
        apply_output(rec, ml.predictor.predict(features))
    return rec


async def score_all_channels(session: AsyncSession, only_if_empty: bool = True) -> int:
    if only_if_empty:
        existing = await session.scalar(select(func.count()).select_from(PredictionRecord))
        if existing:
            return 0
    channel_ids = (await session.scalars(select(TelemetryEvent.channel_id).distinct())).all()
    if not channel_ids:
        return 0
    channels = (await session.scalars(select(SensorChannel).where(SensorChannel.id.in_(channel_ids)))).all()
    generated_at = now_msk()
    for ch in channels:
        await score_channel(session, ch, generated_at)
    await session.commit()
    log.info("scored %d channels", len(channels))
    return len(channels)


async def build_risk_timeline_background() -> None:
    """Запускается фоновой задачей после старта, чтобы не задерживать готовность сервиса."""
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as session:
            channel_ids = (await session.scalars(select(TelemetryEvent.channel_id).distinct())).all()
            channels = (await session.scalars(select(SensorChannel).where(SensorChannel.id.in_(channel_ids)))).all() if channel_ids else []
            await build_risk_timeline(session, channels)
    except Exception:  # noqa: BLE001
        log.exception("risk timeline build failed")


async def build_risk_timeline(session: AsyncSession, channels: list[SensorChannel], step_hours: int = 1) -> int:
    """Почасовые срезы: для каждого часа t считаются признаки по событиям ≤ t и число каналов по категориям."""
    t_min = await session.scalar(select(func.min(TelemetryEvent.ts)))
    t_max = await session.scalar(select(func.max(TelemetryEvent.ts)))
    if t_min is None or t_max is None:
        return 0
    if t_min.tzinfo is None:  # SQLite возвращает наивное время
        from app.core.timeutil import MSK

        t_min, t_max = t_min.replace(tzinfo=MSK), t_max.replace(tzinfo=MSK)
    per_channel: dict[int, tuple[list[TelemetryEvent], list[datetime]]] = {}
    for ch in channels:
        if not ml.predictor.supports(ch.sensor_type):
            continue
        events = (
            await session.scalars(select(TelemetryEvent).where(TelemetryEvent.channel_id == ch.id).order_by(TelemetryEvent.ts))
        ).all()
        per_channel[ch.id] = (events, [e.ts if e.ts.tzinfo else e.ts.replace(tzinfo=t_min.tzinfo) for e in events])
    ch_by_id = {c.id: c for c in channels}

    def compute() -> list[dict]:
        # CPU-bound: выполняется в отдельном потоке, чтобы не блокировать event loop
        snapshots: list[dict] = []
        t = t_min.replace(minute=0, second=0, microsecond=0) + timedelta(hours=step_hours)
        while t <= t_max + timedelta(hours=step_hours):
            counts = {"critical": 0, "high": 0, "medium": 0}
            for cid, (events, ts_list) in per_channel.items():
                idx = bisect_right(ts_list, t)
                if idx == 0:
                    continue
                lo = bisect_right(ts_list, t - timedelta(hours=25))
                out = ml.predictor.predict(build_features(ch_by_id[cid], events[lo:idx]))
                if out.risk_category in counts:
                    counts[out.risk_category] += 1
            snapshots.append({"ts": t, **counts})
            t += timedelta(hours=step_hours)
        return snapshots

    snapshots = await asyncio.to_thread(compute)
    await session.execute(delete(RiskSnapshot))
    if snapshots:
        await session.execute(insert(RiskSnapshot), snapshots)
    await session.commit()
    log.info("risk timeline: %d hourly snapshots", len(snapshots))
    return len(snapshots)
