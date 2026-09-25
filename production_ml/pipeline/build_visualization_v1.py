"""Данные сводок и графиков для пункта 6 без кода интерфейса."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def quote(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_каналов_датчиков.csv")
    parser.add_argument("--objects", type=Path, default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_объектов_диспетчер.csv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = args.root
    output = args.output or root / "visualization_v1"
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "situations": root / "observed_v1" / "situations.parquet",
        "phase_labels": root / "power_phase_v2" / "labels.parquet",
        "pump_labels": root / "pump_v1" / "labels.parquet",
        "coverage": root / "its_evidence_v1" / "object_type_history.parquet",
        "fire_manifest": root / "observed_v1" / "fire_history_manifest.json",
        "smoke_stats": root / "observed_v1" / "smoke_signal_statistics.csv",
    }
    for period in ("policy_2024", "diagnostic_2025_2026"):
        paths[f"members_{period}"] = root / "dispatch_review_v2" / period / "members.parquet"
        paths[f"groups_{period}"] = root / "dispatch_review_v2" / period / "groups.parquet"
        paths[f"mapping_{period}"] = root / "dispatch_review_v2" / period / "observed_mapping.parquet"
    for path in (*paths.values(), args.catalog, args.objects):
        if not path.exists():
            raise FileNotFoundError(path)
    gas_files = sorted((root / "gas_v1").glob("hourly_20??.parquet"))
    if not gas_files:
        raise FileNotFoundError(root / "gas_v1")
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    temp = output / "duckdb_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={quote(temp)}")
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv({quote(args.catalog)})")
    con.execute(f"CREATE VIEW object_names AS SELECT * FROM read_csv({quote(args.objects)})")
    for name in ("situations", "phase_labels", "pump_labels", "coverage"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet({quote(paths[name])})")
    for kind in ("members", "groups", "mapping"):
        a = paths[f"{kind}_policy_2024"]
        b = paths[f"{kind}_diagnostic_2025_2026"]
        con.execute(f"CREATE VIEW {kind} AS SELECT * FROM read_parquet([{quote(a)},{quote(b)}])")
    gas_list = "[" + ",".join(quote(path) for path in gas_files) + "]"
    con.execute(f"CREATE VIEW gas_hourly AS SELECT * FROM read_parquet({gas_list})")
    con.execute("""
        CREATE TABLE objects AS
        SELECT DISTINCT c."ид_объект" object_id,
               o."диспетчерское_название_объекта" object_name
        FROM catalog c LEFT JOIN object_names o
          ON c."ид_объект"=o."ид_объект";

        CREATE TABLE draft_facts AS
        SELECT m.*,c."тип_датчика" sensor_type
        FROM members m LEFT JOIN catalog c ON m.channel_id=c."ид_канала_данных";

        CREATE TABLE situation_facts AS
        SELECT *,CASE
            WHEN situation_kind LIKE 'OBSERVED_SMOKE%' THEN 'Датчик дыма'
            WHEN situation_kind LIKE 'OBSERVED_GAS%' THEN 'Газовый датчик'
            WHEN situation_kind='OBSERVED_PUMP_FLOODED_STATUS' THEN 'Состояние насоса'
            WHEN situation_kind='OBSERVED_UPS_BATTERY_LOW_STATUS' THEN 'ИБП'
            WHEN situation_kind='OBSERVED_TEMPERATURE_HIGH_STATUS'
              THEN 'Датчик температуры'
            WHEN situation_kind='OBSERVED_MANUAL_LEVER_STATUS'
              THEN 'Состояние УИР-Р'
            ELSE NULL END sensor_type
        FROM situations;

        CREATE TABLE calendar AS
        SELECT d::DATE activity_date
        FROM generate_series((SELECT min(first_seen)::DATE FROM situations),
            (SELECT max(first_seen)::DATE FROM situations),INTERVAL 1 DAY) x(d);

        CREATE TABLE object_day AS
        WITH d AS (
            SELECT object_id,obs_time::DATE activity_date,count(*) draft_count,
                   count(*) FILTER(WHERE basis_kind='forecast') forecast_drafts,
                   count(*) FILTER(WHERE basis_kind='observed_status') observed_drafts,
                   count(*) FILTER(WHERE review_status='draft') pending_drafts
            FROM draft_facts GROUP BY 1,2
        ), g AS (
            SELECT object_id,first_obs_time::DATE activity_date,count(*) review_groups,
                   count(*) FILTER(WHERE draft_count>1) multi_draft_groups
            FROM groups GROUP BY 1,2
        ), s AS (
            SELECT object_id,first_seen::DATE activity_date,count(*) observed_situations,
                   count(*) FILTER(WHERE situation_kind LIKE 'OBSERVED_SMOKE%') smoke_situations,
                   count(*) FILTER(WHERE situation_kind LIKE 'OBSERVED_GAS%') gas_situations,
                   count(*) FILTER(WHERE multi_channel_campaign) mass_situations
            FROM situation_facts GROUP BY 1,2
        )
        SELECT cal.activity_date,o.object_id,o.object_name,
               coalesce(d.draft_count,0) draft_count,
               coalesce(d.forecast_drafts,0) forecast_drafts,
               coalesce(d.observed_drafts,0) observed_drafts,
               coalesce(d.pending_drafts,0) pending_drafts,
               coalesce(g.review_groups,0) review_groups,
               coalesce(g.multi_draft_groups,0) multi_draft_groups,
               coalesce(s.observed_situations,0) observed_situations,
               coalesce(s.smoke_situations,0) smoke_situations,
               coalesce(s.gas_situations,0) gas_situations,
               coalesce(s.mass_situations,0) mass_situations
        FROM calendar cal CROSS JOIN objects o
        LEFT JOIN d USING(object_id,activity_date)
        LEFT JOIN g USING(object_id,activity_date)
        LEFT JOIN s USING(object_id,activity_date);

        CREATE TABLE object_type_day AS
        WITH d AS (
            SELECT object_id,sensor_type,obs_time::DATE activity_date,
                   count(*) draft_count,
                   count(*) FILTER(WHERE basis_kind='forecast') forecast_drafts,
                   count(*) FILTER(WHERE basis_kind='observed_status') observed_drafts
            FROM draft_facts GROUP BY 1,2,3
        ), s AS (
            SELECT object_id,sensor_type,first_seen::DATE activity_date,
                   count(*) observed_situations
            FROM situation_facts GROUP BY 1,2,3
        )
        SELECT coalesce(d.object_id,s.object_id) object_id,
               coalesce(d.sensor_type,s.sensor_type) sensor_type,
               coalesce(d.activity_date,s.activity_date) activity_date,
               coalesce(d.draft_count,0) draft_count,
               coalesce(d.forecast_drafts,0) forecast_drafts,
               coalesce(d.observed_drafts,0) observed_drafts,
               coalesce(s.observed_situations,0) observed_situations
        FROM d FULL OUTER JOIN s USING(object_id,sensor_type,activity_date);

        CREATE TABLE shift_workload AS
        SELECT date_trunc('day',first_obs_time)+
                 CASE WHEN hour(first_obs_time)<12 THEN INTERVAL 0 HOUR
                      ELSE INTERVAL 12 HOUR END shift_start,
               object_id,count(*) review_groups,sum(draft_count) draft_count,
               sum(forecast_count) forecast_drafts,sum(observed_count) observed_drafts
        FROM groups GROUP BY 1,2;

        CREATE TABLE coverage_monthly AS
        SELECT c.*,o.object_name FROM coverage c
        LEFT JOIN objects o USING(object_id);

        CREATE TABLE situation_navigation AS
        SELECT s.situation_id,s.situation_kind,s.sensor_type,s.object_id,
               o.object_name,s.first_seen,s.last_seen,s.location_key,
               s.signal_records,s.affected_channels,s.limitations,
               s.multi_channel_campaign,m.selected_draft,
               d.draft_id,d.group_id,
               CASE WHEN d.draft_id IS NOT NULL AND m.selected_draft
                    THEN 'draft_created'
                    WHEN d.draft_id IS NOT NULL THEN 'update_of_existing_draft'
                    ELSE 'information_only' END review_link_state
        FROM situation_facts s LEFT JOIN objects o USING(object_id)
        LEFT JOIN mapping m ON s.situation_id=m.source_situation_id
        LEFT JOIN members d ON m.draft_situation_id=d.situation_id;

        CREATE TABLE forecast_quality_daily AS
        WITH labeled AS (
            SELECT d.*,l.training_eligible,l.target_1_48h
            FROM draft_facts d LEFT JOIN phase_labels l USING(channel_id,obs_time)
            WHERE d.model_version='power_phase_scada_v2'
            UNION ALL
            SELECT d.*,l.training_eligible,l.target_1_48h
            FROM draft_facts d LEFT JOIN pump_labels l USING(channel_id,obs_time)
            WHERE d.model_version='pump_scada_v1'
        )
        SELECT obs_time::DATE activity_date,object_id,sensor_type,model_version,
               count(*) forecast_drafts,
               count(*) FILTER(WHERE training_eligible) evaluable_drafts,
               count(*) FILTER(WHERE training_eligible AND target_1_48h=1)
                   matched_scada_drafts,
               count(*) FILTER(WHERE NOT coalesce(training_eligible,false))
                   unevaluable_drafts
        FROM labeled GROUP BY 1,2,3,4;

        CREATE TABLE gas_daily AS
        SELECT channel_id,object_id,obs_time::DATE activity_date,
               count(*) recorded_hours,sum(numeric_count) source_measurements,
               min(numeric_min) numeric_min,max(numeric_max) numeric_max,
               avg(numeric_median) mean_of_hourly_medians,
               count(*) FILTER(WHERE numeric_max>=1.0) hours_at_or_above_stated_threshold,
               sum(negative_count) negative_measurements,
               'vol_percent_methane' numeric_unit,
               1.0 stated_device_threshold,
               'maintenance_schedule_unavailable' maintenance_context
        FROM gas_hourly GROUP BY 1,2,3;
    """)
    for table in ("object_day", "object_type_day", "shift_workload", "coverage_monthly",
                  "situation_navigation", "forecast_quality_daily", "gas_daily"):
        con.execute(f"COPY {table} TO {quote(output / (table + '.parquet'))} "
                    "(FORMAT PARQUET,COMPRESSION ZSTD)")
    fire = json.loads(paths["fire_manifest"].read_text(encoding="utf-8"))
    smoke = con.execute(f"SELECT * FROM read_csv({quote(paths['smoke_stats'])}) ORDER BY yr").df()
    fire_view = {
        "display_state": fire["display_state"],
        "confirmed_fire_register_available": fire["confirmed_fire_register_available"],
        "confirmed_fire_records_in_data": fire["confirmed_fire_count"],
        "real_fire_count": None,
        "telemetry_candidate_count": fire["telemetry_candidate_count"],
        "smoke_signal_statistics_are_fires": False,
        "smoke_signal_statistics": smoke.to_dict(orient="records"),
    }
    (output / "fire_history_view.json").write_text(
        json.dumps(fire_view,ensure_ascii=False,indent=2),encoding="utf-8")
    (output / "feedback_availability.json").write_text(json.dumps({
        "real_feedback_available": False,
        "decision_counts": None,
        "rejection_reasons": None,
        "meaning": "Журнал решений диспетчеров не передан; нули не подставляются."
    },ensure_ascii=False,indent=2),encoding="utf-8")
    result = con.execute("""
        SELECT (SELECT count(*) FROM object_day) object_days,
               (SELECT count(*) FROM object_type_day) active_object_type_days,
               (SELECT count(*) FROM situation_navigation) situations,
               (SELECT count(*) FROM gas_daily) gas_channel_days,
               (SELECT sum(draft_count) FROM object_day) drafts,
               (SELECT sum(observed_situations) FROM object_day) observed_situations
    """)
    print(json.dumps(dict(zip([d[0] for d in result.description],result.fetchone())),
                     ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
