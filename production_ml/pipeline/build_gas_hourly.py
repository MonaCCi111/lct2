"""Собрать почасовые числовые факты газовых каналов без строк в pandas."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "gas_v1")
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    root = args.source_root
    catalog = root / "dataset" / "справочник_каналов_датчиков.csv"
    if not catalog.exists():
        raise FileNotFoundError(catalog)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{(args.output / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
        CREATE TABLE gas_channels AS
        SELECT "ид_канала_данных" channel_id,"ид_объект" object_id
        FROM read_csv('{catalog.as_posix()}',header=true)
        WHERE "тип_датчика"='Газовый датчик';
    """)
    for year in range(args.start_year, args.end_year + 1):
        source = root / "production_ml" / "data" / "source_v2" / f"journal_{year}.parquet"
        if not source.exists():
            raise FileNotFoundError(source)
        output = args.output / f"hourly_{year}.parquet"
        con.execute(f"""
            COPY (
                WITH parsed AS (
                    SELECT j.channel_id,g.object_id,j.event_time,
                           try_cast(replace(j.sensor_value,',','.') AS DOUBLE) numeric_value
                    FROM read_parquet('{source.as_posix()}') j
                    JOIN gas_channels g USING(channel_id)
                )
                SELECT channel_id,object_id,
                       date_trunc('hour',event_time)+INTERVAL 1 HOUR obs_time,
                       count(*) numeric_count,
                       count(DISTINCT event_time) distinct_event_times,
                       count(*) FILTER(WHERE numeric_value<0) negative_count,
                       min(numeric_value) numeric_min,
                       median(numeric_value) numeric_median,
                       avg(numeric_value) numeric_mean,
                       max(numeric_value) numeric_max
                FROM parsed
                WHERE numeric_value IS NOT NULL AND isfinite(numeric_value)
                GROUP BY 1,2,3
            ) TO '{output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)
        """)
        result = con.execute(f"""
            SELECT count(*) hourly_rows,sum(numeric_count) numeric_rows,
                   count(DISTINCT channel_id) channels,min(obs_time) first_time,
                   max(obs_time) last_time
            FROM read_parquet('{output.as_posix()}')
        """)
        print(json.dumps({"year": year, "output": str(output), "bytes": output.stat().st_size,
                          "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                         ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
