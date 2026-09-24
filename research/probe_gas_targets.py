"""Вывести факты о разделённых газовых тревогах и доступности чисел до них."""

import json
import sys
from pathlib import Path

import duckdb


def emit(con, name, query):
    result = con.execute(query)
    print(json.dumps({"probe": name, "columns": [d[0] for d in result.description],
                      "rows": result.fetchall()}, ensure_ascii=False, default=str), flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = Path(__file__).resolve().parents[1] / "production_ml" / "data" / "gas_v1"
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW status AS SELECT * FROM read_parquet('{(data / 'status_events.parquet').as_posix()}');
        CREATE VIEW hourly AS SELECT * FROM read_parquet('{(data / 'hourly_*.parquet').as_posix()}');
        CREATE TABLE alarm_times AS
        SELECT channel_id,object_id,event_time
        FROM status WHERE sensor_value='Обнаружен газ' AND is_alarm
        GROUP BY 1,2,3;
        CREATE TABLE separated AS
        WITH ordered AS (
            SELECT *,lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time) previous_time
            FROM alarm_times
        )
        SELECT * FROM ordered
        WHERE previous_time IS NULL OR event_time>=previous_time+INTERVAL 48 HOUR;
    """)
    emit(con, "annual", """
        SELECT year(event_time) yr,count(*) separated_alarms,
               count(DISTINCT channel_id) channels,count(DISTINCT object_id) objects,
               count(DISTINCT cast(event_time AS DATE)) calendar_days
        FROM separated GROUP BY 1 ORDER BY 1
    """)
    emit(con, "top_object_days", """
        SELECT cast(event_time AS DATE) d,object_id,count(*) alarms,
               count(DISTINCT channel_id) channels
        FROM separated GROUP BY 1,2 ORDER BY alarms DESC LIMIT 30
    """)
    emit(con, "numeric_coverage", """
        WITH previous AS (
            SELECT a.*,h.obs_time numeric_obs_time,h.numeric_median,h.numeric_max
            FROM separated a ASOF LEFT JOIN hourly h
              ON a.channel_id=h.channel_id AND a.event_time>=h.obs_time
        )
        SELECT year(event_time) yr,count(*) alarms,
               count(*) FILTER(WHERE numeric_obs_time>=event_time-INTERVAL 24 HOUR) numeric_24h,
               count(*) FILTER(WHERE numeric_obs_time>=event_time-INTERVAL 72 HOUR) numeric_72h,
               quantile_cont(numeric_median,[0.1,0.5,0.9,0.99]) last_hour_median_q,
               quantile_cont(numeric_max,[0.1,0.5,0.9,0.99]) last_hour_max_q
        FROM previous GROUP BY 1 ORDER BY 1
    """)
    emit(con, "object_concentration", """
        SELECT year(event_time) yr,object_id,count(*) alarms,
               count(DISTINCT channel_id) channels
        FROM separated GROUP BY 1,2 ORDER BY alarms DESC LIMIT 25
    """)


if __name__ == "__main__":
    main()
