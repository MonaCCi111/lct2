"""Подготовить группы черновиков и порядок разбора внутри каждой модели."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--catalog", type=Path,
                        default=Path(__file__).resolve().parents[2] / "dataset"
                        / "справочник_каналов_датчиков.csv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.drafts, args.catalog):
        if not path.exists():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW drafts AS SELECT * FROM read_parquet('{args.drafts.as_posix()}');
        CREATE VIEW locations AS
        SELECT "ид_канала_данных" channel_id,"ид_объект" object_id
        FROM read_csv('{args.catalog.as_posix()}',header=true);
    """)
    missing = con.execute("""
        SELECT count(*) FROM drafts d LEFT JOIN locations l USING(channel_id)
        WHERE l.object_id IS NULL
    """).fetchone()[0]
    if missing:
        raise ValueError(f"Нет объекта у {missing} черновиков")
    con.execute("""
        CREATE TABLE review_members AS
        WITH located AS (
            SELECT d.*,l.object_id,
                   row_number() OVER (
                       PARTITION BY d.model_version,cast(d.obs_time AS DATE)
                       ORDER BY d.score DESC,d.obs_time,d.channel_id,d.draft_id
                   ) rank_in_model_day
            FROM drafts d JOIN locations l USING(channel_id)
        ), ordered AS (
            SELECT *,lag(obs_time) OVER (
                PARTITION BY object_id ORDER BY obs_time,model_version,channel_id,draft_id
            ) previous_object_time
            FROM located
        ), numbered AS (
            SELECT *,sum(CASE WHEN previous_object_time IS NULL
                                   OR obs_time>previous_object_time+INTERVAL 1 HOUR
                              THEN 1 ELSE 0 END) OVER (
                PARTITION BY object_id ORDER BY obs_time,model_version,channel_id,draft_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) group_number
            FROM ordered
        ), identified AS (
            SELECT *,min(obs_time) OVER(PARTITION BY object_id,group_number) first_group_time
            FROM numbered
        )
        SELECT concat('review:',object_id::VARCHAR,':',
                      strftime(first_group_time,'%Y%m%dT%H%M%S')) group_id,
               draft_id,object_id,channel_id,obs_time,score,model_version,
               forecast_horizon_hours,target_kind,review_status,rank_in_model_day
        FROM identified;

        CREATE TABLE review_groups AS
        SELECT group_id,object_id,min(obs_time) first_obs_time,
               max(obs_time) last_obs_time,count(*) draft_count,
               count(DISTINCT channel_id) channel_count,
               count(*) FILTER(WHERE model_version='power_phase_scada_v2') phase_count,
               count(*) FILTER(WHERE model_version='pump_scada_v1') pump_count,
               max(score) FILTER(WHERE model_version='power_phase_scada_v2') max_phase_score,
               max(score) FILTER(WHERE model_version='pump_scada_v1') max_pump_score,
               'draft' review_status
        FROM review_members GROUP BY 1,2;
    """)
    for table in ("review_members", "review_groups"):
        path = args.output / f"{table}.parquet"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    result = con.execute("""
        WITH daily AS (
            SELECT cast(first_obs_time AS DATE) d,count(*) n
            FROM review_groups GROUP BY 1
        )
        SELECT (SELECT count(*) FROM review_members) drafts,
               (SELECT count(*) FROM review_groups) review_group_count,
               (SELECT count(*) FROM review_groups WHERE draft_count>1) multi_draft_groups,
               (SELECT max(draft_count) FROM review_groups) largest_group,
               (SELECT max(n) FROM daily) max_daily_groups,
               (SELECT count(*) FROM daily WHERE n>10) days_over_ten_groups
    """)
    print(json.dumps({"output": str(args.output), "columns": [d[0] for d in result.description],
                      "rows": result.fetchall()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
