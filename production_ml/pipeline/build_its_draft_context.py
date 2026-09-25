"""Фактическое состояние входных данных в момент исторического черновика."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def quote(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--members", type=Path, nargs="+", required=True)
    parser.add_argument("--journals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in args.members:
        if not path.exists():
            raise FileNotFoundError(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    member_list = "[" + ",".join(quote(path) for path in args.members) + "]"
    con.execute(f"CREATE VIEW drafts AS SELECT * FROM read_parquet({member_list})")
    first_year, last_year = con.execute("SELECT year(min(obs_time)),year(max(obs_time)) FROM drafts").fetchone()
    journals = [args.journals / f"journal_{year}.parquet"
                for year in range(first_year, last_year + 1)]
    for path in journals:
        if not path.exists():
            raise FileNotFoundError(path)
    journal_list = "[" + ",".join(quote(path) for path in journals) + "]"
    con.execute(f"CREATE VIEW journal AS SELECT * FROM read_parquet({journal_list})")
    con.execute("""
        CREATE TABLE draft_events AS
        SELECT d.draft_id,d.obs_time,d.channel_id,j.event_time,j.event_id,
               j.sensor_value,j.is_alarm
        FROM drafts d JOIN journal j ON d.channel_id=j.channel_id
           AND j.event_time BETWEEN d.obs_time-INTERVAL 72 HOUR AND d.obs_time;

        CREATE TABLE conflicts AS
        WITH value_flags AS (
            SELECT draft_id,event_time,sensor_value,
                   min(is_alarm) min_alarm,max(is_alarm) max_alarm
            FROM draft_events GROUP BY 1,2,3
        ), time_flags AS (
            SELECT draft_id,event_time,
                   count(*) FILTER(WHERE min_alarm!=max_alarm) exact_conflicts,
                   min(min_alarm) min_alarm,max(max_alarm) max_alarm
            FROM value_flags GROUP BY 1,2
        )
        SELECT draft_id,sum(exact_conflicts) conflicting_status_keys_72h,
               count(*) FILTER(WHERE min_alarm!=max_alarm) mixed_alarm_timestamps_72h
        FROM time_flags WHERE exact_conflicts>0 OR min_alarm!=max_alarm
        GROUP BY 1;

        CREATE TABLE context AS
        SELECT d.draft_id,d.group_id,d.basis_kind,d.target_kind,d.object_id,
               d.channel_id,d.obs_time,d.score,d.situation_id,
               count(e.event_time) event_count_72h,
               count(e.event_time) FILTER(WHERE e.sensor_value IN
                   ('Неисправен','Батарея неисправна')) fault_reports_72h,
               count(e.event_time) FILTER(WHERE e.sensor_value IN
                   ('Неопределен','Не определено','Выключен','Отключено устройство'))
                   service_reports_72h,
               coalesce(max(c.conflicting_status_keys_72h),0)
                   conflicting_status_keys_72h,
               coalesce(max(c.mixed_alarm_timestamps_72h),0)
                   mixed_alarm_timestamps_72h,
               max(e.event_time) last_event_time,
               arg_max(e.event_id,struct_pack(t:=e.event_time,id:=e.event_id,
                       v:=e.sensor_value,a:=e.is_alarm)) last_event_id,
               arg_max(e.sensor_value,struct_pack(t:=e.event_time,id:=e.event_id,
                       v:=e.sensor_value,a:=e.is_alarm)) last_value,
               CASE WHEN count(e.event_time)=0 THEN 'no_recent_observation'
                    WHEN coalesce(max(c.conflicting_status_keys_72h),0)>0
                    THEN 'conflicting_recent_status_flag'
                    WHEN coalesce(max(c.mixed_alarm_timestamps_72h),0)>0
                    THEN 'ambiguous_simultaneous_statuses'
                    ELSE 'recent_observation' END observation_state,
               CAST(NULL AS DOUBLE) its_value,
               'unavailable_no_confirmed_health_target' its_status
        FROM drafts d LEFT JOIN draft_events e USING(draft_id)
        LEFT JOIN conflicts c USING(draft_id)
        GROUP BY d.draft_id,d.group_id,d.basis_kind,d.target_kind,d.object_id,
                 d.channel_id,d.obs_time,d.score,d.situation_id;
    """)
    con.execute(f"COPY context TO {quote(args.output)} (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        SELECT count(*) drafts,
               count(*) FILTER(WHERE event_count_72h=0) without_72h_history,
               count(*) FILTER(WHERE fault_reports_72h>0) with_fault_report,
               count(*) FILTER(WHERE service_reports_72h>0) with_service_report,
               count(*) FILTER(WHERE conflicting_status_keys_72h>0) with_conflict,
               count(*) FILTER(WHERE mixed_alarm_timestamps_72h>0) with_mixed_status,
               count(*) FILTER(WHERE its_value IS NOT NULL) numeric_its_values
        FROM context
    """)
    print(json.dumps(dict(zip([d[0] for d in result.description],result.fetchone())),
                     ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
