"""Рассчитать свидетельства для одного дымового сигнала из ограниченной истории."""

from datetime import timedelta
from statistics import median


def build_signal_evidence(signal, smoke_history, temperature_history):
    """Входные строки содержат object_id, piket, channel_id и event_time.

    smoke_history содержит однозначные сигналы «Обнаружен дым»,
    temperature_history содержит числовые значения в поле numeric_value.
    mixed_alarm_flags_at_time передаётся во входном сигнале после проверки
    всех уже полученных состояний канала на ту же временную метку.
    Историю передают за последние 30 часов, включая события с той же меткой
    времени, которые уже поступили. Текущий сигнал добавляется функцией.
    """
    event_time = signal["event_time"]
    object_id = signal["object_id"]
    piket = signal.get("piket") or ""
    lower_smoke = event_time - timedelta(minutes=15)
    lower_recent = event_time - timedelta(hours=6)
    lower_baseline = event_time - timedelta(hours=30)

    object_channels = {signal["channel_id"]}
    location_channels = {signal["channel_id"]} if piket else set()
    for row in smoke_history:
        if (row["object_id"] != object_id
                or not lower_smoke <= row["event_time"] <= event_time):
            continue
        object_channels.add(row["channel_id"])
        if piket and row.get("piket") == piket:
            location_channels.add(row["channel_id"])

    recent = []
    baseline = []
    recent_channels = set()
    if piket:
        for row in temperature_history:
            if row["object_id"] != object_id or row.get("piket") != piket:
                continue
            t = row["event_time"]
            if not lower_baseline <= t <= event_time:
                continue
            value = row.get("numeric_value")
            if value is None:
                continue
            if t >= lower_recent:
                recent.append(value)
                recent_channels.add(row["channel_id"])
            else:
                baseline.append(value)

    recent_median = median(recent) if recent else None
    baseline_median = median(baseline) if baseline else None
    return {
        "channel_id": signal["channel_id"],
        "event_time": event_time,
        "object_id": object_id,
        "piket": piket,
        "mixed_alarm_flags_at_time": bool(signal.get("mixed_alarm_flags_at_time", False)),
        "object_smoke_channels_15m": len(object_channels),
        "location_smoke_channels_15m": len(location_channels),
        "recent_numeric_count": len(recent),
        "baseline_numeric_count": len(baseline),
        "recent_temp_channels": len(recent_channels),
        "recent_median": recent_median,
        "baseline_median": baseline_median,
        "temperature_delta": (recent_median - baseline_median
                              if recent_median is not None and baseline_median is not None
                              else None),
        "recent_min": min(recent) if recent else None,
        "recent_max": max(recent) if recent else None,
    }
