"""Собрать признаки и метки ветки состояния вентилятора."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from .fan_episodes import episode_sql
from .fan_features import FEATURES, event_and_feature_sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "fan_v1")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source_root / "production_ml" / "data" / "source_v2"
    journals = [source / f"journal_{year}.parquet" for year in range(2019, 2027)]
    channels = args.source_root / "dataset" / "справочник_каналов_датчиков.csv"
    for path in (*journals, channels):
        if not path.exists():
            raise FileNotFoundError(path)

    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output / 'duckdb_temp').as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(event_and_feature_sql(journals, channels))
    con.execute(episode_sql())
    con.execute("""
    CREATE TABLE fan_channel_bounds AS
    SELECT channel_id,min(event_time) first_event_time,max(event_time) last_event_time
    FROM fan_clear_events GROUP BY 1;

    CREATE TABLE fan_labels AS
    WITH previous_episode AS (
        SELECT f.*,p.episode_id previous_episode_id,p.episode_start previous_episode_start,
               p.recovery_time previous_recovery_time,b.first_event_time,b.last_event_time
        FROM fan_features f
        JOIN fan_channel_bounds b USING(channel_id)
        ASOF LEFT JOIN fan_episodes p
          ON f.channel_id=p.channel_id AND f.obs_time>=p.episode_start
    ), next_episode AS (
        SELECT p.*,n.episode_id target_episode_id_raw,n.episode_start target_episode_start
        FROM previous_episode p
        ASOF LEFT JOIN fan_episodes n
          ON p.channel_id=n.channel_id AND p.obs_time<n.episode_start
    ), eligibility AS (
        SELECT *,
               CASE WHEN first_event_time<=obs_time-INTERVAL 72 HOUR
                          AND last_is_alarm=false
                          AND (previous_episode_id IS NULL OR previous_recovery_time<=obs_time-INTERVAL 48 HOUR)
                    THEN true ELSE false END operational_eligible,
               CASE WHEN last_event_time>=obs_time+INTERVAL 48 HOUR THEN true ELSE false END future_observed
        FROM next_episode
    )
    SELECT channel_id,obs_time,operational_eligible,future_observed,
           (operational_eligible AND future_observed) training_eligible,
           previous_episode_id,previous_episode_start,previous_recovery_time,
           CASE WHEN operational_eligible AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN 1 ELSE 0 END::TINYINT target_1_48h,
           CASE WHEN operational_eligible AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN target_episode_id_raw END target_episode_id,
           CASE WHEN operational_eligible AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN epoch(target_episode_start-obs_time)/3600.0 END target_lead_hours
    FROM eligibility;
    """)
    for name, table in {
        "events": "fan_events", "clear_events": "fan_clear_events",
        "episodes": "fan_episodes", "features": "fan_features", "labels": "fan_labels",
    }.items():
        path = args.output / f"{name}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(json.dumps({"artifact": name, "rows": rows, "bytes": path.stat().st_size}), flush=True)
    result = con.execute("""
        SELECT year(obs_time) yr,count(*) features,
               count(*) FILTER(WHERE operational_eligible) operational_rows,
               count(*) FILTER(WHERE training_eligible) training_rows,
               count(*) FILTER(WHERE training_eligible AND target_1_48h=1) positives,
               count(DISTINCT concat(channel_id,':',target_episode_id))
                 FILTER(WHERE training_eligible AND target_1_48h=1) unique_target_episodes,
               count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows
        FROM fan_labels GROUP BY 1 ORDER BY 1
    """)
    print(json.dumps({"features": FEATURES, "label_facts": result.fetchall()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
