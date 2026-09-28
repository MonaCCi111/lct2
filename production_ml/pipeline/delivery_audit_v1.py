"""Измерить повторы и позднюю доставку без изменения ML-решений."""

from datetime import datetime


FIELDS = ("channel_id","event_time","event_id","sensor_value","is_alarm")


def audit_deliveries(records):
    """Вернуть принятые исходные записи и факты о порядке доставки.

    Повтор определяется полным составным ключом. Позднее событие
    сравнивается с уже увиденным временем того же канала.
    """
    seen = set()
    by_event_id = {}
    latest_by_channel = {}
    accepted = []
    duplicate = []
    late = []
    reused_event_id = []
    for position,record in enumerate(records,1):
        missing = [field for field in FIELDS if field not in record]
        if missing:
            raise ValueError(f"Запись {position}: нет полей {missing}")
        stamp = record["event_time"]
        if isinstance(stamp,str):
            stamp = datetime.fromisoformat(stamp)
        if stamp.tzinfo is not None:
            raise ValueError("В исходном журнале временная зона неизвестна")
        key = (record["channel_id"],stamp,record["event_id"],
               record["sensor_value"],record["is_alarm"])
        if key in seen:
            duplicate.append({"position":position,"source_key":key})
            continue
        seen.add(key)
        prior_id = by_event_id.get(record["event_id"])
        if prior_id is not None and prior_id!=key:
            reused_event_id.append({"position":position,"event_id":record["event_id"]})
        else:
            by_event_id[record["event_id"]] = key
        previous = latest_by_channel.get(record["channel_id"])
        if previous is not None and stamp<previous:
            late.append({"position":position,"channel_id":record["channel_id"],
                         "event_time":stamp,"previous_latest_time":previous})
        latest_by_channel[record["channel_id"]] = max(previous,stamp) if previous else stamp
        accepted.append(dict(record))
    return {"accepted":accepted,"duplicate":duplicate,"late":late,
            "reused_event_id":reused_event_id}
