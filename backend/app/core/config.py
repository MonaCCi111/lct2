from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    app_name: str = "Moscollector Predictive Maintenance API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    api_v2_prefix: str = "/api/v2"

    database_url: str = f"sqlite+aiosqlite:///{BACKEND_ROOT / 'app.db'}"
    cors_origins: str = "*"
    data_dir: Path = BACKEND_ROOT / "data"
    ml_handoff_dir: Path = BACKEND_ROOT / "data" / "ml_handoff"
    log_level: str = "info"

    # Имена файлов справочников (dataset/ из репозитория)
    objects_csv: str = "справочник_объектов_диспетчер.csv"
    channels_csv: str = "справочник_каналов_датчиков.csv"
    states_csv: str = "справочник_состояний.csv"
    telemetry_csv: str = "telemetry_sample_100k.csv"

    # Погода
    weather_url: str = (
        "https://api.open-meteo.com/v1/forecast?latitude=55.7522&longitude=37.6156"
        "&current=temperature_2m,relative_humidity_2m,surface_pressure,precipitation"
    )
    weather_cache_ttl_sec: int = 3600

    # Даунсэмплинг телеметрии
    telemetry_max_points: int = 1000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
