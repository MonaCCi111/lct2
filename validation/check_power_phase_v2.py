"""Фактические проверки исправленного пути power_phase_scada_v2."""

import hashlib
import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.model import MODEL_FEATURES
from production_ml.pipeline.package_power_phase_v2 import canonical_json


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root=Path(__file__).resolve().parents[1];data=root/"production_ml"/"data"/"power_phase_v2";bundle=root/"production_ml"/"models"/"power_phase_scada_v2"
    con=duckdb.connect();con.execute("SET threads=4")
    for name in ("phase_events","episodes","features","labels"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(data/(name+'.parquet')).as_posix()}')")
    def emit(name,sql):
        cur=con.execute(sql);fields=[x[0] for x in cur.description]
        print(json.dumps({"check":name,"rows":[dict(zip(fields,r)) for r in cur.fetchall()]},ensure_ascii=False,default=str),flush=True)
    emit("counts","SELECT (SELECT count(*) FROM phase_events) events,(SELECT count(*) FROM features) features,(SELECT count(*) FROM episodes) episodes,(SELECT count(*) FROM labels) labels")
    emit("duplicate_keys","SELECT (SELECT count(*) FROM (SELECT event_id,channel_id,event_time,is_alarm,sensor_value FROM phase_events GROUP BY ALL HAVING count(*)>1)) event_duplicates,(SELECT count(*) FROM (SELECT channel_id,obs_time FROM features GROUP BY ALL HAVING count(*)>1)) feature_duplicates")
    emit("feature_availability","WITH h AS (SELECT channel_id,date_trunc('hour',event_time)+INTERVAL 1 HOUR obs_time,max(event_time) max_event,count(*) n FROM phase_events GROUP BY 1,2) SELECT count(*) FILTER(WHERE max_event>obs_time) future_event_violations,count(*) FILTER(WHERE h.n!=f.event_count_1h) count_mismatches FROM h JOIN features f USING(channel_id,obs_time)")
    emit("cross_year_context","WITH o AS (SELECT *,lag(sensor_value) OVER(PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value,is_alarm) pv,lag(event_time) OVER(PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value,is_alarm) pt FROM phase_events) SELECT count(*) FILTER(WHERE year(event_time)!=year(pt)) boundary_pairs,count(*) FILTER(WHERE year(event_time)!=year(pt) AND sensor_value IS DISTINCT FROM pv) boundary_changes FROM o")
    emit("episode_order","WITH x AS (SELECT *,lead(episode_start) OVER(PARTITION BY channel_id ORDER BY episode_start,start_event_id) next_start,lead(start_event_id) OVER(PARTITION BY channel_id ORDER BY episode_start,start_event_id) next_id FROM episodes) SELECT count(*) FILTER(WHERE recovery_time<episode_start OR (recovery_time=episode_start AND recovery_event_id<=start_event_id)) bad_recovery,count(*) FILTER(WHERE next_start IS NOT NULL AND (recovery_time>next_start OR (recovery_time=next_start AND recovery_event_id>=next_id) OR recovery_time IS NULL)) overlap FROM x")
    emit("label_rules","SELECT count(*) FILTER(WHERE NOT future_observed AND target_1_48h!=0) censored_with_target,count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows,min(target_lead_hours) FILTER(WHERE target_1_48h=1) min_lead,max(target_lead_hours) FILTER(WHERE target_1_48h=1) max_lead FROM labels")
    emit("feature_values","SELECT count(*) FILTER(WHERE fast_change_fraction_24h NOT BETWEEN 0 AND 1 OR alarm_event_fraction_24h NOT BETWEEN 0 AND 1 OR undefined_event_fraction_24h NOT BETWEEN 0 AND 1) invalid_fraction,count(*) FILTER(WHERE observed_hours_72h NOT BETWEEN 1 AND 72) invalid_observed_hours FROM features")
    emit("split_episode_overlap","WITH a AS (SELECT DISTINCT channel_id,target_episode_id,CASE WHEN year(obs_time) IN (2020,2022,2023) AND obs_time<TIMESTAMP '2023-12-30' THEN 'train' WHEN obs_time>=TIMESTAMP '2024-01-03' AND obs_time<TIMESTAMP '2024-06-29' THEN 'calibration' WHEN obs_time>=TIMESTAMP '2024-07-03' AND obs_time<TIMESTAMP '2024-12-30' THEN 'policy' WHEN obs_time>=TIMESTAMP '2025-01-03' THEN 'diagnostic' END split FROM labels WHERE training_eligible AND target_1_48h=1) SELECT x.split left_split,y.split right_split,count(*) n FROM a x JOIN a y USING(channel_id,target_episode_id) WHERE x.split<y.split GROUP BY 1,2")
    emit("train_inference_parity",f"SELECT count(*) common,count(*) FILTER(WHERE abs(a.score-b.score)>1e-12) differences,max(abs(a.score-b.score)) max_difference,(SELECT count(*) FROM read_parquet('{(data/'policy_2024_scores.parquet').as_posix()}')) operational_rows FROM read_parquet('{(data/'policy_2024_train_scores.parquet').as_posix()}') a JOIN read_parquet('{(data/'policy_2024_scores.parquet').as_posix()}') b USING(channel_id,obs_time)")
    hashes=json.loads((bundle/"sha256.json").read_text(encoding="utf-8"));actual={}
    for name,spec in hashes.items():
        content=(bundle/name).read_bytes() if spec["mode"]=="bytes" else canonical_json(bundle/name)
        actual[name]=hashlib.sha256(content).hexdigest()
    contract=json.loads((bundle/"contract.json").read_text(encoding="utf-8"));meta=json.loads((bundle/"model_meta.json").read_text(encoding="utf-8"));policy=json.loads((bundle/"policy.json").read_text(encoding="utf-8"))
    print(json.dumps({"check":"bundle","hashes_match":all(actual[n]==s["sha256"] for n,s in hashes.items()),"schema_match":tuple(contract["model_inputs"])==MODEL_FEATURES==tuple(meta["model_features"]),"version_match":len({contract["version"],meta["version"],policy["version"]})==1,"canonical_json_hashes":True}),flush=True)


if __name__=="__main__":main()
