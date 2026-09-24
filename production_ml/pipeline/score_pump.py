"""Пакетный инференс pump_scada_v1."""

import argparse
import json
import pickle
import sys
from pathlib import Path

import duckdb
import pandas as pd

from .package_pump import verify_bundle
from .pump_model import MODEL_FEATURES, model_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "pump_scada_v1",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data = Path(__file__).resolve().parents[1] / "data" / "pump_v1"
    verify_bundle(args.bundle)
    contract = json.loads((args.bundle / "contract.json").read_text(encoding="utf-8"))
    meta = json.loads((args.bundle / "model_meta.json").read_text(encoding="utf-8"))
    if contract["version"] != meta["version"]:
        raise ValueError("Версия контракта не совпадает с моделью")
    if tuple(contract["model_inputs"]) != MODEL_FEATURES:
        raise ValueError("Схема контракта не совпадает с кодом")
    if tuple(meta["model_features"]) != MODEL_FEATURES:
        raise ValueError("Схема модели не совпадает с кодом")
    with (args.bundle / "model.pkl").open("rb") as handle:
        model = pickle.load(handle)
    with (args.bundle / "calibrator.pkl").open("rb") as handle:
        calibrator = pickle.load(handle)
    con = duckdb.connect()
    columns = ",".join(f'f."{name}"' for name in MODEL_FEATURES)
    frame = con.execute(f"""
        WITH bounds AS (
            SELECT channel_id,min(event_time) first_event_time
            FROM read_parquet('{(data / 'events.parquet').as_posix()}')
            GROUP BY 1
        ), previous AS (
            SELECT f.*,p.episode_id,p.recovery_time,b.first_event_time
            FROM read_parquet('{(data / 'features.parquet').as_posix()}') f
            JOIN bounds b USING(channel_id)
            ASOF LEFT JOIN read_parquet('{(data / 'episodes.parquet').as_posix()}') p
              ON f.channel_id=p.channel_id AND f.obs_time>=p.episode_start
        )
        SELECT {columns},f.channel_id,f.obs_time
        FROM previous f
        WHERE f.obs_time>=? AND f.obs_time<?
          AND f.first_event_time<=f.obs_time-INTERVAL 72 HOUR
          AND f.last_is_alarm=false
          AND (f.episode_id IS NULL OR f.recovery_time<=f.obs_time-INTERVAL 48 HOUR)
        ORDER BY f.obs_time,f.channel_id
    """, [args.start, args.end]).df()
    if frame.empty:
        output = pd.DataFrame({
            "channel_id": pd.Series(dtype="int64"),
            "obs_time": pd.Series(dtype="datetime64[ns]"),
            "score": pd.Series(dtype="float64"),
        })
    else:
        output = frame[["channel_id", "obs_time"]].copy()
        output["score"] = calibrator.transform(
            model.predict_proba(model_frame(frame))[:, 1]
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con.register("pump_scores", output)
    con.execute(f"""
        COPY pump_scores TO '{args.output.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(json.dumps({"rows": len(output), "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()
