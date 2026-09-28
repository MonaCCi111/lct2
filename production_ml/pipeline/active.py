"""Единственная точка выбора действующего ML-пакета."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_MODELS = {
    "power_phase_scada_v2": {
        "sensor_type": "Состояние фазы",
        "bundle": ROOT / "models" / "power_phase_scada_v2",
        "scorer": "production_ml.pipeline.score_power_phase_v2",
        "target_kind": "SCADA_STATUS_EPISODE",
    },
    "pump_scada_v1": {
        "sensor_type": "Состояние насоса",
        "bundle": ROOT / "models" / "pump_scada_v1",
        "scorer": "production_ml.pipeline.score_pump",
        "target_kind": "SCADA_PUMP_ALARM",
    },
}
MODEL_VERSION = "power_phase_scada_v2"
SUPPORTED_SENSOR_TYPES = tuple(
    spec["sensor_type"] for spec in ACTIVE_MODELS.values()
)
BUNDLE = ROOT / "models" / MODEL_VERSION
DATA = ROOT / "data" / "power_phase_v2"
