"""Извлечь текстовые состояния газовых каналов из очищенного журнала."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "gas_v1"
                        / "status_events.parquet")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    root = args.source_root
    channels = root / "dataset" / "справочник_каналов_датчиков.csv"
    journals = [root / "production_ml" / "data" / "source_v2" / f"journal_{year}.parquet"
                for year in range(2019, 2027)]
    for path in (channels, *journals):
        if not path.exists():
            raise FileNotFoundError(path)
    sources = ",".join(f"'{path.as_posix()}'" for path in journals)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output.parent / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
        CREATE TABLE gas_channels AS
        SELECT "ид_канала_данных" channel_id,"ид_объект" object_id
        FROM read_csv('{channels.as_posix()}',header=true)
        WHERE "тип_датчика"='Газовый датчик';

        CREATE TABLE statuses AS
        SELECT j.event_id,j.channel_id,g.object_id,j.event_time,j.sensor_value,j.is_alarm
        FROM read_parquet([{sources}]) j JOIN gas_channels g USING(channel_id)
        WHERE try_cast(replace(j.sensor_value,',','.') AS DOUBLE) IS NULL
           OR NOT isfinite(try_cast(replace(j.sensor_value,',','.') AS DOUBLE));
    """)
    con.execute(f"COPY statuses TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        SELECT year(event_time) yr,sensor_value,is_alarm,count(*) n,
               count(DISTINCT channel_id) channels,count(DISTINCT object_id) objects
        FROM statuses GROUP BY 1,2,3 ORDER BY 1,2,3
    """)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
