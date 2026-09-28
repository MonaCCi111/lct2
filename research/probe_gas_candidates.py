"""Измерить поток исследовательских газовых подъёмов при заданных уровнях."""

import argparse
import json
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

import duckdb


def evaluate(con, year, threshold):
    rows = con.execute("""
        WITH candidate AS (
            SELECT channel_id,object_id,obs_time,numeric_count,numeric_median,
                   recent_hourly_median,baseline_hourly_median,median_delta,recent_max,
                   recent_observed_hours,baseline_observed_hours
            FROM features WHERE year(obs_time)=? AND recent_observed_hours>=3
              AND baseline_observed_hours>=12 AND median_delta>=?
        ), preceding AS (
            SELECT c.*,a.event_time preceding_alarm_time
            FROM candidate c ASOF LEFT JOIN alarm_times a
              ON c.channel_id=a.channel_id AND c.obs_time>=a.event_time
        )
        SELECT * FROM preceding
        WHERE preceding_alarm_time IS NULL
           OR obs_time>=preceding_alarm_time+INTERVAL 48 HOUR
        ORDER BY obs_time,object_id,channel_id
    """, [year, threshold]).fetchdf()
    selected = []
    last = {}
    for row in rows.itertuples(index=False):
        prior = last.get(row.channel_id)
        if prior is not None and row.obs_time < prior + timedelta(hours=48):
            continue
        selected.append(row)
        last[row.channel_id] = row.obs_time
    if not selected:
        return {"year": year, "threshold": threshold, "raw_candidates": len(rows),
                "selected_channels": 0, "object_cards": 0}
    import pandas as pd
    selected = pd.DataFrame(selected, columns=rows.columns)
    con.register("selected", selected)
    facts = con.execute("""
        WITH future AS (
            SELECT s.*,a.event_time next_alarm_time,a.card_id next_card_id,
                   a.alarm_channels next_card_channels
            FROM selected s ASOF LEFT JOIN alarm_targets a
              ON s.channel_id=a.channel_id AND s.obs_time<a.event_time
        )
        SELECT channel_id,object_id,obs_time,median_delta,recent_max,
               next_alarm_time,next_card_id,next_card_channels,
               (next_alarm_time BETWEEN obs_time+INTERVAL 1 HOUR
                   AND obs_time+INTERVAL 48 HOUR) matched_status
        FROM future ORDER BY object_id,obs_time,channel_id
    """).fetchdf()
    card_ids = []
    last_by_object = {}
    first_by_object = {}
    for row in facts.itertuples(index=False):
        previous = last_by_object.get(row.object_id)
        if previous is None or row.obs_time > previous + timedelta(hours=1):
            first_by_object[row.object_id] = row.obs_time
        card_ids.append(f"{row.object_id}:{first_by_object[row.object_id]:%Y%m%dT%H%M%S}")
        last_by_object[row.object_id] = row.obs_time
    facts["candidate_card_id"] = card_ids
    days = Counter(timestamp.date() for timestamp in facts.obs_time)
    cards = facts.groupby("candidate_card_id", sort=False)
    matched = facts[facts.matched_status.fillna(False)]
    local_matched = matched[matched.next_card_channels < 10]
    return {
        "year": year,
        "threshold": threshold,
        "raw_candidates": len(rows),
        "selected_channels": len(facts),
        "covered_channels": int(facts.channel_id.nunique()),
        "object_cards": int(facts.candidate_card_id.nunique()),
        "active_days": len(days),
        "max_channel_signals_day": max(days.values()),
        "days_over_ten_signals": sum(value > 10 for value in days.values()),
        "matched_channel_signals": len(matched),
        "matched_candidate_cards": int(matched.candidate_card_id.nunique()),
        "matched_future_status_cards": int(matched.next_card_id.nunique()),
        "matched_local_channel_signals": len(local_matched),
        "matched_local_candidate_cards": int(local_matched.candidate_card_id.nunique()),
        "median_channels_per_card": float(cards.channel_id.nunique().median()),
        "max_channels_per_card": int(cards.channel_id.nunique().max()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025])
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.05, 0.1, 0.2])
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data = Path(__file__).resolve().parents[1] / "production_ml" / "data" / "gas_v1"
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW features AS SELECT * FROM read_parquet('{(data / 'features.parquet').as_posix()}');
        CREATE TABLE alarm_times AS
        SELECT channel_id,event_time FROM read_parquet('{(data / 'status_events.parquet').as_posix()}')
        WHERE sensor_value='Обнаружен газ' AND is_alarm GROUP BY 1,2;
        CREATE TABLE alarm_targets AS
        SELECT e.channel_id,e.event_time,e.card_id,c.alarm_channels
        FROM read_parquet('{(data / 'alarm_evidence.parquet').as_posix()}') e
        JOIN read_parquet('{(data / 'alarm_cards.parquet').as_posix()}') c USING(card_id);
    """)
    for year in args.years:
        for threshold in args.thresholds:
            print(json.dumps(evaluate(con, year, threshold), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
