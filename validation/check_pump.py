"""Проверки pump_scada_v1."""

import sys

from .alarm_branch_checks import run


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run(
        data_name="pump_v1",
        bundle_name="pump_scada_v1",
        model_module_name="production_ml.pipeline.pump_model",
        package_module_name="production_ml.pipeline.package_pump",
    )


if __name__ == "__main__":
    main()
