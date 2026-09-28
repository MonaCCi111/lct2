"""Построить временной поток одного объекта из уже выпущенных ML-витрин."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb


def quoted(path):
    return "'" + path.as_posix().replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--object-id", type=int, required=True)
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--catalog", type=Path,
                        default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_каналов_датчиков.csv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.start.tzinfo or args.end.tzinfo:
        raise ValueError("Исходное время без часового пояса; передайте локальные метки без зоны")
    if args.end <= args.start:
        raise ValueError("Конец периода должен быть позже начала")
    required = [args.catalog, args.root / "observed_v1" / "situations.parquet",
                args.root / "observed_v1" / "evidence.parquet"]
    for period in ("policy_2024", "diagnostic_2025_2026"):
        required.append(args.root / "dispatch_review_v2" / period / "members.parquet")
    lookback = args.start - timedelta(hours=72)
    journals = [args.root / "source_v2" / f"journal_{year}.parquet"
                for year in range(lookback.year, args.end.year + 1)]
    required.extend(journals)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    temp = args.output / "duckdb_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={quoted(temp)}")
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv({quoted(args.catalog)})")
    con.execute("CREATE TEMP TABLE object_channels AS SELECT "
                '"ид_канала_данных" channel_id,"ид_объект" object_id,'
                '"тип_датчика" sensor_type,"название_датчика" channel_name '
                'FROM catalog WHERE "ид_объект"=?', [args.object_id])
    channel_count = con.execute("SELECT count(*) FROM object_channels").fetchone()[0]
    if channel_count == 0:
        raise ValueError("Объект отсутствует в текущем справочнике каналов")
    journal_list = "[" + ",".join(quoted(path) for path in journals) + "]"
    con.execute(f"CREATE VIEW journal AS SELECT * FROM read_parquet({journal_list})")
    con.execute("""
        CREATE TEMP TABLE raw_window AS
        SELECT j.event_time,j.event_id,j.channel_id,j.sensor_value,j.is_alarm,
               c.object_id,c.sensor_type,c.channel_name
        FROM journal j JOIN object_channels c USING(channel_id)
        WHERE j.event_time>=? AND j.event_time<?
    """, [lookback, args.end])
    con.execute("""
        CREATE TEMP TABLE stream AS
        SELECT event_time,10 sort_order,'reading' event_kind,object_id,channel_id,
               concat('journal:',channel_id::VARCHAR,':',event_id::VARCHAR) source_id,
               to_json(struct_pack(event_id:=event_id,
                    sensor_value:=sensor_value,is_alarm:=is_alarm,
                    sensor_type:=sensor_type,channel_name:=channel_name,
                    source_ref:=concat('source_v2/journal_',year(event_time)::VARCHAR,
                      '.parquet'))) payload,
               'source_event_time' availability_basis
        FROM raw_window WHERE event_time>=?
    """, [args.start])

    con.execute(f"CREATE VIEW situations AS SELECT * FROM read_parquet("
                f"{quoted(args.root / 'observed_v1' / 'situations.parquet')})")
    con.execute(f"CREATE VIEW evidence AS SELECT * FROM read_parquet("
                f"{quoted(args.root / 'observed_v1' / 'evidence.parquet')})")
    con.execute("""
        INSERT INTO stream
        SELECT CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN e.event_time+INTERVAL 1 HOUR ELSE e.event_time END,
               25,'observed_signal',s.object_id,e.channel_id,
               concat('evidence:',e.evidence_kind,':',e.channel_id::VARCHAR,':',
                      strftime(e.event_time,'%Y%m%dT%H%M%S'),':',
                      coalesce(e.event_id::VARCHAR,'none')),
               to_json(struct_pack(evidence_kind:=e.evidence_kind,
                   channel_id:=e.channel_id,source_time:=e.event_time,
                   observed_value:=e.observed_value,
                   numeric_value:=e.numeric_value,
                   source_ref:=e.source_ref,
                   final_group_not_yet_known:=true)),
               CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN 'gas_hour_closed' ELSE 'source_event_time' END
        FROM evidence e JOIN situations s USING(situation_id)
        WHERE s.object_id=? AND
          (CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                THEN e.event_time+INTERVAL 1 HOUR ELSE e.event_time END)>=?
          AND (CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                THEN e.event_time+INTERVAL 1 HOUR ELSE e.event_time END)<?
    """, [args.object_id,args.start,args.end])
    con.execute("""
        CREATE TEMP TABLE situation_ready AS
        SELECT s.situation_id,s.situation_kind,s.object_id,s.first_seen,s.last_seen,
               s.location_key,s.affected_channels,s.signal_records,s.limitations,
               s.multi_channel_campaign,
               greatest(s.last_seen,max(CASE
                   WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                   THEN e.event_time+INTERVAL 1 HOUR
                   ELSE e.event_time END))+
                   INTERVAL 1 HOUR+INTERVAL 1 SECOND event_time,
               count(e.situation_id) evidence_count
        FROM situations s JOIN evidence e USING(situation_id)
        WHERE s.object_id=?
        GROUP BY s.situation_id,s.situation_kind,s.object_id,s.first_seen,
                 s.last_seen,s.location_key,s.affected_channels,s.signal_records,
                 s.limitations,s.multi_channel_campaign
    """, [args.object_id])
    con.execute("""
        INSERT INTO stream
        SELECT event_time,30,'situation_ready',object_id,NULL,situation_id,
               to_json(struct_pack(situation_id:=situation_id,
                   situation_kind:=situation_kind,first_seen:=first_seen,
                   last_seen:=last_seen,location_key:=location_key,
                   affected_channels:=affected_channels,signal_records:=signal_records,
                   evidence_count:=evidence_count,limitations:=limitations,
                   multi_channel_campaign:=multi_channel_campaign,
                   fire_confirmed:=CAST(NULL AS BOOLEAN))),
               'all_source_evidence_available;one_hour_group_closure;gas_hour_closed'
        FROM situation_ready WHERE event_time>=? AND event_time<?
    """, [args.start,args.end])
    members = [args.root / "dispatch_review_v2" / period / "members.parquet"
               for period in ("policy_2024", "diagnostic_2025_2026")]
    con.execute("CREATE VIEW members AS SELECT * FROM read_parquet(["
                + ",".join(quoted(path) for path in members) + "])")
    missing = con.execute("SELECT count(*) FROM members m LEFT JOIN situation_ready s "
                          "ON m.situation_id=s.situation_id WHERE m.object_id=? "
                          "AND m.basis_kind='observed_status' AND s.situation_id IS NULL",
                          [args.object_id]).fetchone()[0]
    if missing:
        raise ValueError(f"У {missing} наблюдаемых черновиков нет исходной ситуации")
    con.execute("""
        INSERT INTO stream
        SELECT CASE WHEN m.basis_kind='observed_status' THEN s.event_time
                    ELSE m.obs_time END,40,'draft_created',m.object_id,
               m.channel_id,m.draft_id,
               to_json(struct_pack(draft_id:=m.draft_id,group_id:=m.group_id,
                   basis_kind:=m.basis_kind,channel_id:=m.channel_id,
                   model_version:=m.model_version,score:=m.score,
                   source_obs_time:=m.obs_time,
                   target_kind:=m.target_kind,review_status:=m.review_status,
                   limitations:=m.limitations)),
               CASE WHEN m.basis_kind='observed_status'
                    THEN 'batch_situation_closed_before_draft'
                    ELSE 'batch_inference_obs_time;model_inputs_checked_separately' END
        FROM members m LEFT JOIN situation_ready s
          ON m.basis_kind='observed_status' AND m.situation_id=s.situation_id
        WHERE m.object_id=? AND
          (CASE WHEN m.basis_kind='observed_status' THEN s.event_time
                ELSE m.obs_time END)>=? AND
          (CASE WHEN m.basis_kind='observed_status' THEN s.event_time
                ELSE m.obs_time END)<?
    """, [args.object_id,args.start,args.end])

    con.execute("""
        CREATE TEMP TABLE channel_times AS
        SELECT DISTINCT channel_id,event_time FROM raw_window
    """)
    con.execute("""
        CREATE TEMP TABLE ordered_times AS
        SELECT channel_id,event_time,
               lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time)
                   previous_time,
               lead(event_time) OVER(PARTITION BY channel_id ORDER BY event_time)
                   next_time
        FROM channel_times
    """)
    con.execute("""
        INSERT INTO stream
        SELECT ?,0,'coverage_baseline',c.object_id,c.channel_id,
               concat('coverage:start:',c.channel_id::VARCHAR),
               to_json(struct_pack(channel_id:=c.channel_id,
                   sensor_type:=c.sensor_type,
                   observation_state:=CASE WHEN b.last_time IS NULL
                        THEN 'no_record_in_previous_72h'
                        ELSE 'observed_in_previous_72h' END,
                   last_event_time:=b.last_time,
                   meaning:='availability_of_records_not_equipment_health')),
               'previous_72h_only'
        FROM object_channels c LEFT JOIN (
            SELECT channel_id,max(event_time) last_time FROM raw_window
            WHERE event_time<? GROUP BY channel_id
        ) b USING(channel_id)
    """, [args.start,args.start])
    con.execute("""
        INSERT INTO stream
        SELECT event_time,20,'coverage_restored',c.object_id,t.channel_id,
               concat('coverage:restore:',t.channel_id::VARCHAR,':',
                      strftime(event_time,'%Y%m%dT%H%M%S')),
               to_json(struct_pack(channel_id:=t.channel_id,
                   previous_event_time:=previous_time,
                   observation_state:='observed_in_previous_72h',
                   meaning:='new_record_after_gap_not_repair')),
               'source_event_time'
        FROM ordered_times t JOIN object_channels c USING(channel_id)
        WHERE t.event_time>=? AND
          (t.previous_time IS NULL OR
           t.event_time>t.previous_time+INTERVAL 72 HOUR+INTERVAL 1 SECOND)
    """, [args.start])
    con.execute("""
        INSERT INTO stream
        SELECT t.event_time+INTERVAL 72 HOUR+INTERVAL 1 SECOND,15,
               'coverage_lost',c.object_id,t.channel_id,
               concat('coverage:lost:',t.channel_id::VARCHAR,':',
                      strftime(t.event_time,'%Y%m%dT%H%M%S')),
               to_json(struct_pack(channel_id:=t.channel_id,
                   last_event_time:=t.event_time,
                   observation_state:='no_record_in_previous_72h',
                   meaning:='silence_not_proof_of_sensor_failure')),
               'elapsed_72h_without_new_record'
        FROM ordered_times t JOIN object_channels c USING(channel_id)
        WHERE t.event_time+INTERVAL 72 HOUR+INTERVAL 1 SECOND>=?
          AND t.event_time+INTERVAL 72 HOUR+INTERVAL 1 SECOND<?
          AND (t.next_time IS NULL OR
               t.next_time>t.event_time+INTERVAL 72 HOUR+INTERVAL 1 SECOND)
    """, [args.start,args.end])
    con.execute("""
        CREATE TEMP TABLE ordered_stream AS
        SELECT row_number() OVER(ORDER BY event_time,sort_order,source_id,
                  coalesce(channel_id,-1),payload::VARCHAR) seq,
               event_time,sort_order,event_kind,object_id,channel_id,
               source_id,payload,availability_basis
        FROM stream
    """)
    con.execute(f"COPY ordered_stream TO {quoted(args.output / 'timeline.parquet')} "
                "(FORMAT PARQUET,COMPRESSION ZSTD)")
    counts = con.execute("SELECT event_kind,count(*) FROM ordered_stream "
                         "GROUP BY 1 ORDER BY 1").fetchall()
    fire_manifest = args.root / "observed_v1" / "fire_history_manifest.json"
    fire = json.loads(fire_manifest.read_text(encoding="utf-8"))
    manifest = {
        "schema_version":"replay_v1", "object_id":args.object_id,
        "start":args.start.isoformat(sep=" "), "end_exclusive":args.end.isoformat(sep=" "),
        "catalog_channels":channel_count, "event_counts":dict(counts),
        "source_clock":"event_time_without_timezone_or_delivery_time",
        "delivery_time_available":False,"historical_feedback_available":False,
        "feedback_state":"NO_REAL_DISPATCHER_DECISIONS",
        "coverage_window_hours":72,
        "coverage_meaning":"record_recency_not_physical_health",
        "catalog_metadata_time":"current_snapshot_not_proven_historical_at_replay_time",
        "situation_release_rule":"signals at source time or gas hour close; "
                                 "final batch card one hour and one second after last evidence",
        "batch_revision_possible":True,
        "confirmed_fire_register_available":fire["confirmed_fire_register_available"],
        "real_fire_count":None,
        "source_limits":"Current catalog cannot assign unknown historical channels to an object. "
                        "Names and types come from the current catalog snapshot. "
                        "Batch situation grouping may change after late data; delivery order unknown."
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"timeline":str(args.output / "timeline.parquet"),
                      "event_counts":dict(counts)},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
