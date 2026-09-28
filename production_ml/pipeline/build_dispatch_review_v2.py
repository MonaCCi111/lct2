"""Собрать проверяемую очередь из активных прогнозов и наблюдаемых статусов."""

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd


OBSERVED_KINDS = (
    "OBSERVED_PUMP_FLOODED_STATUS",
    "OBSERVED_UPS_BATTERY_LOW_STATUS",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictive", type=Path, required=True)
    parser.add_argument("--observed", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_каналов_датчиков.csv")
    parser.add_argument("--phase-features", type=Path, required=True)
    parser.add_argument("--pump-features", type=Path, required=True)
    parser.add_argument("--journals", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.predictive, args.observed, args.evidence, args.catalog,
                 args.phase_features, args.pump_features):
        if not path.exists():
            raise FileNotFoundError(path)
    years = range(int(args.start[:4]), int(args.end[:4]) + 1)
    journals = [args.journals / f"journal_{year}.parquet" for year in years]
    for path in journals:
        if not path.exists():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='6GB'")
    con.execute(f"SET temp_directory='{(args.output / 'duckdb_temp').as_posix()}'")
    paths = {
        "predictive": args.predictive, "observed": args.observed,
        "evidence": args.evidence, "phase_features": args.phase_features,
        "pump_features": args.pump_features,
    }
    for name, path in paths.items():
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv('{args.catalog.as_posix()}')")
    invalid = con.execute(f"""
        SELECT count(*) FROM predictive
        WHERE model_version NOT IN ('power_phase_scada_v2','pump_scada_v1')
           OR review_status!='draft' OR obs_time<'{args.start}'
           OR obs_time>='{args.end}' OR draft_id IS NULL
    """).fetchone()[0]
    duplicate = con.execute("""
        SELECT count(*)-count(DISTINCT draft_id) FROM predictive
    """).fetchone()[0]
    if invalid or duplicate:
        raise ValueError(f"Неверная исходная очередь: invalid={invalid}, duplicate={duplicate}")
    journal_list = ",".join(f"'{path.as_posix()}'" for path in journals)
    con.execute(f"CREATE VIEW journal AS SELECT * FROM read_parquet([{journal_list}])")
    selected = ",".join(f"'{kind}'" for kind in OBSERVED_KINDS)
    candidates = con.execute(f"""
        SELECT s.situation_id,s.situation_kind,s.object_id,s.first_seen,
               (SELECT min(e.channel_id) FROM evidence e
                WHERE e.situation_id=s.situation_id AND e.event_time=s.first_seen)
                channel_id
        FROM observed s
        WHERE s.situation_kind IN ({selected}) AND NOT s.multi_channel_campaign
          AND s.first_seen>='{args.start}' AND s.first_seen<'{args.end}'
        ORDER BY s.first_seen,s.situation_id
    """).fetchall()
    last = {}
    mappings = []
    for situation_id, kind, object_id, first_seen, channel_id in candidates:
        key = (kind, object_id, channel_id)
        prior = last.get(key)
        if prior and (first_seen - prior[0]).total_seconds() < 48 * 3600:
            mapped_to = prior[1]
            selected_draft = False
        else:
            mapped_to = situation_id
            selected_draft = True
            last[key] = (first_seen, situation_id)
        mappings.append((situation_id, mapped_to, selected_draft, channel_id))
    mapping_frame = pd.DataFrame(mappings, columns=(
        "source_situation_id", "draft_situation_id", "selected_draft", "primary_channel_id"))
    if mapping_frame.empty:
        mapping_frame = pd.DataFrame({
            "source_situation_id": pd.Series(dtype="string"),
            "draft_situation_id": pd.Series(dtype="string"),
            "selected_draft": pd.Series(dtype="bool"),
            "primary_channel_id": pd.Series(dtype="int64"),
        })
    con.register("mapping_input", mapping_frame)
    con.execute("CREATE TABLE observed_mapping AS SELECT * FROM mapping_input")
    con.execute(f"""
        CREATE TABLE drafts AS
        WITH forecast AS (
            SELECT p.draft_id,'forecast' basis_kind,p.channel_id,l."ид_объект" object_id,
                   p.obs_time,p.obs_time first_signal_time,p.score,p.model_version,
                   p.forecast_horizon_hours,p.target_kind,p.review_status,
                   CAST(NULL AS VARCHAR) situation_id,CAST(NULL AS VARCHAR) location_key,
                   'model_score_is_not_physical_failure_probability;event_time_only;delivery_time_unavailable' limitations,
                   CAST(NULL AS BIGINT) affected_channels
            FROM predictive p LEFT JOIN catalog l ON p.channel_id=l."ид_канала_данных"
        ), direct_status AS (
            SELECT concat('observed:',s.situation_id) draft_id,
                   'observed_status' basis_kind,
                   map.primary_channel_id channel_id,
                   s.object_id,s.first_seen obs_time,s.first_seen first_signal_time,
                   CAST(NULL AS DOUBLE) score,CAST(NULL AS VARCHAR) model_version,
                   CAST(NULL AS BIGINT) forecast_horizon_hours,
                   s.situation_kind target_kind,'draft' review_status,
                   s.situation_id,s.location_key,s.limitations,s.affected_channels
            FROM observed s JOIN observed_mapping map
                 ON s.situation_id=map.source_situation_id
            WHERE map.selected_draft
        )
        SELECT * FROM forecast UNION ALL SELECT * FROM direct_status;

        CREATE TABLE members AS
        WITH ordered AS (
            SELECT *,lag(obs_time) OVER (
                PARTITION BY object_id ORDER BY obs_time,draft_id) previous_time
            FROM drafts
        ), numbered AS (
            SELECT *,sum(CASE WHEN previous_time IS NULL OR
                    obs_time>previous_time+INTERVAL 1 HOUR THEN 1 ELSE 0 END)
                    OVER (PARTITION BY object_id ORDER BY obs_time,draft_id
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) group_number
            FROM ordered
        ), identified AS (
            SELECT *,min(obs_time) OVER (PARTITION BY object_id,group_number)
                     first_group_time
            FROM numbered
        )
        SELECT concat('review_v2:',object_id::VARCHAR,':',
                      strftime(first_group_time,'%Y%m%dT%H%M%S')) group_id,
               * EXCLUDE(previous_time,group_number,first_group_time)
        FROM identified;

        CREATE TABLE groups AS
        SELECT group_id,object_id,min(obs_time) first_obs_time,max(obs_time) last_obs_time,
               count(*) draft_count,count(*) FILTER (WHERE basis_kind='forecast') forecast_count,
               count(*) FILTER (WHERE basis_kind='observed_status') observed_count,
               count(DISTINCT channel_id) primary_channel_count,
               count(DISTINCT location_key) known_location_count,
               'draft' review_status
        FROM members GROUP BY 1,2;

        CREATE TABLE observed_evidence AS
        SELECT m.draft_id,m.group_id,e.situation_id source_situation_id,
               e.evidence_kind,e.channel_id,e.event_time,
               e.event_time available_at,e.event_id,e.observed_value,e.numeric_value,
               e.channel_name,e.piket,
               CASE WHEN e.event_id IS NOT NULL THEN
                 concat('source_v2/journal_',year(e.event_time)::VARCHAR,
                        '.parquet:channel_id+event_time+event_id+sensor_value+is_alarm')
               ELSE e.source_ref END source_ref,
               e.event_time<=m.obs_time initial_at_draft
        FROM members m JOIN observed_mapping map
          ON m.situation_id=map.draft_situation_id
        JOIN evidence e ON e.situation_id=map.source_situation_id
        WHERE m.basis_kind='observed_status';

        CREATE TABLE forecast_features AS
        SELECT m.draft_id,m.model_version,to_json(f) feature_snapshot
        FROM members m JOIN phase_features f USING(channel_id,obs_time)
        WHERE m.model_version='power_phase_scada_v2'
        UNION ALL
        SELECT m.draft_id,m.model_version,to_json(f) feature_snapshot
        FROM members m JOIN pump_features f USING(channel_id,obs_time)
        WHERE m.model_version='pump_scada_v1';

        CREATE TABLE forecast_evidence AS
        SELECT m.draft_id,m.group_id,j.channel_id,j.event_time,
               j.event_time available_at,j.event_id,j.sensor_value observed_value,
               j.is_alarm,
               concat('source_v2/journal_',year(j.event_time)::VARCHAR,
                      '.parquet:channel_id+event_time+event_id+sensor_value+is_alarm') source_ref
        FROM members m JOIN journal j ON m.channel_id=j.channel_id
            AND j.event_time BETWEEN m.obs_time-INTERVAL 1 HOUR AND m.obs_time
        WHERE m.basis_kind='forecast';
    """)
    for table in ("members", "groups", "observed_mapping", "observed_evidence", "forecast_features",
                  "forecast_evidence"):
        path = args.output / f"{table}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    facts = con.execute("""
        SELECT (SELECT count(*) FROM members) drafts,
               (SELECT count(*) FROM members WHERE basis_kind='forecast') forecasts,
               (SELECT count(*) FROM members WHERE basis_kind='observed_status') observed,
               (SELECT count(*) FROM observed_mapping WHERE NOT selected_draft) observed_updates,
               (SELECT count(*) FROM groups) group_count,
               (SELECT count(*) FROM observed_evidence) observed_evidence,
               (SELECT count(*) FROM forecast_features) feature_snapshots,
               (SELECT count(*) FROM forecast_evidence) forecast_raw_events
    """)
    print(json.dumps(dict(zip([d[0] for d in facts.description], facts.fetchone())),
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
