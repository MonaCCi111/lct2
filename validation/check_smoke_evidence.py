"""Проверить структуру исторических свидетельств дыма и температуры."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    path = root / "production_ml" / "data" / "smoke_evidence" / "signals.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW evidence AS SELECT * FROM read_parquet('{path.as_posix()}')")
    result = con.execute("""
        SELECT count(*) signals,
               count(*)-(SELECT count(*) FROM (SELECT channel_id,event_time FROM evidence GROUP BY 1,2)) duplicate_keys,
               count(*) FILTER(WHERE recent_numeric_count>0 AND recent_median IS NULL) missing_recent,
               count(*) FILTER(WHERE baseline_numeric_count>0 AND baseline_median IS NULL) missing_baseline,
               count(*) FILTER(WHERE recent_numeric_count=0 AND recent_median IS NOT NULL) unexpected_recent,
               count(*) FILTER(WHERE recent_numeric_count>0 AND piket='') temp_without_piket,
               count(*) FILTER(WHERE temperature_delta IS DISTINCT FROM recent_median-baseline_median) bad_delta,
               count(*) FILTER(WHERE location_smoke_channels_15m>object_smoke_channels_15m) bad_context
        FROM evidence
    """)
    fields=[d[0] for d in result.description]
    row=dict(zip(fields,result.fetchone()))
    print(json.dumps({"check":"structure",**row},ensure_ascii=False),flush=True)
    bad=("duplicate_keys","missing_recent","missing_baseline","unexpected_recent",
         "temp_without_piket","bad_delta","bad_context")
    if any(row[field]!=0 for field in bad):
        raise AssertionError(row)
    result=con.execute("""
        WITH x AS (
          SELECT channel_id,event_time,year(event_time) yr,
                 lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time) previous_time,
                 recent_numeric_count,baseline_numeric_count,temperature_delta
          FROM evidence
        )
        SELECT yr,count(*) FILTER(WHERE previous_time IS NULL OR event_time-previous_time>=INTERVAL 24 HOUR) separated_signals,
               count(*) FILTER(WHERE (previous_time IS NULL OR event_time-previous_time>=INTERVAL 24 HOUR)
                                 AND recent_numeric_count>0 AND baseline_numeric_count>0) separated_comparable
        FROM x GROUP BY 1 ORDER BY 1
    """)
    print(json.dumps({"check":"signal_spacing","columns":[d[0] for d in result.description],
                      "rows":result.fetchall()},ensure_ascii=False),flush=True)
    result=con.execute("""
        WITH x AS (
          SELECT *,lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time) previous_time
          FROM evidence
        )
        SELECT count(*) comparable_signals,
               quantile_cont(temperature_delta,[0.01,0.1,0.25,0.5,0.75,0.9,0.99]) delta_quantiles,
               min(temperature_delta) min_delta,max(temperature_delta) max_delta
        FROM x
        WHERE year(event_time) BETWEEN 2022 AND 2025
          AND (previous_time IS NULL OR event_time-previous_time>=INTERVAL 24 HOUR)
          AND recent_numeric_count>0 AND baseline_numeric_count>0
    """)
    print(json.dumps({"check":"temperature_comparison","columns":[d[0] for d in result.description],
                      "rows":result.fetchall()},ensure_ascii=False),flush=True)
    result=con.execute("""
        WITH x AS (
          SELECT *,lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time) previous_time
          FROM evidence
        )
        SELECT channel_id,event_time,object_id,piket,recent_numeric_count,baseline_numeric_count,
               recent_median,baseline_median,temperature_delta,location_smoke_channels_15m,
               object_smoke_channels_15m
        FROM x
        WHERE year(event_time) BETWEEN 2022 AND 2025
          AND (previous_time IS NULL OR event_time-previous_time>=INTERVAL 24 HOUR)
          AND recent_numeric_count>0 AND baseline_numeric_count>0
        ORDER BY temperature_delta DESC LIMIT 10
    """)
    print(json.dumps({"check":"largest_temperature_deltas","columns":[d[0] for d in result.description],
                      "rows":result.fetchall()},ensure_ascii=False,default=str),flush=True)


if __name__ == "__main__":
    main()
