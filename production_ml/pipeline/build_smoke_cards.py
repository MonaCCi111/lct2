"""Свести однозначные дымовые сигналы в карточки одного объекта и пикета."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "smoke_evidence" / "signals.parquet",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "smoke_evidence" / "cards.parquet",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if not args.evidence.exists():
        raise FileNotFoundError(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute(f"SET temp_directory='{(args.output.parent / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
        CREATE VIEW evidence AS
        SELECT * FROM read_parquet('{args.evidence.as_posix()}');

        CREATE TABLE cards AS
        WITH located AS (
            SELECT *,
                   CASE WHEN piket IS NULL OR piket=''
                        THEN concat('channel:',channel_id::VARCHAR)
                        ELSE concat('piket:',piket) END location_key
            FROM evidence
        ), ordered AS (
            SELECT *,lag(event_time) OVER (
                PARTITION BY object_id,location_key ORDER BY event_time,channel_id
            ) previous_time
            FROM located
        ), numbered AS (
            SELECT *,sum(CASE WHEN previous_time IS NULL
                                   OR event_time>previous_time+INTERVAL 15 MINUTE
                              THEN 1 ELSE 0 END) OVER (
                PARTITION BY object_id,location_key ORDER BY event_time,channel_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) incident_number
            FROM ordered
        )
        SELECT concat(object_id::VARCHAR,':',location_key,':',
                      strftime(min(event_time),'%Y%m%dT%H%M%S')) card_id,
               object_id,piket,location_key,min(event_time) first_signal_time,
               max(event_time) last_signal_time,count(*) signal_records,
               count(DISTINCT channel_id) smoke_channels,
               max(object_smoke_channels_15m) max_object_smoke_channels_15m,
               max(location_smoke_channels_15m) max_location_smoke_channels_15m,
               count(*) FILTER(WHERE recent_numeric_count>0) signals_with_recent_temperature,
               count(*) FILTER(WHERE recent_numeric_count>0 AND baseline_numeric_count>0)
                   signals_with_comparable_temperature,
               min(temperature_delta) minimum_temperature_delta,
               median(temperature_delta) median_temperature_delta,
               max(temperature_delta) maximum_temperature_delta,
               max(recent_temp_channels) recent_temperature_channels
        FROM numbered
        GROUP BY object_id,piket,location_key,incident_number;
    """)
    con.execute(f"COPY cards TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        SELECT year(first_signal_time) yr,count(*) cards,sum(signal_records) signals,
               count(*) FILTER(WHERE signals_with_comparable_temperature>0) comparable_cards,
               max(signal_records) max_signal_records
        FROM cards GROUP BY 1 ORDER BY 1
    """)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
