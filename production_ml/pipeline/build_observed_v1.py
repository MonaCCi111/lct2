"""Собрать отдельный слой наблюдаемых ситуаций без прогноза и диагноза."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = args.root
    output = args.output or root / "observed_v1"
    output.mkdir(parents=True, exist_ok=True)
    inputs = {
        "smoke_cards": root / "smoke_evidence" / "cards.parquet",
        "smoke_signals": root / "smoke_evidence" / "signals.parquet",
        "gas_cards": root / "gas_v1" / "alarm_cards.parquet",
        "gas_evidence": root / "gas_v1" / "alarm_evidence.parquet",
        "gas_status_events": root / "gas_v1" / "status_events.parquet",
    }
    yearly = [root / "gas_v1" / f"hourly_{year}.parquet"
              for year in range(2019, 2027)]
    yearly += [root / "source_v2" / f"journal_{year}.parquet"
               for year in range(2019, 2027)]
    for path in (*inputs.values(), *yearly):
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    con.execute(f"SET temp_directory='{(output / 'duckdb_temp').as_posix()}'")
    for name, path in inputs.items():
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    con.execute(f"CREATE VIEW gas_hourly AS SELECT * FROM read_parquet('{(root / 'gas_v1' / 'hourly_20??.parquet').as_posix()}')")
    catalog = Path(__file__).resolve().parents[4] / "dataset" / "справочник_каналов_датчиков.csv"
    if not catalog.exists():
        raise FileNotFoundError(catalog)
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv('{catalog.as_posix()}')")
    con.execute(f"CREATE VIEW journal AS SELECT * FROM read_parquet('{(root / 'source_v2' / 'journal_20??.parquet').as_posix()}')")

    # Десять каналов или мест в объектной цепочке служат правилом упаковки.
    con.execute("""
        CREATE TABLE smoke_mapping AS
        WITH ordered AS (
            SELECT *,lag(first_signal_time) OVER (
                PARTITION BY object_id ORDER BY first_signal_time,card_id
            ) previous_start
            FROM smoke_cards
        ), numbered AS (
            SELECT *,sum(CASE WHEN previous_start IS NULL OR
                    first_signal_time>previous_start+INTERVAL 1 HOUR THEN 1 ELSE 0 END)
                    OVER (PARTITION BY object_id ORDER BY first_signal_time,card_id
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) group_number
            FROM ordered
        ), group_scope AS (
            SELECT object_id,group_number,count(DISTINCT location_key) locations,
                   max(max_object_smoke_channels_15m) simultaneous_channels,
                   concat('SMOKE_MASS:',object_id::VARCHAR,':',
                          strftime(min(first_signal_time),'%Y%m%dT%H%M%S')) situation_id
            FROM numbered GROUP BY 1,2
        )
        SELECT n.card_id,
               CASE WHEN g.locations>=10 OR g.simultaneous_channels>=10
                    THEN g.situation_id
                    ELSE concat('SMOKE_LOCAL:',n.card_id) END situation_id,
               g.locations>=10 OR g.simultaneous_channels>=10 mass
        FROM numbered n JOIN group_scope g USING(object_id,group_number);

        CREATE TABLE smoke_output AS
        SELECT m.situation_id,
               CASE WHEN bool_or(m.mass) THEN 'OBSERVED_SMOKE_OBJECT_CAMPAIGN'
                    ELSE 'OBSERVED_SMOKE_LOCAL' END situation_kind,
               c.object_id,min(c.first_signal_time) first_seen,
               max(c.last_signal_time) last_seen,
               CASE WHEN bool_or(m.mass) THEN NULL ELSE min(c.location_key) END location_key,
               sum(c.signal_records) signal_records,
               count(DISTINCT c.location_key) locations,
               max(c.max_object_smoke_channels_15m) object_channels_15m,
               max(c.max_location_smoke_channels_15m) local_channels_15m,
               sum(c.signals_with_comparable_temperature) comparable_temperature_signals,
               max(c.maximum_temperature_delta) max_temperature_delta,
               max(c.maximum_recent_numeric_temperature) max_recent_numeric_temperature,
               CAST(NULL AS DOUBLE) numeric_max,
               CAST(NULL AS BIGINT) numeric_channels,
               CAST(NULL AS BIGINT) recent_text_alarm_channels,
               sum(c.mixed_status_signal_records) mixed_status_signal_records,
               'smoke_status_not_confirmed_fire;temperature_unit_unverified;location_from_name' limitations
        FROM smoke_cards c JOIN smoke_mapping m USING(card_id)
        GROUP BY 1,3;

        CREATE TABLE gas_status_output AS
        SELECT concat('GAS_STATUS:',card_id) situation_id,
               'OBSERVED_GAS_TEXT_STATUS' situation_kind,object_id,
               first_alarm_time first_seen,last_alarm_time last_seen,
               CAST(NULL AS VARCHAR) location_key,alarm_records signal_records,
               CAST(NULL AS BIGINT) locations,CAST(NULL AS BIGINT) object_channels_15m,
               CAST(NULL AS BIGINT) local_channels_15m,
               CAST(NULL AS BIGINT) comparable_temperature_signals,
               CAST(NULL AS DOUBLE) max_temperature_delta,
               CAST(NULL AS DOUBLE) max_recent_numeric_temperature,
               maximum_recent_numeric numeric_max,alarm_channels numeric_channels,
               alarm_channels recent_text_alarm_channels,
               CAST(NULL AS BIGINT) mixed_status_signal_records,
               'status_not_confirmed_leak;maintenance_schedule_unavailable;numeric_context_may_be_old' limitations
        FROM gas_cards;

        CREATE TABLE gas_threshold_hours AS
        SELECT channel_id,object_id,obs_time,numeric_max,numeric_min,numeric_count,
               lag(obs_time) OVER (
                   PARTITION BY object_id ORDER BY obs_time,channel_id) previous_time
        FROM gas_hourly WHERE numeric_max>=1.0;

        CREATE TABLE gas_threshold_numbered AS
        SELECT *,sum(CASE WHEN previous_time IS NULL OR
                   obs_time>previous_time+INTERVAL 1 HOUR THEN 1 ELSE 0 END)
                   OVER (PARTITION BY object_id ORDER BY obs_time,channel_id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) group_number
        FROM gas_threshold_hours;

        CREATE TABLE gas_threshold_ids AS
        SELECT object_id,group_number,
               concat('GAS_NUMERIC:',object_id::VARCHAR,':',
                      strftime(min(obs_time),'%Y%m%dT%H%M%S')) situation_id
        FROM gas_threshold_numbered GROUP BY 1,2;

        CREATE TABLE gas_numeric_output AS
        SELECT i.situation_id,'OBSERVED_GAS_NUMERIC_1PCT' situation_kind,
               h.object_id,min(h.obs_time) first_seen,max(h.obs_time) last_seen,
               CAST(NULL AS VARCHAR) location_key,
               count(DISTINCT (h.channel_id,h.obs_time)) signal_records,
               CAST(NULL AS BIGINT) locations,CAST(NULL AS BIGINT) object_channels_15m,
               CAST(NULL AS BIGINT) local_channels_15m,
               CAST(NULL AS BIGINT) comparable_temperature_signals,
               CAST(NULL AS DOUBLE) max_temperature_delta,
               CAST(NULL AS DOUBLE) max_recent_numeric_temperature,
               max(h.numeric_max) numeric_max,
               count(DISTINCT h.channel_id) numeric_channels,
               count(DISTINCT a.channel_id) recent_text_alarm_channels,
               CAST(NULL AS BIGINT) mixed_status_signal_records,
               'threshold_is_observation_not_leak;hourly_max_not_instant_time;maintenance_schedule_unavailable;extreme_values_unverified' limitations
        FROM gas_threshold_numbered h
        JOIN gas_threshold_ids i USING(object_id,group_number)
        LEFT JOIN gas_evidence a ON h.channel_id=a.channel_id
             AND a.event_time BETWEEN h.obs_time-INTERVAL 24 HOUR AND h.obs_time
        GROUP BY 1,3;

        CREATE TABLE other_raw AS
        SELECT j.event_id,j.channel_id,c."ид_объект" object_id,
               c."тип_датчика" sensor_type,j.event_time,j.sensor_value,j.is_alarm
        FROM journal j JOIN catalog c ON j.channel_id=c."ид_канала_данных"
        WHERE (c."тип_датчика",j.sensor_value) IN (
            ('Состояние насоса','Затоплен'),
            ('ИБП','Батарея разряжена'),
            ('Датчик температуры','Температура выше 40ºC'),
            ('Состояние УИР-Р','Рычаг сдернут'));

        CREATE TABLE other_times AS
        SELECT channel_id,event_time,sensor_value,bool_or(is_alarm) any_alarm,
               bool_and(is_alarm) all_alarm
        FROM other_raw GROUP BY 1,2,3;

        CREATE TABLE other_signals AS
        SELECT r.event_id,r.channel_id,r.object_id,r.sensor_type,
               r.event_time,r.sensor_value,
               CASE WHEN r.sensor_type='Состояние насоса' THEN 'OBSERVED_PUMP_FLOODED_STATUS'
                    WHEN r.sensor_type='ИБП' THEN 'OBSERVED_UPS_BATTERY_LOW_STATUS'
                    WHEN r.sensor_type='Датчик температуры' THEN 'OBSERVED_TEMPERATURE_HIGH_STATUS'
                    ELSE 'OBSERVED_MANUAL_LEVER_STATUS' END situation_kind
        FROM other_raw r JOIN other_times t USING(channel_id,event_time,sensor_value)
        WHERE r.is_alarm AND t.all_alarm=t.any_alarm;

        CREATE TABLE other_numbered AS
        WITH ordered AS (
            SELECT *,lag(event_time) OVER (
                PARTITION BY situation_kind,object_id ORDER BY event_time,channel_id,event_id
            ) previous_time
            FROM other_signals
        )
        SELECT *,sum(CASE WHEN previous_time IS NULL OR
                   event_time>previous_time+INTERVAL 1 HOUR THEN 1 ELSE 0 END)
                   OVER (PARTITION BY situation_kind,object_id
                         ORDER BY event_time,channel_id,event_id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) group_number
        FROM ordered;

        CREATE TABLE other_ids AS
        SELECT situation_kind,object_id,group_number,
               concat(situation_kind,':',object_id::VARCHAR,':',
                      strftime(min(event_time),'%Y%m%dT%H%M%S')) situation_id
        FROM other_numbered GROUP BY 1,2,3;

        CREATE TABLE other_output AS
        SELECT i.situation_id,n.situation_kind,n.object_id,
               min(n.event_time) first_seen,max(n.event_time) last_seen,
               CAST(NULL AS VARCHAR) location_key,count(*) signal_records,
               CAST(NULL AS BIGINT) locations,CAST(NULL AS BIGINT) object_channels_15m,
               CAST(NULL AS BIGINT) local_channels_15m,
               CAST(NULL AS BIGINT) comparable_temperature_signals,
               CAST(NULL AS DOUBLE) max_temperature_delta,
               CAST(NULL AS DOUBLE) max_recent_numeric_temperature,
               CAST(NULL AS DOUBLE) numeric_max,count(DISTINCT n.channel_id) numeric_channels,
               CAST(NULL AS BIGINT) recent_text_alarm_channels,
               CAST(NULL AS BIGINT) mixed_status_signal_records,
               'observed_text_status_not_confirmed_physical_incident;maintenance_context_unavailable' limitations
        FROM other_numbered n JOIN other_ids i USING(situation_kind,object_id,group_number)
        GROUP BY 1,2,3;

        CREATE TABLE situations AS
        SELECT *,CASE WHEN situation_kind LIKE 'OBSERVED_GAS%'
                      THEN 'vol_percent_methane' ELSE NULL END numeric_unit,
               CASE WHEN situation_kind='OBSERVED_GAS_NUMERIC_1PCT'
                      THEN 1.0 ELSE NULL END stated_threshold,
               CASE WHEN situation_kind='OBSERVED_SMOKE_OBJECT_CAMPAIGN'
                           OR coalesce(numeric_channels,0)>=10
                    THEN true ELSE false END multi_channel_campaign
        FROM (
            SELECT * FROM smoke_output
            UNION ALL SELECT * FROM gas_status_output
            UNION ALL SELECT * FROM gas_numeric_output
            UNION ALL SELECT * FROM other_output
        );
    """)
    con.execute("""
        CREATE TABLE evidence AS
        WITH smoke AS (
            SELECT m.situation_id,'SMOKE_TEXT' evidence_kind,
                   s.channel_id,s.event_time,CAST(NULL AS BIGINT) event_id,
                   'Обнаружен дым' observed_value,CAST(NULL AS DOUBLE) numeric_value,
                   s.piket,CAST(NULL AS TIMESTAMP) observation_end,
                   s.object_smoke_channels_15m,s.location_smoke_channels_15m,
                   s.recent_numeric_count,s.baseline_numeric_count,
                   s.recent_median,s.baseline_median,s.temperature_delta,
                   s.mixed_alarm_flags_at_time,
                   'source_v2/journal_YEAR.parquet:channel_id+event_time+sensor_value+is_alarm' source_ref
            FROM smoke_signals s JOIN smoke_cards c
              ON s.object_id=c.object_id
             AND (CASE WHEN s.piket IS NULL OR s.piket='' THEN concat('channel:',s.channel_id::VARCHAR)
                       ELSE concat('piket:',s.piket) END)=c.location_key
             AND s.event_time BETWEEN c.first_signal_time AND c.last_signal_time
            JOIN smoke_mapping m USING(card_id)
        ), gas_status AS (
            SELECT concat('GAS_STATUS:',card_id),'GAS_TEXT',channel_id,event_time,
                   (SELECT min(event_id) FROM gas_status_events se
                    WHERE se.channel_id=a.channel_id AND se.event_time=a.event_time
                      AND se.sensor_value='Обнаружен газ' AND se.is_alarm),
                   'Обнаружен газ',CAST(NULL AS DOUBLE),
                   CAST(NULL AS VARCHAR),CAST(NULL AS TIMESTAMP),
                   CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),
                   CAST(NULL AS BOOLEAN),
                   'gas_v1/status_events.parquet:channel_id+event_time+sensor_value+is_alarm'
            FROM gas_evidence a
        ), gas_numeric AS (
            SELECT i.situation_id,'GAS_NUMERIC_HOURLY',h.channel_id,h.obs_time,
                   CAST(NULL AS BIGINT),CAST(h.numeric_max AS VARCHAR),h.numeric_max,
                   CAST(NULL AS VARCHAR),h.obs_time,
                   CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),
                   CAST(NULL AS BOOLEAN),
                   'gas_v1/hourly_YEAR.parquet:channel_id+obs_time;source_v2/journal_YEAR.parquet:hour_before_obs_time'
            FROM gas_threshold_numbered h JOIN gas_threshold_ids i USING(object_id,group_number)
        ), other_status AS (
            SELECT i.situation_id,'OTHER_TEXT_STATUS',n.channel_id,n.event_time,n.event_id,
                   n.sensor_value,CAST(NULL AS DOUBLE),CAST(NULL AS VARCHAR),
                   CAST(NULL AS TIMESTAMP),CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS BIGINT),CAST(NULL AS BIGINT),
                   CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),CAST(NULL AS DOUBLE),
                   CAST(NULL AS BOOLEAN),
                   'source_v2/journal_YEAR.parquet:event_id'
            FROM other_numbered n JOIN other_ids i USING(situation_kind,object_id,group_number)
        )
        SELECT * FROM smoke UNION ALL SELECT * FROM gas_status
        UNION ALL SELECT * FROM gas_numeric UNION ALL SELECT * FROM other_status;

        CREATE TABLE evidence_export AS
        SELECT e.*,c."название_датчика" channel_name,
               CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN 'vol_percent_methane' ELSE NULL END numeric_unit,
               h.numeric_count hour_numeric_count,h.numeric_min hour_numeric_min
        FROM evidence e LEFT JOIN catalog c ON e.channel_id=c."ид_канала_данных"
        LEFT JOIN (SELECT * FROM gas_hourly WHERE numeric_max>=1) h
              ON e.evidence_kind='GAS_NUMERIC_HOURLY'
              AND e.channel_id=h.channel_id AND e.observation_end=h.obs_time;

        CREATE TABLE situations_export AS
        SELECT s.*,x.affected_channels
        FROM situations s JOIN (
            SELECT situation_id,count(DISTINCT channel_id) affected_channels
            FROM evidence_export GROUP BY 1
        ) x USING(situation_id);
    """)
    for table, name in (("situations_export", "situations"), ("evidence_export", "evidence")):
        path = output / f"{name}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    con.execute(f"""
        COPY (
            SELECT cast(first_seen AS DATE) observed_date,situation_kind,
                   count(*) situation_count,count(DISTINCT object_id) affected_objects,
                   sum(signal_records) source_records
            FROM situations_export GROUP BY 1,2 ORDER BY 1,2
        ) TO '{(output / 'daily_situation_counts.csv').as_posix()}'
        (HEADER,DELIMITER ',')
    """)
    summary = con.execute("""
        SELECT situation_kind,year(first_seen) yr,count(*) situations,
               count(DISTINCT object_id) objects,max(signal_records) max_records,
               max(numeric_channels) max_numeric_channels
        FROM situations_export GROUP BY 1,2 ORDER BY 1,2
    """).fetchall()
    print(json.dumps({"output": str(output), "summary": summary,
                      "situations": con.execute("SELECT count(*) FROM situations_export").fetchone()[0],
                      "evidence": con.execute("SELECT count(*) FROM evidence").fetchone()[0]},
                     ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
