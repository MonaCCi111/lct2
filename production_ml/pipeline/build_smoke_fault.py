"""Собрать исследовательскую витрину неисправности дымовых датчиков."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from .smoke_fault_episodes import episode_sql
from .smoke_fault_features import FEATURES, feature_sql


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"data"/"smoke_fault_v1")
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.output.mkdir(parents=True,exist_ok=True)
    journals=[args.source_root/"production_ml"/"data"/"source_v2"/f"journal_{y}.parquet" for y in range(2019,2027)]
    channels=args.source_root/"dataset"/"справочник_каналов_датчиков.csv"
    for path in (*journals,channels):
        if not path.exists():
            raise FileNotFoundError(path)
    con=duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory='{(args.output/'duckdb_temp').as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(feature_sql(journals,channels))
    con.execute(episode_sql())
    con.execute("""
    CREATE TABLE smoke_fault_bounds AS
    SELECT channel_id,min(event_time) first_event_time,max(event_time) last_event_time
    FROM smoke_fault_clear_events GROUP BY 1;

    CREATE TABLE smoke_fault_labels AS
    WITH previous AS (
      SELECT f.*,p.episode_id previous_episode_id,p.episode_start previous_episode_start,
             p.recovery_time previous_recovery_time,b.first_event_time,b.last_event_time
      FROM smoke_fault_features f JOIN smoke_fault_bounds b USING(channel_id)
      ASOF LEFT JOIN smoke_fault_episodes p
        ON f.channel_id=p.channel_id AND f.obs_time>=p.episode_start
    ), state_at_obs AS (
      SELECT p.*,s.state latest_explicit_state
      FROM previous p
      ASOF LEFT JOIN smoke_fault_states s
        ON p.channel_id=s.channel_id AND p.obs_time>s.event_time
    ), next_episode AS (
      SELECT p.*,n.episode_id target_episode_id_raw,n.episode_start target_episode_start
      FROM state_at_obs p
      ASOF LEFT JOIN smoke_fault_episodes n
        ON p.channel_id=n.channel_id AND p.obs_time<n.episode_start
    ), eligibility AS (
      SELECT *,
             (first_event_time<=obs_time-INTERVAL 72 HOUR
              AND latest_explicit_state=0
              AND (previous_episode_id IS NULL OR previous_recovery_time<=obs_time-INTERVAL 48 HOUR)) operational_eligible,
             (last_event_time>=obs_time+INTERVAL 48 HOUR) future_observed
      FROM next_episode
    )
    SELECT channel_id,obs_time,coalesce(operational_eligible,false) operational_eligible,
           future_observed,(coalesce(operational_eligible,false) AND future_observed) training_eligible,
           latest_explicit_state,previous_episode_id,previous_recovery_time,
           CASE WHEN coalesce(operational_eligible,false) AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN 1 ELSE 0 END::TINYINT target_1_48h,
           CASE WHEN coalesce(operational_eligible,false) AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN target_episode_id_raw END target_episode_id,
           CASE WHEN coalesce(operational_eligible,false) AND future_observed
                     AND target_episode_start BETWEEN obs_time+INTERVAL 1 HOUR AND obs_time+INTERVAL 48 HOUR
                THEN epoch(target_episode_start-obs_time)/3600.0 END target_lead_hours
    FROM eligibility;
    """)
    for name,table in {
      "events":"smoke_fault_events", "clear_events":"smoke_fault_clear_events",
      "states":"smoke_fault_states", "episodes":"smoke_fault_episodes",
      "features":"smoke_fault_features", "labels":"smoke_fault_labels",
    }.items():
        path=args.output/f"{name}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
        n=con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(json.dumps({"artifact":name,"rows":n,"bytes":path.stat().st_size}),flush=True)
    result=con.execute("""
      SELECT year(obs_time) yr,count(*) feature_rows,
             count(*) FILTER(WHERE training_eligible) eligible_rows,
             count(*) FILTER(WHERE training_eligible AND target_1_48h=1) positive_rows,
             count(DISTINCT concat(channel_id,':',target_episode_id))
               FILTER(WHERE training_eligible AND target_1_48h=1) target_episodes,
             count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows
      FROM smoke_fault_labels GROUP BY 1 ORDER BY 1
    """)
    print(json.dumps({"features":FEATURES,"label_facts":result.fetchall()},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
