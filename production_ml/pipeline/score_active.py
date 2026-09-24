"""CLI действующей модели. Версия выбирается только в active.py."""

from .active import MODEL_VERSION
from .score_power_phase_v2 import main


if MODEL_VERSION != "power_phase_scada_v2":
    raise RuntimeError(f"Для {MODEL_VERSION} не зарегистрирован scorer")


if __name__ == "__main__":
    main()
