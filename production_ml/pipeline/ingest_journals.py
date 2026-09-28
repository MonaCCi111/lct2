"""Проверяемая конвертация журналов CSV в Parquet без молчаливых подмен."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


YEARS = tuple(range(2019, 2027))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "source_v2")
    parser.add_argument("--years", type=int, nargs="+", default=YEARS)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output / 'duckdb_temp').as_posix()}'")

    unknown_years=sorted(set(args.years)-set(YEARS))
    if unknown_years:
        raise ValueError(f"Неподдерживаемые годы: {unknown_years}")
    for year in args.years:
        source = args.source_root / "dataset" / f"ext-journal-{year}.csv"
        target = args.output / f"journal_{year}.parquet"
        if not source.exists():
            raise FileNotFoundError(source)
        con.execute("DROP TABLE IF EXISTS raw")
        con.execute("DROP TABLE IF EXISTS classified")
        con.execute("DROP TABLE IF EXISTS accepted")
        con.execute(f"""
        CREATE TABLE raw AS
        SELECT * FROM read_csv(
            '{source.as_posix()}', header=true, all_varchar=true,
            strict_mode=true
        )
        """)
        con.execute("""
        CREATE TABLE classified AS
        WITH parsed AS (
            SELECT *,
                   TRY_CAST("ид_события" AS BIGINT) event_id,
                   TRY_CAST("ид_канала_данных" AS BIGINT) channel_id,
                   TRY_CAST(trim("дата") || ' ' || trim("время") AS TIMESTAMP) event_time,
                   lower(trim("тревожное")) alarm_text
            FROM raw
        )
        SELECT *,
               CASE WHEN alarm_text IN ('t','true','1') THEN true
                    WHEN alarm_text IN ('f','false','0') THEN false
                    ELSE NULL END is_alarm,
               CASE WHEN lower(trim("дата"))='дата' THEN 'REPEATED_HEADER'
                    WHEN event_id IS NULL THEN 'INVALID_EVENT_ID'
                    WHEN channel_id IS NULL THEN 'INVALID_CHANNEL_ID'
                    WHEN event_time IS NULL THEN 'INVALID_EVENT_TIME'
                    WHEN alarm_text NOT IN ('t','true','1','f','false','0') THEN 'UNKNOWN_ALARM'
                    ELSE 'VALID' END row_status
        FROM parsed
        """)
        conflicts = con.execute("""
            SELECT count(*) FROM (
                SELECT event_id
                FROM classified WHERE row_status='VALID'
                GROUP BY event_id
                HAVING count(DISTINCT concat_ws('|',channel_id,event_time,is_alarm,"значение_датчика"))>1
            )
        """).fetchone()[0]
        con.execute("""
        CREATE TABLE accepted AS
        WITH valid AS (
            SELECT event_id,channel_id,event_time,is_alarm,
                   CAST("значение_датчика" AS VARCHAR) sensor_value,
                   row_number() OVER (
                       PARTITION BY event_id,channel_id,event_time,is_alarm,"значение_датчика"
                       ORDER BY event_id
                   ) exact_copy
            FROM classified WHERE row_status='VALID'
        )
        SELECT event_id,channel_id,event_time,is_alarm,sensor_value
        FROM valid WHERE exact_copy=1
        """)
        con.execute(f"COPY accepted TO '{target.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        statuses = dict(con.execute("SELECT row_status,count(*) FROM classified GROUP BY 1").fetchall())
        accepted = con.execute("SELECT count(*) FROM accepted").fetchone()[0]
        valid = statuses.get("VALID", 0)
        result = {
            "year": year,
            "source_rows": sum(statuses.values()),
            "accepted_rows": accepted,
            "exact_duplicate_rows_removed": valid - accepted,
            "reused_event_ids_with_different_content": conflicts,
            "row_status": statuses,
            "output": str(target),
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
