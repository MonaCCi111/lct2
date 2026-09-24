"""Собрать и проверить пакет pump_scada_v1."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from .pump_features import PUMP_STATUSES
from .pump_model import MODEL_FEATURES


def canonical_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def verify_bundle(bundle):
    hashes = json.loads((bundle / "sha256.json").read_text(encoding="utf-8"))
    for name, spec in hashes.items():
        if spec["mode"] == "bytes":
            content = (bundle / name).read_bytes()
        else:
            content = canonical_json(bundle / name)
        actual = hashlib.sha256(content).hexdigest()
        if actual != spec["sha256"]:
            raise ValueError(f"Контрольная сумма не совпадает: {name}")
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    source = root / "data" / "pump_v1"
    bundle = root / "models" / "pump_scada_v1"
    bundle.mkdir(parents=True, exist_ok=True)
    for name in ("model.pkl", "calibrator.pkl", "model_meta.json"):
        shutil.copy2(source / name, bundle / name)
    shutil.copy2(Path(__file__).with_name("contract_pump.json"), bundle / "contract.json")
    shutil.copy2(Path(__file__).with_name("policy_pump.json"), bundle / "policy.json")
    meta = json.loads((bundle / "model_meta.json").read_text(encoding="utf-8"))
    contract = json.loads((bundle / "contract.json").read_text(encoding="utf-8"))
    policy = json.loads((bundle / "policy.json").read_text(encoding="utf-8"))
    if tuple(meta["model_features"]) != MODEL_FEATURES:
        raise ValueError("Схема метаданных не совпадает с кодом")
    if tuple(meta["status_categories"]) != PUMP_STATUSES:
        raise ValueError("Категории статуса не совпадают с кодом")
    if tuple(contract["model_inputs"]) != MODEL_FEATURES:
        raise ValueError("Схема контракта не совпадает с кодом")
    if len({meta["version"], contract["version"], policy["version"]}) != 1:
        raise ValueError("Версии пакета не совпадают")
    hashes = {}
    for name in ("model.pkl", "calibrator.pkl"):
        hashes[name] = {
            "mode": "bytes",
            "sha256": hashlib.sha256((bundle / name).read_bytes()).hexdigest(),
        }
    for name in ("model_meta.json", "contract.json", "policy.json"):
        hashes[name] = {
            "mode": "canonical_json",
            "sha256": hashlib.sha256(canonical_json(bundle / name)).hexdigest(),
        }
    (bundle / "sha256.json").write_text(
        json.dumps(hashes, indent=2),
        encoding="utf-8",
    )
    verify_bundle(bundle)
    print(json.dumps({"bundle": str(bundle), "hashes": hashes}), flush=True)


if __name__ == "__main__":
    main()
