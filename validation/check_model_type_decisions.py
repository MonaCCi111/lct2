"""Проверить полноту решений по типам и согласованность с активным реестром."""

import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.active import ACTIVE_MODELS
from production_ml.pipeline.sensor_coverage import DECISIONS, describe_type


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    catalog = root.parents[1] / "dataset" / "справочник_каналов_датчиков.csv"
    if not catalog.exists():
        catalog = Path("G:/lct2/dataset/справочник_каналов_датчиков.csv")
    names = {row[0] for row in duckdb.connect().execute(
        f"SELECT DISTINCT \"тип_датчика\" FROM read_csv('{catalog.as_posix()}',header=true)"
    ).fetchall()}
    raw = json.loads((root / "production_ml/pipeline/model_type_decisions.json").read_text(encoding="utf-8"))
    assert len(raw["types"]) == len({item["sensor_type"] for item in raw["types"]})
    assert set(DECISIONS) == names, (sorted(names-set(DECISIONS)), sorted(set(DECISIONS)-names))
    assert len(DECISIONS) == 19
    active = {v["sensor_type"]: k for k, v in ACTIVE_MODELS.items()}
    for sensor_type, item in DECISIONS.items():
        assert item["forecast_capability"] in {"active", "research", "not_released"}
        assert item["forecast_reason"] and item["forecast_reason_text"]
        if item["forecast_capability"] == "active":
            assert active[sensor_type] == item["forecast_model_version"]
            assert ACTIVE_MODELS[active[sensor_type]]["target_kind"] == item["forecast_target_kind"]
        else:
            assert sensor_type not in active
        assert describe_type(sensor_type)["forecast_capability"] == item["forecast_capability"]
    assert set(active) == {name for name, item in DECISIONS.items()
                           if item["forecast_capability"] == "active"}
    assert DECISIONS["Датчик дыма"]["forecast_capability"] == "not_released"
    assert describe_type("Новый тип")["forecast_capability"] == "not_assessed"
    print(json.dumps({"checked_types":len(names),"active_types":len(active),
                      "research_types":sum(v["forecast_capability"]=="research"
                                           for v in DECISIONS.values()),
                      "not_released_types":sum(v["forecast_capability"]=="not_released"
                                               for v in DECISIONS.values())},ensure_ascii=False))


if __name__ == "__main__":
    main()
