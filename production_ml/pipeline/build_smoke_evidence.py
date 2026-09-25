"""Собрать исторические свидетельства дыма и совместной температуры."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data" / "smoke_evidence" / "signals.parquet")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    journals = [args.source_root / "production_ml" / "data" / "source_v2" / f"journal_{y}.parquet"
                for y in range(2019, 2027)]
    channels = args.source_root / "dataset" / "справочник_каналов_датчиков.csv"
    for path in (*journals, channels):
        if not path.exists():
            raise FileNotFoundError(path)
    sources = ",".join(f"'{p.as_posix()}'" for p in journals)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output.parent / 'duckdb_temp').as_posix()}'")
    con.execute(f"""
    CREATE TABLE locations AS
    SELECT "ид_канала_данных" channel_id,"тип_датчика" sensor_type,
           "ид_объект" object_id,
           replace(regexp_extract("название_датчика",'(?i)ПК\\s*([0-9]+(?:[.,][0-9]+)?)',1),',','.') piket
    FROM read_csv('{channels.as_posix()}',header=true)
    WHERE "тип_датчика" IN ('Датчик дыма','Датчик температуры');

    CREATE TABLE source_events AS
    SELECT j.channel_id,j.event_time,j.is_alarm,j.sensor_value,l.sensor_type,l.object_id,l.piket
    FROM read_parquet([{sources}]) j
    JOIN locations l USING(channel_id);

    CREATE TABLE smoke_times AS
    SELECT channel_id,event_time,
           bool_and(is_alarm) FILTER(WHERE sensor_value='Обнаружен дым') smoke_all_alarm,
           bool_or(is_alarm) FILTER(WHERE sensor_value='Обнаружен дым') smoke_any_alarm,
           bool_and(is_alarm) all_alarm,bool_or(is_alarm) any_alarm
    FROM source_events WHERE sensor_type='Датчик дыма' GROUP BY 1,2;

    CREATE TABLE smoke_signals AS
    SELECT DISTINCT e.channel_id,e.event_time,e.object_id,e.piket,
           t.all_alarm!=t.any_alarm mixed_alarm_flags_at_time
    FROM source_events e
    JOIN smoke_times t USING(channel_id,event_time)
    WHERE e.sensor_type='Датчик дыма'
      AND e.sensor_value='Обнаружен дым' AND e.is_alarm
      AND t.smoke_all_alarm=t.smoke_any_alarm;

    CREATE TABLE temperature_events AS
    SELECT channel_id,event_time,object_id,piket,
           try_cast(replace(sensor_value,',','.') AS DOUBLE) numeric_value
    FROM source_events
    WHERE sensor_type='Датчик температуры' AND piket!='';

    CREATE TABLE temperature_evidence AS
    SELECT s.channel_id,s.event_time,
           count(t.numeric_value) FILTER(WHERE t.event_time>=s.event_time-INTERVAL 6 HOUR) recent_numeric_count,
           count(t.numeric_value) FILTER(WHERE t.event_time<s.event_time-INTERVAL 6 HOUR) baseline_numeric_count,
           median(t.numeric_value) FILTER(WHERE t.event_time>=s.event_time-INTERVAL 6 HOUR) recent_median,
           median(t.numeric_value) FILTER(WHERE t.event_time<s.event_time-INTERVAL 6 HOUR) baseline_median,
           min(t.numeric_value) FILTER(WHERE t.event_time>=s.event_time-INTERVAL 6 HOUR) recent_min,
           max(t.numeric_value) FILTER(WHERE t.event_time>=s.event_time-INTERVAL 6 HOUR) recent_max,
           count(DISTINCT t.channel_id) FILTER(WHERE t.event_time>=s.event_time-INTERVAL 6 HOUR) recent_temp_channels
    FROM smoke_signals s
    LEFT JOIN temperature_events t
      ON s.object_id=t.object_id AND s.piket=t.piket AND s.piket!=''
     AND t.numeric_value IS NOT NULL
     AND t.event_time BETWEEN s.event_time-INTERVAL 30 HOUR AND s.event_time
    GROUP BY 1,2;

    CREATE TABLE smoke_context AS
    SELECT s.channel_id,s.event_time,
           count(DISTINCT other.channel_id) FILTER(WHERE other.object_id=s.object_id) object_smoke_channels_15m,
           count(DISTINCT other.channel_id) FILTER(WHERE other.object_id=s.object_id AND other.piket=s.piket AND s.piket!='') location_smoke_channels_15m
    FROM smoke_signals s
    LEFT JOIN smoke_signals other
      ON other.event_time BETWEEN s.event_time-INTERVAL 15 MINUTE AND s.event_time
     AND other.object_id=s.object_id
    GROUP BY 1,2;

    CREATE TABLE evidence AS
    SELECT s.channel_id,s.event_time,s.object_id,s.piket,s.mixed_alarm_flags_at_time,
           c.object_smoke_channels_15m,c.location_smoke_channels_15m,
           t.recent_numeric_count,t.baseline_numeric_count,t.recent_temp_channels,
           t.recent_median,t.baseline_median,
           t.recent_median-t.baseline_median temperature_delta,
           t.recent_min,t.recent_max
    FROM smoke_signals s
    JOIN smoke_context c USING(channel_id,event_time)
    JOIN temperature_evidence t USING(channel_id,event_time);
    """)
    con.execute(f"COPY evidence TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        SELECT year(event_time) yr,count(*) signals,
               count(*) FILTER(WHERE piket!='') with_piket,
               count(*) FILTER(WHERE recent_numeric_count>0) with_recent_temperature,
               count(*) FILTER(WHERE recent_numeric_count>0 AND baseline_numeric_count>0) comparable_temperature,
               max(object_smoke_channels_15m) max_object_channels_15m
        FROM evidence GROUP BY 1 ORDER BY 1
    """)
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size,
                      "columns": [d[0] for d in result.description], "rows": result.fetchall()},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
