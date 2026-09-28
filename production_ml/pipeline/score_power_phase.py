"""Пакетный расчёт балла только из наблюдаемой истории канала."""

import argparse
import json
import pickle
import sys
from pathlib import Path

import duckdb

from .model import MODEL_FEATURES, model_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1] / "models" / "power_phase_scada_v1")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "data" / "power_phase_v1"
    with (args.bundle / "model.pkl").open("rb") as handle:
        model = pickle.load(handle)
    with (args.bundle / "calibrator.pkl").open("rb") as handle:
        calibrator = pickle.load(handle)
    meta = json.loads((args.bundle / "model_meta.json").read_text(encoding="utf-8"))
    contract = json.loads((args.bundle / "contract.json").read_text(encoding="utf-8"))
    if tuple(meta["model_features"]) != MODEL_FEATURES:
        raise ValueError("Схема модели расходится с кодом расчёта признаков")
    if tuple(contract["model_inputs"]) != MODEL_FEATURES or contract["version"] != meta["version"]:
        raise ValueError("Контракт пакета расходится с моделью")
    con = duckdb.connect()
    con.execute("SET threads=4")
    columns = ",".join(f'f."{name}"' for name in MODEL_FEATURES)
    frame = con.execute(f"""
        WITH latest_failure AS (
            SELECT f.*, h.event_time AS last_failure_time
            FROM read_parquet('{(data / 'features.parquet').as_posix()}') f
            ASOF LEFT JOIN read_parquet('{(data / 'failure_events.parquet').as_posix()}') h
              ON f.channel_id=h.channel_id AND f.obs_time>h.event_time
        )
        SELECT {columns}, f.channel_id, f.obs_time
        FROM latest_failure f
        WHERE f.obs_time>=? AND f.obs_time<?
          AND (f.last_failure_time IS NULL
               OR f.last_failure_time<f.obs_time-INTERVAL 48 HOUR)
    """, [args.start, args.end]).df()
    raw_score = model.predict_proba(model_frame(frame))[:, 1]
    output = frame[["channel_id", "obs_time"]].copy()
    output["score"] = calibrator.transform(raw_score)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con.register("scored", output)
    con.execute(f"COPY scored TO '{args.output.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    print(json.dumps({"rows": len(output), "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()
