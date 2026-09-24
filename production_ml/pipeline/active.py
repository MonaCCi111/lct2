"""Единственная точка выбора действующего ML-пакета."""

from pathlib import Path


MODEL_VERSION = "power_phase_scada_v2"
SUPPORTED_SENSOR_TYPES = ("Состояние фазы",)
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "models" / MODEL_VERSION
DATA = ROOT / "data" / "power_phase_v2"
