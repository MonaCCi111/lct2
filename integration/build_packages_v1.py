"""Собрать переносимый проверяемый набор для двух продуктовых команд."""

import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "integration"
BACKEND = OUT / "backend_sanya"
FRONTEND = OUT / "frontend_roma"
DATA = ROOT / "production_ml" / "data"
SOURCE_MANIFEST = DATA / "handoff_v1" / "schema_manifest.json"
SCORER_INPUTS = (
    "power_phase_v2/features.parquet",
    "power_phase_v2/phase_events.parquet",
    "power_phase_v2/episodes.parquet",
    "pump_v1/features.parquet",
    "pump_v1/events.parquet",
    "pump_v1/episodes.parquet",
)
REVIEW_INPUTS = tuple(
    f"dispatch_review_v2/{period}/{name}.parquet"
    for period in ("policy_2024", "diagnostic_2025_2026")
    for name in ("forecast_evidence", "forecast_features", "observed_evidence", "observed_mapping")
)
JSON_INPUTS = (
    "handoff_v1/fire_history_view.json",
    "handoff_v1/feedback_availability.json",
    "handoff_v1/chart_example_index.json",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    raw = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    required = {item["path"] for item in raw["resources"].values()}
    required.update(SCORER_INPUTS)
    required.update(REVIEW_INPUTS)
    required.update(JSON_INPUTS)
    required.add("handoff_v1/schema_manifest.json")
    for scenario in json.loads((ROOT / "production_ml" / "pipeline" / "replay_scenarios_v1.json").read_text(encoding="utf-8")):
        required.add(f"replay_v1/{scenario['id']}/timeline.parquet")
        required.add(f"replay_v1/{scenario['id']}/manifest.json")
    sources = {f"data/{name}": DATA / name for name in required}
    sources["data/catalog/справочник_каналов_датчиков.csv"] = (
        ROOT.parents[1] / "dataset" / "справочник_каналов_датчиков.csv")
    sources["data/catalog/справочник_состояний.csv"] = (
        ROOT.parents[1] / "dataset" / "справочник_состояний.csv")
    for model in ("power_phase_scada_v2", "pump_scada_v1"):
        for source in (ROOT / "production_ml" / "models" / model).iterdir():
            if source.is_file():
                sources[f"models/{model}/{source.name}"] = source
    sources["model_type_decisions.json"] = (ROOT / "production_ml" / "pipeline"
                                             / "model_type_decisions.json")
    sources["replay_scenarios_v1.json"] = (ROOT / "production_ml" / "pipeline"
                                           / "replay_scenarios_v1.json")
    for name in ("USAGE_HANDOFF_V1.txt", "USAGE_DISPATCH_REVIEW_V2.txt",
                 "USAGE_REPLAY_V1.txt", "DEMO_ROUTE_V1.txt"):
        source = ROOT / "production_ml" / "pipeline" / name
        sources[f"docs/{name}"] = source
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    copied = []
    for relative, source in sorted(sources.items()):
        target = BACKEND / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or sha256(target) != sha256(source):
            shutil.copy2(source, target)
        copied.append({"path": relative, "bytes": target.stat().st_size,
                       "sha256": sha256(target)})
    api_source = BACKEND / "api_contract_v1.json"
    api_target = FRONTEND / "api_contract_v1.json"
    api_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(api_source, api_target)
    (FRONTEND / "docs").mkdir(parents=True, exist_ok=True)
    for name in ("USAGE_HANDOFF_V1.txt", "USAGE_REPLAY_V1.txt", "DEMO_ROUTE_V1.txt"):
        shutil.copy2(BACKEND / "docs" / name, FRONTEND / "docs" / name)
    shutil.copy2(BACKEND / "model_type_decisions.json",
                 FRONTEND / "model_type_decisions.json")
    shutil.copy2(BACKEND / "replay_scenarios_v1.json",
                 FRONTEND / "replay_scenarios_v1.json")
    shutil.copy2(BACKEND / "ARCHITECTURE_V1.txt",
                 FRONTEND / "ARCHITECTURE_V1.txt")
    shutil.copy2(BACKEND / "runtime_policy_v1.json",
                 FRONTEND / "runtime_policy_v1.json")
    package = {
        "package_version": "dispatcher_integration_v1",
        "data_cutoff": raw["data_cutoff"],
        "handoff_schema_version": raw["schema_version"],
        "api_contract_sha256": sha256(api_source),
        "files": copied,
    }
    (BACKEND / "data" / "package_manifest.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(copied), "bytes": sum(x["bytes"] for x in copied),
                      "api_contract_sha256": package["api_contract_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
