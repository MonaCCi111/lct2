"""Рассчитать часовой газовый факт и прошлые окна из ограниченной истории."""

from datetime import timedelta
from statistics import mean, median


def aggregate_hour(channel_id, object_id, obs_time, numeric_events):
    """numeric_events содержат только конечные числовые значения и время."""
    lower = obs_time - timedelta(hours=1)
    events = [row for row in numeric_events if lower <= row["event_time"] < obs_time]
    if not events:
        return None
    values = [row["numeric_value"] for row in events]
    return {
        "channel_id": channel_id,
        "object_id": object_id,
        "obs_time": obs_time,
        "numeric_count": len(values),
        "distinct_event_times": len({row["event_time"] for row in events}),
        "negative_count": sum(value < 0 for value in values),
        "numeric_min": min(values),
        "numeric_median": median(values),
        "numeric_mean": mean(values),
        "numeric_max": max(values),
    }


def build_hour_features(current_hour, previous_hours):
    """Повторить окна витрины на часовом факте и предыдущих 72 часах."""
    obs_time = current_hour["obs_time"]
    channel_id = current_hour["channel_id"]
    rows = [row for row in previous_hours
            if row["channel_id"] == channel_id
            and obs_time - timedelta(hours=72) <= row["obs_time"] < obs_time]
    rows.append(current_hour)
    recent = [row for row in rows if row["obs_time"] >= obs_time - timedelta(hours=5)]
    baseline = [row for row in rows if row["obs_time"] <= obs_time - timedelta(hours=6)]
    recent_median = median(row["numeric_median"] for row in recent)
    baseline_median = (median(row["numeric_median"] for row in baseline)
                       if baseline else None)
    return {
        **current_hour,
        "recent_observed_hours": len(recent),
        "recent_numeric_count": sum(row["numeric_count"] for row in recent),
        "recent_hourly_median": recent_median,
        "recent_max": max(row["numeric_max"] for row in recent),
        "baseline_observed_hours": len(baseline),
        "baseline_numeric_count": (sum(row["numeric_count"] for row in baseline)
                                   if baseline else None),
        "baseline_hourly_median": baseline_median,
        "baseline_negative_count": (sum(row["negative_count"] for row in baseline)
                                    if baseline else None),
        "median_delta": (recent_median - baseline_median
                         if baseline_median is not None else None),
    }
