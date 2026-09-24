"""Проверить очередь черновиков активных моделей."""

import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.create_review_queue import OUTPUT_COLUMNS


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root=Path(__file__).resolve().parents[1]
    data=root/"production_ml"/"data"/"review_queue"
    phase=(root/"production_ml"/"data"/"power_phase_v2"/"labels.parquet").as_posix()
    pump=(root/"production_ml"/"data"/"pump_v1"/"labels.parquet").as_posix()
    con=duckdb.connect()
    path=(data/"policy_2024.parquet").as_posix()
    empty=(data/"empty.parquet").as_posix()
    con.execute(f"CREATE VIEW drafts AS SELECT * FROM read_parquet('{path}')")
    result=con.execute("""
        WITH ordered AS (
          SELECT *,lag(obs_time) OVER(PARTITION BY model_version,channel_id ORDER BY obs_time) previous_time
          FROM drafts
        ), daily AS (
          SELECT date_trunc('day',obs_time) d,count(*) n FROM drafts GROUP BY 1
        )
        SELECT (SELECT count(*) FROM drafts) drafts,
               (SELECT count(*) FROM (SELECT draft_id FROM drafts GROUP BY 1 HAVING count(*)>1)) duplicate_ids,
               (SELECT count(*) FROM ordered WHERE previous_time IS NOT NULL
                AND obs_time<previous_time+INTERVAL 48 HOUR) cooldown_violations,
               (SELECT count(*) FROM drafts WHERE review_status!='draft') wrong_status,
               (SELECT max(n) FROM daily) max_daily
    """)
    fields=[d[0] for d in result.description]
    facts=dict(zip(fields,result.fetchone()))
    print(json.dumps({"check":"structure",**facts},ensure_ascii=False),flush=True)
    result=con.execute(f"""
        WITH x AS (
          SELECT d.model_version,d.channel_id,d.obs_time,l.target_1_48h,l.target_episode_id
          FROM drafts d JOIN read_parquet('{phase}') l USING(channel_id,obs_time)
          WHERE d.model_version='power_phase_scada_v2'
          UNION ALL
          SELECT d.model_version,d.channel_id,d.obs_time,l.target_1_48h,l.target_episode_id
          FROM drafts d JOIN read_parquet('{pump}') l USING(channel_id,obs_time)
          WHERE d.model_version='pump_scada_v1'
        )
        SELECT count(*) evaluated_drafts,sum(target_1_48h) matched_drafts,
               count(DISTINCT concat(model_version,':',channel_id,':',target_episode_id))
                 FILTER(WHERE target_1_48h=1) covered_episodes
        FROM x
    """)
    fields=[d[0] for d in result.description]
    matches=dict(zip(fields,result.fetchone()))
    print(json.dumps({"check":"retrospective_policy",**matches},ensure_ascii=False),flush=True)
    schema=[r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{empty}')").fetchall()]
    empty_count=con.execute(f"SELECT count(*) FROM read_parquet('{empty}')").fetchone()[0]
    print(json.dumps({"check":"empty","rows":empty_count,"columns":schema},ensure_ascii=False),flush=True)
    if facts["duplicate_ids"] or facts["cooldown_violations"] or facts["wrong_status"]:
        raise AssertionError(facts)
    if schema!=list(OUTPUT_COLUMNS) or empty_count!=0:
        raise AssertionError("Пустая очередь имеет неверную схему")


if __name__=="__main__":
    main()
