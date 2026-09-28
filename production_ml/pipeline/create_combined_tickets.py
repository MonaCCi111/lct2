"""Общий поток заявок активных моделей с единым суточным лимитом."""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd

from .active import ACTIVE_MODELS
from .package_power_phase_v2 import verify_bundle as verify_phase_bundle
from .package_pump import verify_bundle as verify_pump_bundle


OUTPUT_COLUMNS = (
    "ticket_id",
    "channel_id",
    "obs_time",
    "score",
    "model_version",
    "forecast_horizon_hours",
    "target_kind",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-scores", type=Path, required=True)
    parser.add_argument("--pump-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.phase_scores, args.pump_scores):
        if not path.exists():
            raise FileNotFoundError(path)
    phase_bundle = ACTIVE_MODELS["power_phase_scada_v2"]["bundle"]
    pump_bundle = ACTIVE_MODELS["pump_scada_v1"]["bundle"]
    verify_phase_bundle(phase_bundle)
    verify_pump_bundle(pump_bundle)
    phase_policy = json.loads((phase_bundle / "policy.json").read_text(encoding="utf-8"))
    pump_policy = json.loads((pump_bundle / "policy.json").read_text(encoding="utf-8"))
    limits = {
        (policy["daily_ticket_limit"], policy["channel_cooldown_hours"])
        for policy in (phase_policy, pump_policy)
    }
    if len(limits) != 1:
        raise ValueError("Активные политики имеют разные лимиты")
    daily_limit, cooldown_hours = limits.pop()
    con = duckdb.connect()
    candidates = con.execute(f"""
        SELECT channel_id,obs_time,score,
               'power_phase_scada_v2' model_version,
               'SCADA_STATUS_EPISODE' target_kind
        FROM read_parquet('{args.phase_scores.as_posix()}')
        WHERE score>=?
        UNION ALL
        SELECT channel_id,obs_time,score,
               'pump_scada_v1' model_version,
               'SCADA_PUMP_ALARM' target_kind
        FROM read_parquet('{args.pump_scores.as_posix()}')
        WHERE score>=?
        ORDER BY obs_time,score DESC,model_version,channel_id
    """, [phase_policy["score_threshold"], pump_policy["score_threshold"]]).fetchall()
    last_ticket = {}
    daily_count = {}
    selected = []
    cooldown = timedelta(hours=cooldown_hours)
    for channel_id, obs_time, score, model_version, target_kind in candidates:
        day = obs_time.date()
        key = (model_version, channel_id)
        if daily_count.get(day, 0) >= daily_limit:
            continue
        if key in last_ticket and obs_time < last_ticket[key] + cooldown:
            continue
        selected.append((
            len(selected),
            channel_id,
            obs_time,
            float(score),
            model_version,
            48,
            target_kind,
        ))
        daily_count[day] = daily_count.get(day, 0) + 1
        last_ticket[key] = obs_time
    frame = pd.DataFrame(selected, columns=OUTPUT_COLUMNS)
    if frame.empty:
        frame = pd.DataFrame({
            "ticket_id": pd.Series(dtype="int64"),
            "channel_id": pd.Series(dtype="int64"),
            "obs_time": pd.Series(dtype="datetime64[ns]"),
            "score": pd.Series(dtype="float64"),
            "model_version": pd.Series(dtype="string"),
            "forecast_horizon_hours": pd.Series(dtype="int64"),
            "target_kind": pd.Series(dtype="string"),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con.register("combined_tickets", frame)
    con.execute(f"""
        COPY combined_tickets TO '{args.output.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    by_model = frame.groupby("model_version", observed=True).size().to_dict()
    print(json.dumps({
        "input_candidates": len(candidates),
        "tickets": len(frame),
        "tickets_by_model": by_model,
        "days": len(daily_count),
        "max_daily": max(daily_count.values(), default=0),
        "days_at_limit": sum(count == daily_limit for count in daily_count.values()),
        "output": str(args.output),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
