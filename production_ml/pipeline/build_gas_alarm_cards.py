"""Собрать проверяемые карточки наблюдавшихся газовых тревог."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "gas_v1")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    status = args.input / "status_events.parquet"
    features = args.input / "features.parquet"
    for path in (status, features):
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute(f"SET temp_directory='{(args.input / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
        CREATE VIEW status AS SELECT * FROM read_parquet('{status.as_posix()}');
        CREATE VIEW features AS SELECT * FROM read_parquet('{features.as_posix()}');

        CREATE TABLE alarm_times AS
        SELECT channel_id,object_id,event_time
        FROM status
        WHERE sensor_value='Обнаружен газ' AND is_alarm
        GROUP BY 1,2,3;

        CREATE TABLE numbered AS
        WITH ordered AS (
            SELECT *,lag(event_time) OVER (
                PARTITION BY object_id ORDER BY event_time,channel_id
            ) previous_object_time
            FROM alarm_times
        )
        SELECT *,sum(CASE WHEN previous_object_time IS NULL
                               OR event_time>previous_object_time+INTERVAL 1 HOUR
                          THEN 1 ELSE 0 END) OVER (
            PARTITION BY object_id ORDER BY event_time,channel_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) burst_number
        FROM ordered;

        CREATE TABLE bursts AS
        SELECT object_id,burst_number,min(event_time) first_alarm_time,
               max(event_time) last_alarm_time,
               concat(object_id::VARCHAR,':',strftime(min(event_time),'%Y%m%dT%H%M%S')) card_id
        FROM numbered GROUP BY 1,2;

        CREATE TABLE status_times AS
        SELECT channel_id,event_time,count(DISTINCT sensor_value) status_kinds,
               bool_or(is_alarm) any_alarm,bool_and(is_alarm) all_alarm
        FROM status GROUP BY 1,2;

        CREATE TABLE alarm_evidence AS
        WITH previous_numeric AS (
            SELECT a.channel_id,a.object_id,a.event_time,a.burst_number,
                   f.obs_time numeric_obs_time,f.numeric_count,f.numeric_min,
                   f.numeric_median,f.numeric_max,f.recent_observed_hours,
                   f.baseline_observed_hours,f.recent_numeric_count,
                   f.baseline_numeric_count,f.recent_hourly_median,
                   f.baseline_hourly_median,f.median_delta,f.recent_max
            FROM numbered a ASOF LEFT JOIN features f
              ON a.channel_id=f.channel_id AND a.event_time>=f.obs_time
        )
        SELECT b.card_id,p.channel_id,p.object_id,p.event_time,p.numeric_obs_time,
               epoch(p.event_time-p.numeric_obs_time)/3600.0 numeric_age_hours,
               p.numeric_count,p.numeric_min,p.numeric_median,p.numeric_max,
               p.recent_observed_hours,p.baseline_observed_hours,
               p.recent_numeric_count,p.baseline_numeric_count,
               p.recent_hourly_median,p.baseline_hourly_median,p.median_delta,p.recent_max,
               t.status_kinds,(t.any_alarm AND NOT t.all_alarm) mixed_status_at_time
        FROM previous_numeric p
        JOIN bursts b USING(object_id,burst_number)
        JOIN status_times t USING(channel_id,event_time);

        CREATE TABLE alarm_cards AS
        SELECT e.card_id,e.object_id,min(e.event_time) first_alarm_time,
               max(e.event_time) last_alarm_time,count(*) alarm_records,
               count(DISTINCT e.channel_id) alarm_channels,
               count(DISTINCT e.channel_id) FILTER(
                   WHERE e.numeric_age_hours BETWEEN 0 AND 24) numeric_channels_24h,
               count(DISTINCT e.channel_id) FILTER(
                   WHERE e.numeric_age_hours BETWEEN 0 AND 24
                     AND e.recent_observed_hours>0 AND e.baseline_observed_hours>0)
                   comparable_numeric_channels_24h,
               count(*) FILTER(WHERE e.mixed_status_at_time) mixed_status_records,
               max(e.recent_max) FILTER(WHERE e.numeric_age_hours BETWEEN 0 AND 24)
                   maximum_recent_numeric,
               'OBSERVED_GAS_STATUS' card_kind
        FROM alarm_evidence e GROUP BY 1,2;
    """)
    for name in ("alarm_evidence", "alarm_cards"):
        path = args.input / f"{name}.parquet"
        con.execute(f"COPY {name} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        result = con.execute(f"""
            SELECT year({('event_time' if name == 'alarm_evidence' else 'first_alarm_time')}) yr,
                   count(*) n FROM {name} GROUP BY 1 ORDER BY 1
        """)
        print(json.dumps({"output": str(path), "bytes": path.stat().st_size,
                          "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
