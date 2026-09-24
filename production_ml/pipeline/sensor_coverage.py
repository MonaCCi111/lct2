"""Описание возможностей типа и текущего наблюдения канала.

Здесь нет обученных по ID исключений и решений о выпуске черновика.
"""

from __future__ import annotations

import json
from datetime import datetime


SCHEMA_VERSION = "sensor_coverage_v1"
RECENT_HOURS = 72

# Это версии уже проверенных веток, а не вывод о любом канале данного типа.
TYPE_CAPABILITIES = {
    "Состояние фазы": ("active", "power_phase_scada_v2", "not_assessed", "categorical"),
    "Состояние насоса": ("active", "pump_scada_v1", "not_assessed", "categorical"),
    "Датчик температуры": ("research", "temperature_scada_v1", "not_assessed", "numeric_and_status"),
    "Состояние вентилятора": ("research", "fan_scada_v1", "not_assessed", "categorical"),
    "Датчик дыма": ("not_released", None, "research", "categorical"),
    "Газовый датчик": ("not_released", None, "research", "numeric_and_status"),
}

FORECAST_REASONS = {
    "Состояние фазы": "active_package_available",
    "Состояние насоса": "active_package_available",
    "Датчик температуры": "too_few_policy_target_episodes",
    "Состояние вентилятора": "weak_policy_quality",
    "Датчик дыма": "fire_prediction_out_of_scope_smoke_fault_model_not_released",
    "Газовый датчик": "gas_prediction_not_validated",
}


def describe_type(sensor_type: str | None) -> dict:
    forecast, version, observed, chart = TYPE_CAPABILITIES.get(
        sensor_type, ("not_assessed", None, "not_assessed", "raw_event_timeline")
    )
    return {
        "sensor_type": sensor_type,
        "forecast_capability": forecast,
        "forecast_model_version": version,
        "forecast_reason": FORECAST_REASONS.get(sensor_type, "type_not_studied_yet"),
        "observed_event_capability": observed,
        "observed_event_reason": (
            "historical_evidence_only" if observed == "research"
            else "observed_event_scenario_not_validated"
        ),
        "chart_capability": chart,
        "chart_reason": (
            "unit_not_confirmed" if chart == "numeric_and_status"
            else "value_semantics_not_assessed" if chart == "raw_event_timeline"
            else "literal_recorded_statuses"
        ),
        "its_capability": "pending_definition",
    }


def assess_channel(facts: dict, as_of: datetime) -> dict:
    """Превратить измеренные факты канала в понятное состояние на as_of.

    `no_recent_events` говорит только об отсутствии записей, не о поломке.
    `recent_input_context` не обещает, что модель выдаст балл.
    """
    channel_id = int(facts["channel_id"])
    sensor_type = facts.get("sensor_type")
    capability = describe_type(sensor_type)
    last_time = facts.get("last_event_time")
    first_time = facts.get("first_event_time")
    event_count = int(facts.get("event_count") or 0)
    recent_count = int(facts.get("events_72h") or 0)
    mixed_count = int(facts.get("mixed_alarm_timestamps_72h") or 0)
    in_catalog = bool(facts.get("in_catalog"))

    issues = []
    if not in_catalog:
        issues.append("channel_missing_from_catalog")
    if event_count == 0:
        state = "no_historical_events"
        issues.append("no_historical_events")
    elif recent_count == 0:
        state = "no_recent_events"
        issues.append("no_events_in_72h")
    elif mixed_count:
        state = "recent_conflicting_events"
        issues.append("mixed_alarm_at_same_timestamp")
    else:
        state = "recent_events"

    if first_time is not None and last_time is not None:
        history_hours = round((last_time - first_time).total_seconds() / 3600, 3)
        age_hours = round((as_of - last_time).total_seconds() / 3600, 3)
        if history_hours < RECENT_HOURS:
            issues.append("history_shorter_than_72h")
    else:
        history_hours = None
        age_hours = None

    if capability["forecast_capability"] == "active":
        if not in_catalog:
            context = "metadata_missing"
        elif recent_count == 0:
            context = "no_recent_events"
        elif mixed_count:
            context = "conflicting_recent_events"
        elif history_hours is not None and history_hours < RECENT_HOURS:
            context = "limited_72h_history"
        else:
            context = "recent_input_present"
    else:
        context = "no_active_model_for_type"

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of.isoformat(sep=" "),
        "channel_id": channel_id,
        "sensor_type": sensor_type,
        "object_id": facts.get("object_id"),
        "in_catalog": in_catalog,
        "observation_state": state,
        "issue_codes": json.dumps(issues, ensure_ascii=False),
        "first_event_time": first_time.isoformat(sep=" ") if first_time else None,
        "last_event_time": last_time.isoformat(sep=" ") if last_time else None,
        "last_recorded_value": facts.get("last_recorded_value"),
        "last_recorded_is_alarm": facts.get("last_recorded_is_alarm"),
        "event_count": event_count,
        "events_72h": recent_count,
        "events_30d": int(facts.get("events_30d") or 0),
        "finite_numeric_events_30d": int(facts.get("finite_numeric_events_30d") or 0),
        "mixed_alarm_timestamps_72h": mixed_count,
        "hours_since_last_event": age_hours,
        "history_span_hours": history_hours,
        "recent_input_context": context,
        **{key: value for key, value in capability.items() if key != "sensor_type"},
    }
