"""Вывести факты о газовых каналах из очищенного журнала."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def emit(con, name, query):
    result = con.execute(query)
    print(json.dumps({"probe": name, "columns": [d[0] for d in result.description],
                      "rows": result.fetchall()}, ensure_ascii=False, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--catalog-only", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    channels = root / "dataset" / "справочник_каналов_датчиков.csv"
    paths = [root / "production_ml" / "data" / "source_v2" / f"journal_{y}.parquet"
             for y in range(args.start_year, args.end_year + 1)]
    for path in [channels, *paths]:
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(root / 'duckdb_temp').as_posix()}'")
    emit(con, "gas_type_names", f"""
        SELECT "тип_датчика",count(*) n FROM read_csv('{channels.as_posix()}',header=true)
        WHERE lower("тип_датчика") LIKE '%газ%'
        GROUP BY 1 ORDER BY n DESC
    """)
    con.execute(f"""
        CREATE TABLE gas_channels AS
        SELECT "ид_канала_данных" channel_id,"ид_объект" object_id,
               "название_датчика" sensor_name
        FROM read_csv('{channels.as_posix()}',header=true)
        WHERE lower("тип_датчика") LIKE '%газ%';
    """)
    emit(con, "catalog", "SELECT count(*) channels,count(DISTINCT object_id) objects FROM gas_channels")
    emit(con, "catalog_names", """
        SELECT sensor_name,count(*) channels FROM gas_channels
        GROUP BY 1 ORDER BY channels DESC LIMIT 25
    """)
    if args.catalog_only:
        return
    sources = ",".join(f"'{path.as_posix()}'" for path in paths)
    con.execute(f"""
        CREATE VIEW gas AS
        SELECT j.channel_id,g.object_id,j.event_time,j.sensor_value,j.is_alarm,
               try_cast(replace(j.sensor_value,',','.') AS DOUBLE) numeric_value
        FROM read_parquet([{sources}]) j JOIN gas_channels g USING(channel_id);
    """)
    emit(con, "annual", """
        SELECT year(event_time) yr,count(*) n_rows,count(DISTINCT channel_id) channels,
               count(DISTINCT object_id) objects,
               count(*) FILTER(WHERE numeric_value IS NOT NULL AND isfinite(numeric_value)) numeric_rows,
               count(*) FILTER(WHERE is_alarm) alarm_rows,
               min(event_time) first_time,max(event_time) last_time
        FROM gas GROUP BY 1 ORDER BY 1
    """)
    emit(con, "non_numeric_values", """
        SELECT sensor_value,is_alarm,count(*) n_rows,count(DISTINCT channel_id) channels
        FROM gas WHERE numeric_value IS NULL OR NOT isfinite(numeric_value)
        GROUP BY 1,2 ORDER BY n_rows DESC LIMIT 30
    """)
    emit(con, "numeric_distribution", """
        SELECT count(*) n_rows,min(numeric_value) min_value,max(numeric_value) max_value,
               quantile_cont(numeric_value,[0.001,0.01,0.1,0.5,0.9,0.99,0.999]) quantiles,
               count(*) FILTER(WHERE numeric_value<0) negative_rows,
               count(*) FILTER(WHERE is_alarm) alarm_rows
        FROM gas WHERE numeric_value IS NOT NULL AND isfinite(numeric_value)
    """)
    emit(con, "top_channels", """
        SELECT channel_id,object_id,count(*) n_rows,min(event_time) first_time,
               max(event_time) last_time,count(*) FILTER(WHERE is_alarm) alarm_rows,
               count(*) FILTER(WHERE numeric_value IS NULL OR NOT isfinite(numeric_value)) non_numeric_rows,
               min(numeric_value) min_value,max(numeric_value) max_value
        FROM gas GROUP BY 1,2 ORDER BY n_rows DESC LIMIT 15
    """)


if __name__ == "__main__":
    main()
