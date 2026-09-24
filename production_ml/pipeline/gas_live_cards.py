"""Собрать карточки уже наблюдавшихся газовых статусов из потока свидетельств."""

from datetime import timedelta


def build_observed_cards(alarm_evidence):
    """Вход содержит уникальные тревожные времена и поля alarm_evidence."""
    ordered = sorted(alarm_evidence,
                     key=lambda row: (row["object_id"], row["event_time"], row["channel_id"]))
    cards = []
    active = None
    last_object = None
    last_time = None
    alarm_channels = set()
    numeric_channels = set()
    comparable_channels = set()
    for row in ordered:
        object_id = row["object_id"]
        time = row["event_time"]
        if (active is None or object_id != last_object
                or time > last_time + timedelta(hours=1)):
            if active is not None:
                active["alarm_channels"] = len(alarm_channels)
                active["numeric_channels_24h"] = len(numeric_channels)
                active["comparable_numeric_channels_24h"] = len(comparable_channels)
                cards.append(active)
            active = {
                "card_id": f"{object_id}:{time:%Y%m%dT%H%M%S}",
                "object_id": object_id,
                "first_alarm_time": time,
                "last_alarm_time": time,
                "alarm_records": 0,
                "mixed_status_records": 0,
                "maximum_recent_numeric": None,
                "card_kind": "OBSERVED_GAS_STATUS",
            }
            alarm_channels = set()
            numeric_channels = set()
            comparable_channels = set()
        active["last_alarm_time"] = time
        active["alarm_records"] += 1
        alarm_channels.add(row["channel_id"])
        active["mixed_status_records"] += int(bool(row["mixed_status_at_time"]))
        age = row.get("numeric_age_hours")
        if age is not None and 0 <= age <= 24:
            numeric_channels.add(row["channel_id"])
            if row.get("recent_observed_hours") and row.get("baseline_observed_hours"):
                comparable_channels.add(row["channel_id"])
            numeric_max = row.get("recent_max")
            if numeric_max is not None:
                old_max = active["maximum_recent_numeric"]
                active["maximum_recent_numeric"] = (
                    numeric_max if old_max is None else max(old_max, numeric_max)
                )
        last_object = object_id
        last_time = time
    if active is not None:
        active["alarm_channels"] = len(alarm_channels)
        active["numeric_channels_24h"] = len(numeric_channels)
        active["comparable_numeric_channels_24h"] = len(comparable_channels)
        cards.append(active)
    return cards
