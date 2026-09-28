"""Последовательно сформировать диагностические заявки из баллов v2."""

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

from .active import BUNDLE, MODEL_VERSION
from .alerts import load_policy, select_alerts
from .package_power_phase_v2 import verify_bundle


OUTPUT_COLUMNS = (
    "ticket_id", "channel_id", "obs_time", "score", "model_version",
    "forecast_horizon_hours", "target_kind",
)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scores",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();sys.stdout.reconfigure(encoding="utf-8")
    if not args.scores.exists():raise FileNotFoundError(args.scores)
    verify_bundle(BUNDLE)
    policy=load_policy(BUNDLE/"policy.json")
    if policy["version"]!=MODEL_VERSION:raise ValueError("Версия политики не совпадает с активной моделью")
    con=duckdb.connect()
    candidates=con.execute(f"""
        SELECT channel_id,obs_time,score
        FROM read_parquet('{args.scores.as_posix()}')
        WHERE score>=?
        ORDER BY obs_time,score DESC,channel_id
    """,[policy["score_threshold"]]).fetchall()
    selected,daily=select_alerts(candidates,policy)
    rows=[(ticket_id,channel_id,obs_time,score,MODEL_VERSION,48,"SCADA_STATUS_EPISODE")
          for ticket_id,channel_id,obs_time,score in selected]
    frame=pd.DataFrame(rows,columns=OUTPUT_COLUMNS)
    if frame.empty:
        frame=pd.DataFrame({"ticket_id":pd.Series(dtype="int64"),"channel_id":pd.Series(dtype="int64"),
                            "obs_time":pd.Series(dtype="datetime64[ns]"),"score":pd.Series(dtype="float64"),
                            "model_version":pd.Series(dtype="string"),"forecast_horizon_hours":pd.Series(dtype="int64"),
                            "target_kind":pd.Series(dtype="string")})
    args.output.parent.mkdir(parents=True,exist_ok=True);con.register("tickets",frame)
    con.execute(f"COPY tickets TO '{args.output.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    print(json.dumps({"model_version":MODEL_VERSION,"input_candidates":len(candidates),"tickets":len(frame),
                      "days":len(daily),"days_at_limit":sum(n==policy["daily_ticket_limit"] for n in daily.values()),
                      "output_columns":OUTPUT_COLUMNS,"output":str(args.output)},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
