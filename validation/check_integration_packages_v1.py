"""Проверка двух handoff-папок и скоринга из опубликованного набора."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

from production_ml.pipeline.package_power_phase_v2 import verify_bundle as verify_phase
from production_ml.pipeline.package_pump import verify_bundle as verify_pump


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "integration" / "backend_sanya"
FRONTEND = ROOT / "integration" / "frontend_roma"
DATA = BACKEND / "data"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_contents():
    package = json.loads((DATA / "package_manifest.json").read_text(encoding="utf-8"))
    assert package["package_version"] == "dispatcher_integration_v1"
    assert sha256(BACKEND / "api_contract_v1.json") == package["api_contract_sha256"]
    assert sha256(FRONTEND / "api_contract_v1.json") == package["api_contract_sha256"]
    assert sha256(BACKEND / "ARCHITECTURE_V1.txt") == sha256(FRONTEND / "ARCHITECTURE_V1.txt")
    assert sha256(BACKEND / "runtime_policy_v1.json") == sha256(FRONTEND / "runtime_policy_v1.json")
    for entry in package["files"]:
        path = BACKEND / entry["path"]
        assert path.is_file(), path
        assert path.stat().st_size == entry["bytes"], path
        assert sha256(path) == entry["sha256"], path
    handoff = json.loads((DATA / "handoff_v1" / "schema_manifest.json").read_text(encoding="utf-8"))
    assert handoff["schema_version"] == "ml_handoff_v1"
    assert len(handoff["resources"]) == 14
    for entry in handoff["resources"].values():
        path = DATA / entry["path"]
        assert path.is_file() and sha256(path) == entry["sha256"], path
    api = json.loads((BACKEND / "api_contract_v1.json").read_text(encoding="utf-8"))
    assert api["base_path"] == "/api/v2"
    paths = {(item["method"], item["path"]) for item in api["endpoints"]}
    assert ("POST", "/drafts/{draft_id}/decisions") in paths
    assert ("POST", "/drafts/{draft_id}/decision-corrections") in paths
    assert ("GET", "/drafts") in paths
    assert ("GET", "/objects") in paths
    assert ("POST", "/work-orders") in paths
    assert ("GET", "/replays/{scenario_id}/events") in paths
    assert (DATA / "catalog" / "справочник_объектов_диспетчер.csv").is_file()
    policy = json.loads((BACKEND / "runtime_policy_v1.json").read_text(encoding="utf-8"))
    assert policy["daily_draft_limit"] is None
    assert set(policy["forecast_models"]) == {"power_phase_scada_v2", "pump_scada_v1"}
    verify_phase(BACKEND / "models" / "power_phase_scada_v2")
    verify_pump(BACKEND / "models" / "pump_scada_v1")
    scenarios = json.loads((BACKEND / "replay_scenarios_v1.json").read_text(encoding="utf-8"))
    assert len(scenarios) == 8
    for item in scenarios:
        assert (DATA / "replay_v1" / item["id"] / "timeline.parquet").is_file()
    fixtures = json.loads((FRONTEND / "fixtures_v1.json").read_text(encoding="utf-8"))
    assert fixtures["GET /api/v2/meta"]["live_ingestion_available"] is False
    assert fixtures["GET /api/v2/fire-history"]["real_fire_count"] is None
    forecast = fixtures["GET /api/v2/drafts?basis_kind=forecast"]["items"][0]
    assert forecast["score"] is not None
    assert forecast["model_version"] == "power_phase_scada_v2"
    assert forecast["forecast_horizon_hours"] == 48
    assert fixtures["GET /api/v2/objects/{object_id}"]["object_name"]
    print(f"OK файлы и SHA256: {len(package['files'])}, ресурсы: 14, replay: 8")


def verify_scores():
    con = duckdb.connect()
    with tempfile.TemporaryDirectory(prefix="package_score_", dir=ROOT / "production_ml" / "data") as dirname:
        temp = Path(dirname)
        for model, module, bundle in (
            ("phase", "production_ml.pipeline.score_power_phase_v2", "power_phase_scada_v2"),
            ("pump", "production_ml.pipeline.score_pump", "pump_scada_v1"),
        ):
            originals = temp / f"{model}_original.parquet"
            portable = temp / f"{model}_package.parquet"
            base = [sys.executable, "-m", module, "--start", "2024-10-01",
                    "--end", "2024-10-03"]
            subprocess.run([*base, "--output", str(originals)], cwd=ROOT,
                           check=True, capture_output=True)
            subprocess.run([*base, "--output", str(portable),
                            "--data-root", str(DATA),
                            "--bundle", str(BACKEND / "models" / bundle)],
                           cwd=ROOT, check=True, capture_output=True)
            left = f"read_parquet('{originals.as_posix()}')"
            right = f"read_parquet('{portable.as_posix()}')"
            missing = con.execute(f"SELECT count(*) FROM ((SELECT * FROM {left}) EXCEPT ALL (SELECT * FROM {right}))").fetchone()[0]
            extra = con.execute(f"SELECT count(*) FROM ((SELECT * FROM {right}) EXCEPT ALL (SELECT * FROM {left}))").fetchone()[0]
            assert missing == extra == 0, (model, missing, extra)
            rows = con.execute(f"SELECT count(*) FROM {right}").fetchone()[0]
            print(f"OK {model}: исходный и переносимый скоринг совпали, строк {rows}")
    con.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    verify_contents()
    verify_scores()


if __name__ == "__main__":
    main()
