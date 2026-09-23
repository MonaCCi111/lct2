"""Собрать проверяемый пакет модели из локальных артефактов обучения."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from .model import MODEL_FEATURES


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    source = root / "data" / "power_phase_v1"
    bundle = root / "models" / "power_phase_scada_v1"
    bundle.mkdir(parents=True, exist_ok=True)
    for name in ("model.pkl", "calibrator.pkl", "model_meta.json"):
        shutil.copy2(source / name, bundle / name)
    for name in ("contract.json", "policy.json"):
        shutil.copy2(Path(__file__).with_name(name), bundle / name)
    meta = json.loads((bundle / "model_meta.json").read_text(encoding="utf-8"))
    contract = json.loads((bundle / "contract.json").read_text(encoding="utf-8"))
    policy = json.loads((bundle / "policy.json").read_text(encoding="utf-8"))
    if tuple(meta["model_features"]) != MODEL_FEATURES or tuple(contract["model_inputs"]) != MODEL_FEATURES:
        raise ValueError("Схема модели и контракт не совпадают")
    if len({meta["version"], contract["version"], policy["version"]}) != 1:
        raise ValueError("Версии модели, контракта и политики не совпадают")
    hashes = {}
    for name in ("model.pkl", "calibrator.pkl", "model_meta.json", "contract.json", "policy.json"):
        hashes[name] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    (bundle / "sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps({"bundle": str(bundle), "sha256": hashes}), flush=True)


if __name__ == "__main__":
    main()
