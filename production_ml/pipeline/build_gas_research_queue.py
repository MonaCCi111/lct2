"""Собрать исследовательскую очередь числовых подъёмов газа без нарядов."""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--median-delta", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    data = Path(__file__).resolve().parents[1] / "data" / "gas_v1"
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW features AS SELECT * FROM read_parquet('{(data / 'features.parquet').as_posix()}');
        CREATE TABLE alarm_times AS
        SELECT channel_id,event_time
        FROM read_parquet('{(data / 'status_events.parquet').as_posix()}')
        WHERE sensor_value='Обнаружен газ' AND is_alarm GROUP BY 1,2;
    """)
    candidates = con.execute("""
        WITH eligible AS (
            SELECT channel_id,object_id,obs_time,numeric_count,
                   numeric_min,numeric_median,numeric_max,
                   recent_observed_hours,recent_numeric_count,recent_hourly_median,
                   recent_max,baseline_observed_hours,baseline_numeric_count,
                   baseline_hourly_median,median_delta
            FROM features
            WHERE year(obs_time)=? AND recent_observed_hours>=3
              AND baseline_observed_hours>=12 AND median_delta>=?
        ), previous AS (
            SELECT e.*,a.event_time previous_alarm_time
            FROM eligible e ASOF LEFT JOIN alarm_times a
              ON e.channel_id=a.channel_id AND e.obs_time>=a.event_time
        )
        SELECT * FROM previous
        WHERE previous_alarm_time IS NULL
           OR obs_time>=previous_alarm_time+INTERVAL 48 HOUR
        ORDER BY obs_time,object_id,channel_id
    """, [args.year, args.median_delta]).df()
    selected = []
    last_channel = {}
    for row in candidates.itertuples(index=False):
        prior = last_channel.get(row.channel_id)
        if prior is not None and row.obs_time < prior + timedelta(hours=48):
            continue
        selected.append(row)
        last_channel[row.channel_id] = row.obs_time
    signals = pd.DataFrame(selected, columns=candidates.columns)
    if signals.empty:
        signals["card_id"] = pd.Series(dtype="string")
    else:
        ordered = signals.sort_values(["object_id", "obs_time", "channel_id"]).index
        card_ids = {}
        last_object = {}
        first_object = {}
        for index in ordered:
            row = signals.loc[index]
            object_id = row["object_id"]
            time = row["obs_time"]
            previous = last_object.get(object_id)
            if previous is None or time > previous + timedelta(hours=1):
                first_object[object_id] = time
            card_ids[index] = f"GAS_RISE:{object_id}:{first_object[object_id]:%Y%m%dT%H%M%S}"
            last_object[object_id] = time
        signals["card_id"] = pd.Series(card_ids)
    con.register("signals", signals)
    con.execute("""
        CREATE TABLE cards AS
        SELECT card_id,object_id,min(obs_time) first_signal_time,
               max(obs_time) last_signal_time,count(*) signal_count,
               count(DISTINCT channel_id) channel_count,
               max(median_delta) maximum_median_delta,
               max(recent_max) maximum_recent_value,
               min(baseline_hourly_median) minimum_baseline_median,
               'UNVERIFIED_NUMERIC_RISE' candidate_kind,
               'research' review_status
        FROM signals GROUP BY 1,2;
    """)
    for name in ("signals", "cards"):
        path = args.output / f"{name}.parquet"
        con.execute(f"COPY {name} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        WITH daily AS (
            SELECT cast(first_signal_time AS DATE) d,count(*) n
            FROM cards GROUP BY 1
        )
        SELECT (SELECT count(*) FROM signals) channel_signals,
               (SELECT count(DISTINCT channel_id) FROM signals) channels,
               (SELECT count(*) FROM cards) cards,
               (SELECT max(n) FROM daily) max_daily_cards,
               (SELECT count(*) FROM daily WHERE n>10) days_over_ten_cards
    """)
    print(json.dumps({"year": args.year, "median_delta": args.median_delta,
                      "output": str(args.output), "columns": [d[0] for d in result.description],
                      "rows": result.fetchall()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
