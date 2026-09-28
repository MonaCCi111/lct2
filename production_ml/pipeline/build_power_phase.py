"""Собрать отдельные эпизоды, признаки и метки POWER_PHASE."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from .episodes import episodes_sql, failure_events_sql
from .features import FEATURES, SENSORS, feature_sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "power_phase_v1")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    years = (2020, 2022, 2023, 2024, 2025, 2026)
    journal = [args.source_root / "ml_research" / "data" / "parquet_by_year" / f"journal_{year}.parquet" for year in years]
    hourly = [args.source_root / "production_ml" / "data" / "cache_v6" / f"hourly_{year}.parquet" for year in years]
    channels = Path(__file__).resolve().parents[2] / "dataset" / "справочник_каналов_датчиков.csv"
    for path in (*journal, *hourly, channels):
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output / 'duckdb_temp').as_posix()}'")
    con.execute("SET preserve_insertion_order=false")

    con.execute("CREATE TABLE failure_events AS " + failure_events_sql(journal, channels))
    con.execute("CREATE TABLE episodes AS " + episodes_sql())
    con.execute("CREATE TABLE features AS " + feature_sql(hourly))
    con.execute("""
    CREATE TABLE labels AS
    WITH future_episode AS (
        SELECT f.channel_id, f.obs_time, e.episode_id, e.episode_start,
               epoch(e.episode_start - f.obs_time) / 3600.0 AS lead_hours
        FROM features f
        ASOF LEFT JOIN episodes e
          ON f.channel_id=e.channel_id AND f.obs_time<=e.episode_start
    ), last_event AS (
        SELECT n.*, h.event_time AS last_failure_time
        FROM future_episode n
        ASOF LEFT JOIN failure_events h
          ON n.channel_id=h.channel_id AND n.obs_time>h.event_time
    )
    SELECT channel_id, obs_time,
           CASE WHEN lead_hours BETWEEN 1.0 AND 48.0 THEN 1 ELSE 0 END::TINYINT AS target_1_48h,
           CASE WHEN lead_hours BETWEEN 1.0 AND 48.0 THEN episode_id ELSE NULL END AS target_episode_id,
           CASE WHEN lead_hours BETWEEN 1.0 AND 48.0 THEN lead_hours ELSE NULL END AS target_lead_hours,
           last_failure_time,
           CASE WHEN last_failure_time IS NULL
                     OR last_failure_time < obs_time - INTERVAL 48 HOUR
                THEN true ELSE false END AS eligible
    FROM last_event
    """)
    for name in ("failure_events", "episodes", "features", "labels"):
        path = args.output / f"{name}.parquet"
        con.execute(f"COPY {name} TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(json.dumps({"artifact": name, "rows": count, "bytes": path.stat().st_size}), flush=True)
    print(json.dumps({"sensors": SENSORS, "features": FEATURES}), flush=True)
    print(json.dumps({"labels": con.execute("SELECT count(*) FILTER (WHERE eligible) eligible_rows, count(*) FILTER (WHERE eligible AND target_1_48h=1) positives FROM labels").fetchone()}), flush=True)


if __name__ == "__main__":
    main()
