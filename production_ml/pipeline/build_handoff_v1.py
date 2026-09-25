"""Единый выпуск ML/data: происхождение, время доступности и схемы файлов."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import duckdb


VERSION = "ml_handoff_v1"


def quoted(path):
    return "'" + path.as_posix().replace("'", "''") + "'"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--states", type=Path,
                        default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_состояний.csv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = args.root
    output = args.output or root / "handoff_v1"
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "channels":"sensor_coverage_v1/channels.csv",
        "snapshots":"its_evidence_v1/channel_history.parquet",
        "situations":"observed_v1/situations.parquet",
        "evidence":"observed_v1/evidence.parquet",
        "navigation":"visualization_v1/situation_navigation.parquet",
        "object_day":"visualization_v1/object_day.parquet",
        "object_type_day":"visualization_v1/object_type_day.parquet",
        "coverage_monthly":"visualization_v1/coverage_monthly.parquet",
        "quality_daily":"visualization_v1/forecast_quality_daily.parquet",
        "gas_daily":"visualization_v1/gas_daily.parquet",
    }
    for period in ("policy_2024", "diagnostic_2025_2026"):
        paths[f"members_{period}"] = f"dispatch_review_v2/{period}/members.parquet"
        paths[f"groups_{period}"] = f"dispatch_review_v2/{period}/groups.parquet"
    for relative in paths.values():
        if not (root / relative).is_file():
            raise FileNotFoundError(root / relative)
    if not args.states.is_file():
        raise FileNotFoundError(args.states)
    for name in ("fire_history_view.json", "feedback_availability.json"):
        if not (root / "visualization_v1" / name).is_file():
            raise FileNotFoundError(root / "visualization_v1" / name)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    temp = output / "duckdb_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={quoted(temp)}")
    for name,relative in paths.items():
        reader = "read_csv" if relative.endswith(".csv") else "read_parquet"
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM {reader}("
                    f"{quoted(root / relative)})")
    con.execute("CREATE VIEW members AS SELECT * FROM members_policy_2024 "
                "UNION ALL SELECT * FROM members_diagnostic_2025_2026")
    con.execute("CREATE VIEW groups AS SELECT * FROM groups_policy_2024 "
                "UNION ALL SELECT * FROM groups_diagnostic_2025_2026")
    con.execute(f"CREATE VIEW states AS SELECT * FROM read_csv({quoted(args.states)})")
    catalog = Path(__file__).resolve().parents[4] / "dataset" / "справочник_каналов_датчиков.csv"
    if not catalog.is_file():
        raise FileNotFoundError(catalog)
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv({quoted(catalog)})")
    con.execute("""
        CREATE TABLE state_dictionary AS
        SELECT 'ml_handoff_v1' schema_version,
               "тип_датчика" sensor_type,
               "ид_набор_состояний" state_set_id,
               "название_состояния" state_text,
               "тревожное" dictionary_alarm,
               'dataset/справочник_состояний.csv' source_file
        FROM states;

        CREATE TABLE observation_snapshots AS
        SELECT 'ml_handoff_v1' schema_version,
               h.channel_id,h.object_id,h.sensor_type,h.channel_name,
               h.in_catalog,h.snapshot_date,h.as_of available_at,
               CASE WHEN h.first_event_time<=h.as_of
                    THEN h.first_event_time ELSE NULL END first_known_event_time,
               h.last_event_time,h.last_event_id,h.last_value,h.last_is_alarm,
               CASE WHEN h.last_event_time IS NOT NULL THEN
                   concat('source_v2/journal_',year(h.last_event_time)::VARCHAR,
                     '.parquet:channel_id+event_time+event_id+sensor_value+is_alarm')
                    ELSE NULL END last_source_ref,
               h.last_text_time,h.last_text_status,h.last_text_alarm,
               CASE WHEN h.last_text_time IS NOT NULL THEN
                   concat('source_v2/journal_',year(h.last_text_time)::VARCHAR,
                     '.parquet:channel_id+event_time+sensor_value+is_alarm')
                    ELSE NULL END last_text_source_ref,
               h.observation_state,h.dictionary_state,
               h.alarm_variants dictionary_alarm_variants,
               h.state_sets dictionary_state_sets,
               h.event_count_72h,h.fault_reports_72h,h.service_reports_72h,
               h.conflicting_status_keys_72h,h.mixed_alarm_timestamps_72h,
               h.hours_since_last_event,h.its_value,h.its_status,h.its_reason,
               'its_evidence_v1' calculation_version,
               CASE WHEN h.dictionary_state IN
                  ('listed_consistently','source_dictionary_disagreement',
                   'dictionary_conflict')
                    THEN 'dataset/справочник_состояний.csv:тип_датчика+название_состояния'
                    ELSE NULL END dictionary_source_ref
        FROM snapshots h;

        CREATE TABLE channel_current AS
        WITH latest AS (
            SELECT * FROM observation_snapshots
            WHERE snapshot_date=(SELECT max(snapshot_date) FROM observation_snapshots)
        )
        SELECT 'ml_handoff_v1' schema_version,c.channel_id,c.as_of available_at,
               c.object_id,c.sensor_type,c.in_catalog,l.channel_name,
               c.forecast_capability,c.forecast_model_version,
               c.forecast_target_kind,c.forecast_reason,c.forecast_reason_text,
               c.observed_event_capability,c.observed_event_reason,
               c.chart_capability,c.chart_reason,c.recent_input_context,
               c.observation_state coverage_observation_state,
               l.observation_state detailed_observation_state,
               l.dictionary_state,l.last_text_status,l.last_text_alarm,
               l.last_text_source_ref,l.dictionary_source_ref,
               l.its_value,l.its_status,l.its_reason,
               c.last_event_time,c.last_recorded_value,c.last_recorded_is_alarm,
               l.last_source_ref,
               'sensor_coverage_v1+its_evidence_v1' calculation_version
        FROM channels c LEFT JOIN latest l USING(channel_id);

        CREATE TABLE situation_availability AS
        SELECT s.situation_id,
               greatest(s.last_seen,max(CASE
                   WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                   THEN e.event_time+INTERVAL 1 HOUR
                   ELSE e.event_time END))+
                   INTERVAL 1 HOUR+INTERVAL 1 SECOND available_at,
               count(*) evidence_count
        FROM situations s JOIN evidence e USING(situation_id)
        GROUP BY 1,s.last_seen;

        CREATE TABLE situation_cards AS
        SELECT 'ml_handoff_v1' schema_version,s.situation_id,s.object_id,
               n.object_name,s.situation_kind,n.sensor_type,
               s.first_seen source_first_seen,s.last_seen source_last_seen,
               a.available_at,s.location_key,s.affected_channels,
               s.signal_records,a.evidence_count,s.multi_channel_campaign,
               s.numeric_unit,s.stated_threshold,s.numeric_max,
               s.limitations,n.review_link_state,n.draft_id,n.group_id,
               'observed_v1' calculation_version,
               'observed_v1/situations.parquet:situation_id' source_ref,
               CAST(NULL AS BOOLEAN) confirmed_physical_incident
        FROM situations s JOIN situation_availability a USING(situation_id)
        LEFT JOIN navigation n USING(situation_id);

        CREATE TABLE evidence_dictionary AS
        SELECT "тип_датчика" sensor_type,
               "название_состояния" state_text,
               count(DISTINCT "тревожное") alarm_variants,
               bool_or("тревожное") dictionary_alarm,
               count(DISTINCT "ид_набор_состояний") state_sets
        FROM states GROUP BY 1,2;

        CREATE TABLE situation_evidence AS
        SELECT 'ml_handoff_v1' schema_version,e.situation_id,
               s.object_id,e.channel_id,c."тип_датчика" sensor_type,
               e.evidence_kind,e.event_time source_time,
               CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN e.event_time+INTERVAL 1 HOUR
                    ELSE e.event_time END available_at,
               e.event_id,e.observed_value,e.numeric_value,e.numeric_unit,
               CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN CAST(NULL AS BOOLEAN) ELSE true END source_alarm,
               e.source_ref,e.channel_name,e.piket,
               CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY'
                    THEN 'not_applicable_numeric'
                    WHEN d.alarm_variants IS NULL THEN 'not_listed_for_type'
                    WHEN d.alarm_variants>1 THEN 'dictionary_conflict'
                    WHEN NOT d.dictionary_alarm THEN 'source_dictionary_disagreement'
                    ELSE 'listed_consistently' END dictionary_state,
               d.alarm_variants dictionary_alarm_variants,
               d.state_sets dictionary_state_sets,
               CASE WHEN d.alarm_variants IS NOT NULL
                    THEN 'dataset/справочник_состояний.csv:тип_датчика+название_состояния'
                    ELSE NULL END dictionary_source_ref,
               'observed_v1' calculation_version
        FROM evidence e JOIN situations s USING(situation_id)
        LEFT JOIN catalog c ON e.channel_id=c."ид_канала_данных"
        LEFT JOIN evidence_dictionary d ON c."тип_датчика"=d.sensor_type
          AND e.observed_value=d.state_text;

        CREATE TABLE draft_cards AS
        SELECT 'ml_handoff_v1' schema_version,m.draft_id,m.group_id,
               m.object_id,m.channel_id,m.basis_kind,m.model_version,
               m.score,m.forecast_horizon_hours,m.target_kind,
               m.obs_time source_obs_time,
               CASE WHEN m.basis_kind='observed_status' THEN a.available_at
                    ELSE m.obs_time END available_at,
               m.review_status,m.situation_id,m.location_key,m.limitations,
               m.affected_channels,
               d.observation_state channel_observation_state,
               d.fault_reports_72h,d.service_reports_72h,
               d.mixed_alarm_timestamps_72h,d.last_source_ref,
               d.its_value,d.its_status,
               'dispatch_review_v2' calculation_version,
               CASE WHEN m.obs_time<'2025-01-01'
                    THEN 'dispatch_review_v2/policy_2024/members.parquet:draft_id'
                    ELSE 'dispatch_review_v2/diagnostic_2025_2026/members.parquet:draft_id'
                    END source_ref
        FROM members m LEFT JOIN situation_availability a
          ON m.situation_id=a.situation_id
        LEFT JOIN (
            SELECT draft_id,observation_state,fault_reports_72h,
                   service_reports_72h,mixed_alarm_timestamps_72h,
                   its_value,its_status,
                   CASE WHEN last_event_time IS NOT NULL THEN
                     concat('source_v2/journal_',year(last_event_time)::VARCHAR,
                       '.parquet:channel_id+event_time+event_id+sensor_value+is_alarm')
                     ELSE NULL END last_source_ref
            FROM read_parquet('DRAFT_CONTEXT_PATH')
        ) d USING(draft_id);

        CREATE TABLE group_cards AS
        SELECT 'ml_handoff_v1' schema_version,g.group_id,g.object_id,
               g.first_obs_time source_first_obs_time,
               g.last_obs_time source_last_obs_time,
               max(d.available_at)+INTERVAL 1 HOUR+INTERVAL 1 SECOND available_at,
               g.draft_count,g.forecast_count,g.observed_count,
               g.primary_channel_count,g.known_location_count,
               g.review_status,'dispatch_review_v2' calculation_version,
               CASE WHEN g.first_obs_time<'2025-01-01'
                    THEN 'dispatch_review_v2/policy_2024/groups.parquet:group_id'
                    ELSE 'dispatch_review_v2/diagnostic_2025_2026/groups.parquet:group_id'
                    END source_ref
        FROM groups g JOIN draft_cards d USING(group_id)
        GROUP BY g.group_id,g.object_id,g.first_obs_time,g.last_obs_time,
                 g.draft_count,g.forecast_count,g.observed_count,
                 g.primary_channel_count,g.known_location_count,g.review_status;
    """.replace("DRAFT_CONTEXT_PATH",(root / "its_evidence_v1" /
                                    "draft_context.parquet").as_posix()))
    derived = ("state_dictionary","observation_snapshots","channel_current",
               "situation_cards","situation_evidence","draft_cards","group_cards")
    for name in derived:
        con.execute(f"COPY {name} TO {quoted(output / (name + '.parquet'))} "
                    "(FORMAT PARQUET,COMPRESSION ZSTD)")
    cases_root = root / "visualization_v1" / "cases"
    case_folders = sorted(folder for folder in cases_root.iterdir()
                          if folder.is_dir() and (folder / "points.parquet").is_file()
                          and (folder / "case_meta.json").is_file())
    if not case_folders:
        raise FileNotFoundError("Нет примеров графиков visualization_v1/cases")
    case_selects = []
    case_meta = []
    for folder in case_folders:
        meta = json.loads((folder / "case_meta.json").read_text(encoding="utf-8"))
        case_meta.append({"folder":folder.name,"case_id":meta["case_id"],
                          "view_at":meta["view_at"],"kind":meta["kind"]})
        case_id = meta["case_id"].replace("'","''")
        view_at = meta["view_at"].replace("'","''")
        case_selects.append(f"SELECT '{VERSION}' schema_version,"
                            f"'{case_id}' case_id,TIMESTAMP '{view_at}' view_at,"
                            "'visualization_v1_case_chart' calculation_version,"
                            f"p.* FROM read_parquet({quoted(folder / 'points.parquet')}) p")
    con.execute("CREATE TABLE chart_examples AS " + " UNION ALL ".join(case_selects))
    con.execute(f"COPY chart_examples TO {quoted(output / 'chart_examples.parquet')} "
                "(FORMAT PARQUET,COMPRESSION ZSTD)")
    (output / "chart_example_index.json").write_text(
        json.dumps({"schema_version":VERSION,"cases":case_meta},
                   ensure_ascii=False,indent=2),encoding="utf-8")
    fire = json.loads((root / "visualization_v1" / "fire_history_view.json")
                      .read_text(encoding="utf-8"))
    fire.update({"schema_version":VERSION,"calculation_version":"fire_history_v1",
                 "source_ref":"observed_v1/fire_history_manifest.json;"
                              "observed_v1/smoke_signal_statistics.csv",
                 "available_at":None,"data_cutoff":"2026-06-30 23:59:59"})
    (output / "fire_history_view.json").write_text(
        json.dumps(fire,ensure_ascii=False,indent=2),encoding="utf-8")
    feedback = json.loads((root / "visualization_v1" / "feedback_availability.json")
                          .read_text(encoding="utf-8"))
    feedback.update({"schema_version":VERSION,
                     "source_ref":"no_real_dispatcher_feedback_source",
                     "available_at":None})
    (output / "feedback_availability.json").write_text(
        json.dumps(feedback,ensure_ascii=False,indent=2),encoding="utf-8")

    resources = {
        "channel_current":("handoff_v1/channel_current.parquet",["channel_id"],"available_at"),
        "observation_snapshots":("handoff_v1/observation_snapshots.parquet",
                                 ["channel_id","snapshot_date"],"available_at"),
        "state_dictionary":("handoff_v1/state_dictionary.parquet",[],None),
        "situations":("handoff_v1/situation_cards.parquet",["situation_id"],"available_at"),
        "situation_evidence":("handoff_v1/situation_evidence.parquet",[],"available_at"),
        "drafts":("handoff_v1/draft_cards.parquet",["draft_id"],"available_at"),
        "groups":("handoff_v1/group_cards.parquet",["group_id"],"available_at"),
        "overview_object_day":(paths["object_day"],["object_id","activity_date"],None),
        "overview_object_type_day":(paths["object_type_day"],
                                    ["object_id","sensor_type","activity_date"],None),
        "coverage_object_type_month":(paths["coverage_monthly"],
                                      ["snapshot_date","object_id","sensor_type"],None),
        "forecast_quality_daily":(paths["quality_daily"],[],None),
        "gas_daily":(paths["gas_daily"],
                     ["channel_id","activity_date"],None),
        "chart_examples":("handoff_v1/chart_examples.parquet",[],"view_at"),
        "replay_timeline_example":("replay_v1/observed_draft/timeline.parquet",
                                   ["seq"],"event_time"),
    }
    schema = {"schema_version":VERSION,
              "clock":"event_time_without_source_timezone_or_delivery_time",
              "data_cutoff":"2026-06-30 23:59:59",
              "resources":{}}
    for name,(relative,keys,available) in resources.items():
        file = root / relative
        if not file.is_file():
            raise FileNotFoundError(file)
        relation = f"read_parquet({quoted(file)})"
        fields = con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        schema["resources"][name] = {
            "path":relative,"format":"parquet","key":keys,
            "availability_field":available,
            "rows":con.execute(f"SELECT count(*) FROM {relation}").fetchone()[0],
            "bytes":file.stat().st_size,"sha256":digest(file),
            "fields":[{"name":row[0],"type":row[1],
                       "nullable":row[2]=="YES"} for row in fields],
        }
    schema["resources"]["forecast_quality_daily"]["usage"] = "retrospective_only"
    for name in ("overview_object_day","overview_object_type_day",
                 "coverage_object_type_month","gas_daily"):
        schema["resources"][name]["usage"] = "historical_aggregate_not_live_as_of"
    schema["resources"]["chart_examples"]["usage"] = "examples_only_generate_per_case"
    schema["resources"]["replay_timeline_example"]["usage"] = "scenario_example"
    schema["json_resources"] = {
        "fire_history":"handoff_v1/fire_history_view.json",
        "feedback_availability":"handoff_v1/feedback_availability.json",
        "chart_example_index":"handoff_v1/chart_example_index.json",
        "replay_scenarios":"../pipeline/replay_scenarios_v1.json",
    }
    (output / "schema_manifest.json").write_text(
        json.dumps(schema,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"schema_version":VERSION,
                      "resources":len(resources),
                      "rows":{name:item["rows"] for name,item in schema["resources"].items()}},
                     ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
