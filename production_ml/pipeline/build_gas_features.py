"""Рассчитать прошлые числовые окна газовых каналов по часовым фактам."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "gas_v1")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "gas_v1"
                        / "features.parquet")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = args.input / "hourly_*.parquet"
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{(args.output.parent / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
        COPY (
            WITH windows AS (
                SELECT channel_id,object_id,obs_time,numeric_count,distinct_event_times,
                       negative_count,numeric_min,numeric_median,numeric_mean,numeric_max,
                       count(*) OVER recent_window recent_observed_hours,
                       sum(numeric_count) OVER recent_window recent_numeric_count,
                       median(numeric_median) OVER recent_window recent_hourly_median,
                       max(numeric_max) OVER recent_window recent_max,
                       count(*) OVER baseline_window baseline_observed_hours,
                       sum(numeric_count) OVER baseline_window baseline_numeric_count,
                       median(numeric_median) OVER baseline_window baseline_hourly_median,
                       sum(negative_count) OVER baseline_window baseline_negative_count
                FROM read_parquet('{source.as_posix()}')
                WINDOW recent_window AS (
                    PARTITION BY channel_id ORDER BY obs_time
                    RANGE BETWEEN INTERVAL 5 HOUR PRECEDING AND CURRENT ROW
                ), baseline_window AS (
                    PARTITION BY channel_id ORDER BY obs_time
                    RANGE BETWEEN INTERVAL 72 HOUR PRECEDING AND INTERVAL 6 HOUR PRECEDING
                )
            )
            SELECT *,recent_hourly_median-baseline_hourly_median median_delta
            FROM windows
        ) TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)
    """)
    result = con.execute(f"""
        SELECT count(*) feature_rows,count(DISTINCT channel_id) channels,
               count(*) FILTER(WHERE baseline_observed_hours>0) with_baseline,
               count(*) FILTER(WHERE recent_observed_hours>0) with_recent,
               min(obs_time) first_time,max(obs_time) last_time
        FROM read_parquet('{args.output.as_posix()}')
    """)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                     ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
