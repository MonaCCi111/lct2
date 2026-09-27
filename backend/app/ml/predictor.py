"""Интерфейс предиктора (INTEGRATION_SPEC §2.3-2.4, BACKEND_SANYA_GUIDE §4).

SensorRiskInput / SensorRiskOutput - контракт со Славой, не менять.
Дополнительные поля SensorRiskOutput (risk_level/urgency/ИТС/domain) нужны фронту Ромы (BACKEND_API_CONTRACT_V1).
Замена заглушки на боевую модель: присвоить `predictor` экземпляр класса с тем же методом `predict`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel

MODEL_DOMAIN_BY_SENSOR_TYPE: dict[str, str] = {
    "Состояние фазы": "POWER_PHASE",
    "ИБП": "POWER_PHASE",
    "Переключатель": "POWER_PHASE",
    "Датчик температуры": "ANALOG_TEMP",
    "Газовый датчик": "ANALOG_GAS",
    "Датчик дыма": "FIRE_SAFETY",
    "Тепловой датчик": "FIRE_SAFETY",
    "Ручной извещатель": "FIRE_SAFETY",
    "Состояние насоса": "HYDRO_MECHANICS",
    "Состояние вентилятора": "HYDRO_MECHANICS",
    "Датчик затопления": "HYDRO_MECHANICS",
}


class SensorRiskInput(BaseModel):
    channel_id: int
    sensor_type: str
    subsystem: str
    tag_root: str
    piket: str
    flapping_count_1h: int = 0
    flapping_count_24h: int = 0
    alarm_ratio_24h: float = 0.0
    numeric_std_24h: Optional[float] = None
    last_numeric_value: Optional[float] = None
    hours_since_last_alarm: float = 999.0


class SensorRiskOutput(BaseModel):
    channel_id: int
    failure_probability: float
    risk_category: str  # "low", "medium", "critical" (спек) + "high" (фронт)
    forecast_horizon_hours: int = 24
    primary_cause: str
    recommended_action: str
    # расширение под контракт фронта v1
    model_domain: Optional[str] = None
    maintenance_urgency: Optional[str] = None  # FLASH_1_6H | URGENT_6_24H | PLANNED_24_48H | NORMAL
    lead_time_hours: Optional[float] = None
    health_index_its: Optional[int] = None
    top_risk_factors: list[str] = []


def risk_category_for(p: float) -> str:
    if p >= 0.7:
        return "critical"
    if p >= 0.5:
        return "high"
    if p >= 0.3:
        return "medium"
    return "low"


def urgency_for(p: float) -> str:
    if p >= 0.85:
        return "FLASH_1_6H"
    if p >= 0.7:
        return "URGENT_6_24H"
    if p >= 0.3:
        return "PLANNED_24_48H"
    return "NORMAL"


def lead_time_for(p: float) -> float:
    return {"FLASH_1_6H": 4.0, "URGENT_6_24H": 18.0, "PLANNED_24_48H": 36.0}.get(urgency_for(p), 72.0)


def its_for(p: float) -> int:
    return max(0, min(100, int(round(100.0 * (1.0 - p)))))


class DummyPredictor:
    """Заглушка по INTEGRATION_SPEC §2.4 до передачи весов от Славы."""

    model_version = "dummy-0.1"

    def predict(self, item: SensorRiskInput) -> SensorRiskOutput:
        factors: list[str] = []
        if item.flapping_count_24h > 5:
            factors.append(f"Дребезг контактов: {item.flapping_count_24h} переключений за 24 ч")
        if item.alarm_ratio_24h > 0.2:
            factors.append(f"Доля тревожных записей за 24 ч: {item.alarm_ratio_24h:.0%}")
        if item.numeric_std_24h is not None and item.numeric_std_24h > 3:
            factors.append(f"Нестабильность показаний (σ={item.numeric_std_24h:.1f})")

        if item.flapping_count_24h > 5 or item.alarm_ratio_24h > 0.2:
            p = 0.88
            return SensorRiskOutput(
                channel_id=item.channel_id,
                failure_probability=p,
                risk_category=risk_category_for(p),
                primary_cause="Аппаратный дребезг контактов",
                recommended_action="Протяжка клемм и ревизия датчика",
                model_domain=MODEL_DOMAIN_BY_SENSOR_TYPE.get(item.sensor_type),
                maintenance_urgency=urgency_for(p),
                lead_time_hours=lead_time_for(p),
                health_index_its=its_for(p),
                top_risk_factors=factors,
            )
        p = 0.08 if item.hours_since_last_alarm > 24 else 0.35
        return SensorRiskOutput(
            channel_id=item.channel_id,
            failure_probability=p,
            risk_category=risk_category_for(p),
            primary_cause="Показания в пределах нормы" if p < 0.3 else "Недавние тревожные срабатывания",
            recommended_action="Штатный мониторинг" if p < 0.3 else "Плановый осмотр при ближайшем обходе",
            model_domain=MODEL_DOMAIN_BY_SENSOR_TYPE.get(item.sensor_type),
            maintenance_urgency=urgency_for(p),
            lead_time_hours=lead_time_for(p),
            health_index_its=its_for(p),
            top_risk_factors=factors,
        )

    def supports(self, sensor_type: str) -> bool:
        return sensor_type in MODEL_DOMAIN_BY_SENSOR_TYPE


def load_predictor(weights_dir: Path | None = None):
    """Точка стыковки с ML. Здесь позже подключается боевая модель Славы (одна строка).

    Ожидаемый файл: app/ml/weights/catboost_sensor_failure.cbm либо пакет из integration/backend_sanya/models.
    """
    return DummyPredictor()


# Глобальный синглтон предиктора
predictor = load_predictor()
