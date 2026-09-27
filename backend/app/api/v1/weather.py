"""Метеоданные Москвы (Open-Meteo) с кэшем на 1 час и дефолтом при ошибке сети (INTEGRATION_SPEC §3.7)."""
from __future__ import annotations

import logging
import time

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.contracts import WeatherDto

router = APIRouter(tags=["weather"])
log = logging.getLogger("weather")

_cache: dict[str, object] = {"ts": 0.0, "data": None}
DEFAULT = WeatherDto(temperature_c=12.0, relative_humidity=70.0, surface_pressure_hpa=1012.0, precipitation_mm=0.0,
                     source="default (Open-Meteo unavailable)")


async def fetch_weather() -> WeatherDto:
    async with httpx.AsyncClient(timeout=6.0) as client:
        r = await client.get(settings.weather_url)
        r.raise_for_status()
        cur = r.json()["current"]
        return WeatherDto(
            temperature_c=float(cur["temperature_2m"]),
            relative_humidity=float(cur["relative_humidity_2m"]),
            surface_pressure_hpa=float(cur["surface_pressure"]),
            precipitation_mm=float(cur.get("precipitation") or 0.0),
            source="Open-Meteo API",
        )


@router.get("/weather/current", response_model=WeatherDto)
async def current_weather() -> WeatherDto:
    now = time.monotonic()
    cached = _cache.get("data")
    if cached is not None and now - float(_cache["ts"]) < settings.weather_cache_ttl_sec:
        return cached.model_copy(update={"source": "Open-Meteo API / cache"})
    try:
        data = await fetch_weather()
        _cache.update(ts=now, data=data)
        return data
    except Exception as exc:  # noqa: BLE001
        log.warning("weather fetch failed: %s", exc)
        if cached is not None:
            return cached.model_copy(update={"source": "Open-Meteo API / stale cache"})
        return DEFAULT
