"""Собрать пакет v2 и записать переносимые контрольные суммы."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from .model import MODEL_FEATURES


def canonical_json(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")


def verify_bundle(bundle):
    hashes=json.loads((bundle/"sha256.json").read_text(encoding="utf-8"))
    for name,spec in hashes.items():
        content=(bundle/name).read_bytes() if spec["mode"]=="bytes" else canonical_json(bundle/name)
        actual=hashlib.sha256(content).hexdigest()
        if actual!=spec["sha256"]:
            raise ValueError(f"Контрольная сумма не совпадает: {name}")
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root=Path(__file__).resolve().parents[1];source=root/"data"/"power_phase_v2";bundle=root/"models"/"power_phase_scada_v2"
    bundle.mkdir(parents=True,exist_ok=True)
    for name in ("model.pkl","calibrator.pkl","model_meta.json"):shutil.copy2(source/name,bundle/name)
    shutil.copy2(Path(__file__).with_name("contract_v2.json"),bundle/"contract.json")
    shutil.copy2(Path(__file__).with_name("policy_v2.json"),bundle/"policy.json")
    meta=json.loads((bundle/"model_meta.json").read_text(encoding="utf-8"));contract=json.loads((bundle/"contract.json").read_text(encoding="utf-8"));policy=json.loads((bundle/"policy.json").read_text(encoding="utf-8"))
    if tuple(meta["model_features"])!=MODEL_FEATURES or tuple(contract["model_inputs"])!=MODEL_FEATURES:raise ValueError("Схема пакета не совпадает")
    if len({meta["version"],contract["version"],policy["version"]})!=1:raise ValueError("Версии пакета не совпадают")
    hashes={}
    for name in ("model.pkl","calibrator.pkl"):
        hashes[name]={"mode":"bytes","sha256":hashlib.sha256((bundle/name).read_bytes()).hexdigest()}
    for name in ("model_meta.json","contract.json","policy.json"):
        hashes[name]={"mode":"canonical_json","sha256":hashlib.sha256(canonical_json(bundle/name)).hexdigest()}
    (bundle/"sha256.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
    verify_bundle(bundle)
    print(json.dumps({"bundle":str(bundle),"hashes":hashes}),flush=True)


if __name__ == "__main__":main()
