"""Сформировать очередь черновиков активных моделей без суточной квоты."""

import argparse
import json
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd

from .active import ACTIVE_MODELS
from .package_power_phase_v2 import verify_bundle as verify_phase_bundle
from .package_pump import verify_bundle as verify_pump_bundle


OUTPUT_COLUMNS = (
    "draft_id", "channel_id", "obs_time", "score", "model_version",
    "forecast_horizon_hours", "target_kind", "review_status",
)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase-scores",type=Path,required=True)
    parser.add_argument("--pump-scores",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.phase_scores,args.pump_scores):
        if not path.exists():
            raise FileNotFoundError(path)
    phase_bundle=ACTIVE_MODELS["power_phase_scada_v2"]["bundle"]
    pump_bundle=ACTIVE_MODELS["pump_scada_v1"]["bundle"]
    verify_phase_bundle(phase_bundle)
    verify_pump_bundle(pump_bundle)
    phase_policy=json.loads((phase_bundle/"policy.json").read_text(encoding="utf-8"))
    pump_policy=json.loads((pump_bundle/"policy.json").read_text(encoding="utf-8"))
    if phase_policy["channel_cooldown_hours"]!=pump_policy["channel_cooldown_hours"]:
        raise ValueError("Активные политики имеют разные паузы канала")
    con=duckdb.connect()
    candidates=con.execute(f"""
        SELECT channel_id,obs_time,score,
               'power_phase_scada_v2' model_version,
               'SCADA_STATUS_EPISODE' target_kind
        FROM read_parquet('{args.phase_scores.as_posix()}') WHERE score>=?
        UNION ALL
        SELECT channel_id,obs_time,score,
               'pump_scada_v1' model_version,
               'SCADA_PUMP_ALARM' target_kind
        FROM read_parquet('{args.pump_scores.as_posix()}') WHERE score>=?
        ORDER BY obs_time,score DESC,model_version,channel_id
    """,[phase_policy["score_threshold"],pump_policy["score_threshold"]]).fetchall()
    cooldown=timedelta(hours=phase_policy["channel_cooldown_hours"])
    last={}
    selected=[]
    daily=Counter()
    for channel_id,obs_time,score,model_version,target_kind in candidates:
        key=(model_version,channel_id)
        if key in last and obs_time<last[key]+cooldown:
            continue
        draft_id=f"{model_version}:{channel_id}:{obs_time:%Y%m%dT%H%M%S}"
        selected.append((draft_id,channel_id,obs_time,float(score),model_version,
                         48,target_kind,"draft"))
        last[key]=obs_time
        daily[obs_time.date()]+=1
    frame=pd.DataFrame(selected,columns=OUTPUT_COLUMNS)
    if frame.empty:
        frame=pd.DataFrame({
          "draft_id":pd.Series(dtype="string"),
          "channel_id":pd.Series(dtype="int64"),
          "obs_time":pd.Series(dtype="datetime64[ns]"),
          "score":pd.Series(dtype="float64"),
          "model_version":pd.Series(dtype="string"),
          "forecast_horizon_hours":pd.Series(dtype="int64"),
          "target_kind":pd.Series(dtype="string"),
          "review_status":pd.Series(dtype="string"),
        })
    args.output.parent.mkdir(parents=True,exist_ok=True)
    con.register("review_queue",frame)
    con.execute(f"COPY review_queue TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    print(json.dumps({"threshold_candidates":len(candidates),"drafts":len(frame),
                      "days":len(daily),"max_daily":max(daily.values(),default=0),
                      "drafts_by_model":dict(Counter(row[4] for row in selected)),
                      "output":str(args.output)},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
