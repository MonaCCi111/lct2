"""Помесячная витрина наблюдаемого состояния без выдуманного балла ИТС."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def quote(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--journals", type=Path, required=True)
    parser.add_argument("--first-month", default="2024-01-01")
    parser.add_argument("--last-month", default="2026-06-01")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.catalog, args.states):
        if not path.exists():
            raise FileNotFoundError(path)
    journals = sorted(args.journals.glob("journal_20??.parquet"))
    if not journals:
        raise FileNotFoundError(args.journals)
    args.output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    temp = args.output / "duckdb_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={quote(temp)}")
    sources = "[" + ",".join(quote(path) for path in journals) + "]"
    con.execute(f"CREATE VIEW journal AS SELECT * FROM read_parquet({sources})")
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv({quote(args.catalog)})")
    con.execute(f"CREATE VIEW states AS SELECT * FROM read_csv({quote(args.states)})")
    duplicates = con.execute('SELECT count(*)-count(DISTINCT "ид_канала_данных") FROM catalog').fetchone()[0]
    if duplicates:
        raise ValueError(f"Повтор канала в каталоге: {duplicates}")
    con.execute(f"""
        CREATE TABLE months AS
        SELECT last_day(month_start)::DATE snapshot_date,
               last_day(month_start)::TIMESTAMP+INTERVAL 1 DAY-INTERVAL 1 SECOND as_of
        FROM generate_series(DATE '{args.first_month}',DATE '{args.last_month}',
                             INTERVAL 1 MONTH) t(month_start);

        CREATE TABLE conflict_dates AS
        SELECT DISTINCT (snapshot_date-day_offset)::DATE event_date
        FROM months CROSS JOIN (VALUES (0),(1),(2)) v(day_offset);

        CREATE TABLE dictionary AS
        SELECT "тип_датчика" sensor_type,"название_состояния" sensor_value,
               count(DISTINCT "тревожное") alarm_variants,
               bool_or("тревожное") any_alarm,bool_and("тревожное") all_alarm,
               count(DISTINCT "ид_набор_состояний") state_sets
        FROM states GROUP BY 1,2;

        CREATE TABLE daily AS
        SELECT channel_id,event_time::DATE event_date,count(*) event_count,
               count(*) FILTER(WHERE isfinite(try_cast(replace(sensor_value,',','.')
                   AS DOUBLE))) numeric_count,
               count(*) FILTER(WHERE sensor_value IN ('Неисправен','Батарея неисправна'))
                   explicit_fault_reports,
               count(*) FILTER(WHERE sensor_value IN
                   ('Неопределен','Не определено','Выключен','Отключено устройство'))
                   service_reports,
               min(event_time) first_event_time,max(event_time) last_event_time,
               arg_max(sensor_value,struct_pack(t:=event_time,e:=event_id,
                       v:=sensor_value,a:=is_alarm)) last_value,
               arg_max(is_alarm,struct_pack(t:=event_time,e:=event_id,
                       v:=sensor_value,a:=is_alarm)) last_is_alarm,
               arg_max(event_id,struct_pack(t:=event_time,e:=event_id,
                       v:=sensor_value,a:=is_alarm)) last_event_id
        FROM journal
        WHERE event_time <= (SELECT max(as_of) FROM months)
        GROUP BY 1,2;

        CREATE TABLE daily_text AS
        SELECT channel_id,event_time::DATE event_date,
               max(event_time) last_text_time,
               arg_max(sensor_value,struct_pack(t:=event_time,e:=event_id,
                       v:=sensor_value,a:=is_alarm)) last_text_status,
               arg_max(is_alarm,struct_pack(t:=event_time,e:=event_id,
                       v:=sensor_value,a:=is_alarm)) last_text_alarm
        FROM journal
        WHERE event_time <= (SELECT max(as_of) FROM months)
          AND NOT coalesce(isfinite(try_cast(replace(sensor_value,',','.')
                                   AS DOUBLE)),false)
        GROUP BY 1,2;

        CREATE TABLE daily_conflicts AS
        WITH value_flags AS (
            SELECT channel_id,event_time,sensor_value,
                   min(is_alarm) min_alarm,max(is_alarm) max_alarm
            FROM journal j JOIN conflict_dates cd
              ON j.event_time::DATE=cd.event_date
            WHERE event_time<=(SELECT max(as_of) FROM months)
            GROUP BY 1,2,3
        ), time_flags AS (
            SELECT channel_id,event_time,
                   count(*) FILTER(WHERE min_alarm!=max_alarm) exact_conflicts,
                   min(min_alarm) min_alarm,max(max_alarm) max_alarm
            FROM value_flags GROUP BY 1,2
        )
        SELECT channel_id,event_time::DATE event_date,
               sum(exact_conflicts) conflicting_status_keys,
               count(*) FILTER(WHERE min_alarm!=max_alarm) mixed_alarm_timestamps
        FROM time_flags WHERE exact_conflicts>0 OR min_alarm!=max_alarm
        GROUP BY 1,2;

        CREATE TABLE channels AS
        SELECT coalesce(c."ид_канала_данных",d.channel_id) channel_id,
               c."тип_датчика" sensor_type,c."ид_объект" object_id,
               c."название_датчика" channel_name,
               c."ид_канала_данных" IS NOT NULL in_catalog
        FROM catalog c FULL OUTER JOIN (SELECT DISTINCT channel_id FROM daily) d
        ON c."ид_канала_данных"=d.channel_id;

        CREATE TABLE grid AS
        SELECT c.*,m.snapshot_date,m.as_of FROM channels c CROSS JOIN months m;

        CREATE TABLE last_event AS
        SELECT g.channel_id,g.snapshot_date,d.last_event_time,d.last_value,
               d.last_is_alarm,d.last_event_id
        FROM grid g ASOF LEFT JOIN daily d
          ON g.channel_id=d.channel_id AND g.snapshot_date>=d.event_date;

        CREATE TABLE last_text AS
        SELECT g.channel_id,g.snapshot_date,d.last_text_time,
               d.last_text_status,d.last_text_alarm
        FROM grid g ASOF LEFT JOIN daily_text d
          ON g.channel_id=d.channel_id AND g.snapshot_date>=d.event_date;

        CREATE TABLE recent AS
        SELECT g.channel_id,g.snapshot_date,
               sum(d.event_count) event_count_72h,
               sum(d.numeric_count) numeric_count_72h,
               sum(d.explicit_fault_reports) fault_reports_72h,
               sum(d.service_reports) service_reports_72h
        FROM grid g LEFT JOIN daily d ON g.channel_id=d.channel_id
          AND d.event_date BETWEEN g.snapshot_date-INTERVAL 2 DAY AND g.snapshot_date
        GROUP BY 1,2;

        CREATE TABLE conflicts AS
        SELECT g.channel_id,g.snapshot_date,
               sum(x.conflicting_status_keys) conflicting_status_keys_72h,
               sum(x.mixed_alarm_timestamps) mixed_alarm_timestamps_72h
        FROM grid g LEFT JOIN daily_conflicts x ON g.channel_id=x.channel_id
          AND x.event_date BETWEEN g.snapshot_date-INTERVAL 2 DAY AND g.snapshot_date
        GROUP BY 1,2;

        CREATE TABLE firsts AS
        SELECT channel_id,min(first_event_time) first_event_time
        FROM daily GROUP BY 1;

        CREATE TABLE facts AS
        SELECT g.channel_id,g.sensor_type,g.object_id,g.channel_name,g.in_catalog,
               g.snapshot_date,g.as_of,f.first_event_time,
               l.last_event_time,l.last_event_id,l.last_value,l.last_is_alarm,
               t.last_text_time,t.last_text_status,t.last_text_alarm,
               coalesce(r.event_count_72h,0) event_count_72h,
               coalesce(r.numeric_count_72h,0) numeric_count_72h,
               coalesce(r.fault_reports_72h,0) fault_reports_72h,
               coalesce(r.service_reports_72h,0) service_reports_72h,
               coalesce(x.conflicting_status_keys_72h,0)
                   conflicting_status_keys_72h,
               coalesce(x.mixed_alarm_timestamps_72h,0)
                   mixed_alarm_timestamps_72h,
               d.alarm_variants,d.any_alarm,d.all_alarm,d.state_sets
        FROM grid g LEFT JOIN firsts f USING(channel_id)
        LEFT JOIN last_event l USING(channel_id,snapshot_date)
        LEFT JOIN last_text t USING(channel_id,snapshot_date)
        LEFT JOIN recent r USING(channel_id,snapshot_date)
        LEFT JOIN conflicts x USING(channel_id,snapshot_date)
        LEFT JOIN dictionary d ON g.sensor_type=d.sensor_type
          AND t.last_text_status=d.sensor_value;

        CREATE TABLE channel_history AS
        WITH classified AS (
            SELECT *,CASE
                WHEN NOT in_catalog THEN 'metadata_missing'
                WHEN first_event_time IS NULL OR first_event_time>as_of
                  THEN 'new_or_never_observed'
                WHEN conflicting_status_keys_72h>0 THEN 'conflicting_recent_status_flag'
                WHEN mixed_alarm_timestamps_72h>0 THEN 'ambiguous_simultaneous_statuses'
                WHEN last_event_time<=as_of-INTERVAL 72 HOUR THEN 'no_recent_observation'
                ELSE 'recent_observation' END observation_state,
                CASE WHEN last_text_time IS NULL THEN 'no_text_status'
                     WHEN alarm_variants IS NULL THEN 'not_listed_for_type'
                     WHEN alarm_variants>1 THEN 'dictionary_conflict'
                     WHEN last_text_alarm!=any_alarm THEN 'source_dictionary_disagreement'
                     ELSE 'listed_consistently' END dictionary_state,
                round(date_diff('second',last_event_time,as_of)/3600.0,3)
                    hours_since_last_event,
                CAST(NULL AS DOUBLE) its_value,
                'unavailable' its_status,
                'no_confirmed_physical_health_or_repair_target' its_reason
            FROM facts
        )
        SELECT *,lag(observation_state) OVER (
                   PARTITION BY channel_id ORDER BY snapshot_date) previous_observation_state,
               lag(fault_reports_72h) OVER (
                   PARTITION BY channel_id ORDER BY snapshot_date) previous_fault_reports_72h
        FROM classified;

        CREATE TABLE object_type_history AS
        SELECT snapshot_date,object_id,sensor_type,count(*) catalog_channels,
               count(*) FILTER(WHERE observation_state='recent_observation')
                   recently_observed_channels,
               count(*) FILTER(WHERE observation_state='no_recent_observation')
                   no_recent_observation_channels,
               count(*) FILTER(WHERE observation_state='conflicting_recent_status_flag')
                   conflicting_channels,
               count(*) FILTER(WHERE observation_state='ambiguous_simultaneous_statuses')
                   ambiguous_simultaneous_channels,
               count(*) FILTER(WHERE fault_reports_72h>0) channels_with_fault_report_72h,
               sum(fault_reports_72h) fault_report_records_72h,
               CAST(NULL AS DOUBLE) its_value,
               'unavailable_no_equipment_mapping_or_health_target' its_status
        FROM channel_history WHERE object_id IS NOT NULL
        GROUP BY 1,2,3;
    """)
    for table in ("channel_history", "object_type_history"):
        con.execute(f"COPY {table} TO {quote(args.output / (table + '.parquet'))} "
                    "(FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        SELECT (SELECT count(*) FROM months) month_count,
               (SELECT count(*) FROM channels) channels,
               (SELECT count(*) FROM channel_history) channel_rows,
               (SELECT count(*) FROM object_type_history) object_type_rows,
               (SELECT count(*) FROM channel_history WHERE snapshot_date=(
                   SELECT max(snapshot_date) FROM months) AND observation_state='recent_observation')
                   last_recent_channels,
               (SELECT count(*) FROM channel_history WHERE snapshot_date=(
                   SELECT max(snapshot_date) FROM months) AND observation_state='no_recent_observation')
                   last_silent_channels,
               (SELECT count(*) FROM channel_history WHERE its_value IS NOT NULL)
                   numeric_its_values
    """)
    print(json.dumps(dict(zip([d[0] for d in result.description],result.fetchone())),
                     ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
