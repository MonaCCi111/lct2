"""Расчёт признаков SensorRiskInput по хронологии телеметрии канала (окно 24 ч до последней записи)."""
from __future__ import annotations

import statistics
from datetime import timedelta

from app.db.models import SensorChannel, TelemetryEvent
from app.ml.predictor import SensorRiskInput


def build_features(channel: SensorChannel, events: list[TelemetryEvent]) -> SensorRiskInput:
    """events - отсортированы по ts по возрастанию."""
    base = SensorRiskInput(
        channel_id=channel.id,
        sensor_type=channel.sensor_type,
        subsystem=channel.subsystem,
        tag_root=channel.tag_root,
        piket=channel.piket or "",
    )
    if not events:
        return base
    t_end = events[-1].ts
    w24 = [e for e in events if e.ts >= t_end - timedelta(hours=24)]
    w1 = [e for e in events if e.ts >= t_end - timedelta(hours=1)]

    def flaps(seq: list[TelemetryEvent]) -> int:
        n = 0
        for a, b in zip(seq, seq[1:]):
            if a.status_code != b.status_code or a.is_alarm != b.is_alarm:
                n += 1
        return n

    nums = [e.numeric_value for e in w24 if e.numeric_value is not None]
    last_alarm = next((e for e in reversed(events) if e.is_alarm), None)
    base.flapping_count_1h = flaps(w1)
    base.flapping_count_24h = flaps(w24)
    base.alarm_ratio_24h = (sum(1 for e in w24 if e.is_alarm) / len(w24)) if w24 else 0.0
    base.numeric_std_24h = statistics.pstdev(nums) if len(nums) > 1 else None
    base.last_numeric_value = next((e.numeric_value for e in reversed(events) if e.numeric_value is not None), None)
    base.hours_since_last_alarm = (
        (t_end - last_alarm.ts).total_seconds() / 3600.0 if last_alarm else 999.0
    )
    return base
