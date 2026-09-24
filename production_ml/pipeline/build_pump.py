"""Собрать признаки и метки pump_scada_v1."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from .pump_episodes import episode_sql
from .pump_features import FEATURES, event_and_feature_sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "pump_v1",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source_root / "production_ml" / "data" / "source_v2"
    journals = [source / f"journal_{year}.parquet" for year in range(2019, 2027)]
    channels = Path(__file__).resolve().parents[2] / "dataset" / "справочник_каналов_датчиков.csv"
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
    CREATE TABLE pump_channel_bounds AS
    SELECT channel_id,min(event_time) first_event_time,max(event_time) last_event_time
    FROM pump_events GROUP BY 1;

    CREATE TABLE pump_labels AS
    WITH previous_episode AS (
        SELECT f.*,p.episode_id previous_episode_id,p.episode_start previous_episode_start,
               p.recovery_time previous_recovery_time,b.first_event_time,b.last_event_time
        FROM pump_features f
        JOIN pump_channel_bounds b USING(channel_id)
        ASOF LEFT JOIN pump_episodes p
          ON f.channel_id=p.channel_id AND f.obs_time>=p.episode_start
    ), next_episode AS (
        SELECT p.*,n.episode_id target_episode_id_raw,n.episode_start target_episode_start
        FROM previous_episode p
        ASOF LEFT JOIN pump_episodes n
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
    artifacts = {
        "events": "pump_events",
        "episodes": "pump_episodes",
        "features": "pump_features",
        "labels": "pump_labels",
    }
    for name, table in artifacts.items():
        path = args.output / f"{name}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(json.dumps({"artifact": name, "rows": rows, "bytes": path.stat().st_size}), flush=True)
    facts = con.execute("""
        SELECT count(*) FILTER(WHERE operational_eligible) operational_rows,
               count(*) FILTER(WHERE training_eligible) training_rows,
               count(*) FILTER(WHERE training_eligible AND target_1_48h=1) positives,
               count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows
        FROM pump_labels
    """).fetchone()
    print(json.dumps({"features": FEATURES, "label_facts": facts}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
