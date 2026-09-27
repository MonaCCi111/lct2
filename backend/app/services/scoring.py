"""Фоновый скоринг: по каждому каналу со срезом телеметрии строится PredictionRecord."""
from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import now_msk
from app.db.models import PredictionRecord, SensorChannel, TelemetryEvent
from app.ml import predictor as ml
from app.ml.features import build_features

log = logging.getLogger("scoring")


def prediction_id_for(channel: SensorChannel) -> str:
    return f"pred-{channel.tag_root}-{channel.id}"


async def score_all_channels(session: AsyncSession, only_if_empty: bool = True) -> int:
    if only_if_empty:
        existing = await session.scalar(select(func.count()).select_from(PredictionRecord))
        if existing:
            return 0
    channel_ids = (await session.scalars(select(TelemetryEvent.channel_id).distinct())).all()
    if not channel_ids:
        return 0
    channels = {c.id: c for c in (await session.scalars(select(SensorChannel).where(SensorChannel.id.in_(channel_ids)))).all()}
    generated_at = now_msk()
    created = 0
    for cid in channel_ids:
        ch = channels.get(cid)
        if ch is None:
            continue  # канал вне справочника - остаётся виден в телеметрии, но не прогнозируется
        events = (
            await session.scalars(select(TelemetryEvent).where(TelemetryEvent.channel_id == cid).order_by(TelemetryEvent.ts))
        ).all()
        features = build_features(ch, events)
        supported = ml.predictor.supports(ch.sensor_type)
        rec = PredictionRecord(
            id=prediction_id_for(ch),
            channel_id=ch.id,
            object_id=ch.object_id,
            model_version=ml.predictor.model_version,
            generated_at=generated_at,
            features_json=features.model_dump_json(),
            prediction_supported=supported,
        )
        if supported:
            out = ml.predictor.predict(features)
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
        session.add(rec)
        created += 1
    await session.commit()
    log.info("scored %d channels", created)
    return created
