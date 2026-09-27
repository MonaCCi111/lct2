"""Время по INTEGRATION_SPEC §1.1: ISO 8601 в зоне Москвы (UTC+3): YYYY-MM-DDTHH:MM:SS+03:00.

Исторические метки ML-пакета (API v2) зоны НЕ имеют и отдаются как есть - см. app/api/v2.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3), name="MSK")


def now_msk() -> datetime:
    return datetime.now(tz=MSK).replace(microsecond=0)


def to_msk(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)


def iso_msk(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_msk(dt).replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    """Принимает 'YYYY-MM-DD', ISO с Z или смещением; наивные значения трактуются как МСК."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    if len(v) == 10:
        d = date.fromisoformat(v)
        return datetime(d.year, d.month, d.day, tzinfo=MSK)
    dt = datetime.fromisoformat(v)
    return to_msk(dt)


def combine_csv_datetime(date_str: str, time_str: str) -> datetime:
    return datetime.fromisoformat(f"{date_str.strip()}T{time_str.strip()}").replace(tzinfo=MSK)
