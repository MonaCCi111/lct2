"""Проверить границы времени, эпизоды и состав пакета POWER_PHASE."""

import hashlib
import json
import os
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.model import MODEL_FEATURES


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "power_phase_v1"
    bundle = root / "production_ml" / "models" / "power_phase_scada_v1"
    source = Path(os.environ.get("LCT2_SOURCE_ROOT", root))
    con = duckdb.connect()
    con.execute("SET threads=4")
    for name in ("features", "labels", "episodes", "failure_events"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(data / (name + '.parquet')).as_posix()}')")

    def emit(check, sql):
        cursor = con.execute(sql)
        fields = [item[0] for item in cursor.description]
        print(json.dumps({"check": check, "rows": [dict(zip(fields, row)) for row in cursor.fetchall()]},
                         ensure_ascii=False, default=str), flush=True)

    emit("feature_counts", "SELECT year(obs_time) yr,count(*) n,count(DISTINCT channel_id) channels FROM features GROUP BY 1 ORDER BY 1")
    emit("duplicate_feature_keys", "SELECT count(*) n FROM (SELECT channel_id,obs_time FROM features GROUP BY 1,2 HAVING count(*)>1)")
    emit("duplicate_label_keys", "SELECT count(*) n FROM (SELECT channel_id,obs_time FROM labels GROUP BY 1,2 HAVING count(*)>1)")
    emit("eligibility", "SELECT count(*) n,count(*) FILTER(WHERE eligible) eligible_rows,sum(target_1_48h) positives,sum(target_1_48h) FILTER(WHERE eligible) eligible_positives FROM labels")
    emit("eligibility_violations", "SELECT count(*) n FROM labels WHERE eligible AND last_failure_time >= obs_time-INTERVAL 48 HOUR")
    emit("lead_bounds", "SELECT min(target_lead_hours) min_hours,max(target_lead_hours) max_hours,count(*) n FROM labels WHERE target_1_48h=1")
    emit("invalid_feature_values", "SELECT count(*) FILTER(WHERE fast_change_fraction_24h<0 OR fast_change_fraction_24h>1) fast_fraction, count(*) FILTER(WHERE alarm_event_fraction_24h<0 OR alarm_event_fraction_24h>1) alarm_fraction, count(*) FILTER(WHERE undefined_event_fraction_24h<0 OR undefined_event_fraction_24h>1) undefined_fraction, count(*) FILTER(WHERE observed_hours_72h<1 OR observed_hours_72h>72) observed_hours FROM features")
    emit("null_features", "SELECT " + ",".join(f'count(*) FILTER(WHERE "{name}" IS NULL) AS "{name}"' for name in MODEL_FEATURES) + " FROM features")
    emit("failure_reasons", "SELECT fail_reason,count(*) n FROM failure_events GROUP BY 1 ORDER BY 2 DESC")
    emit("episode_reasons", "SELECT first_reason,count(*) n FROM episodes GROUP BY 1 ORDER BY 2 DESC")
    emit("episode_first_status", "SELECT first_status,count(*) n FROM episodes GROUP BY 1 ORDER BY 2 DESC")
    emit("episodes_by_sensor", "SELECT sensor_type,first_status,count(*) n FROM episodes GROUP BY 1,2 ORDER BY 1,2")
    emit("split_episode_overlap", """
        WITH assigned AS (
            SELECT DISTINCT channel_id,target_episode_id,
                   CASE WHEN year(obs_time) IN (2020,2022,2023) AND obs_time<TIMESTAMP '2023-12-30' THEN 'train'
                        WHEN obs_time>=TIMESTAMP '2024-01-03' AND obs_time<TIMESTAMP '2024-06-29' THEN 'calibration'
                        WHEN obs_time>=TIMESTAMP '2024-07-03' AND obs_time<TIMESTAMP '2024-12-30' THEN 'threshold'
                        WHEN obs_time>=TIMESTAMP '2025-01-03' THEN 'diagnostic' END AS split
            FROM labels WHERE eligible AND target_1_48h=1
        )
        SELECT a.split left_split,b.split right_split,count(*) n
        FROM assigned a JOIN assigned b USING(channel_id,target_episode_id)
        WHERE a.split<b.split GROUP BY 1,2 ORDER BY 1,2
    """)
    old = source / "production_ml" / "data" / "cache_v6" / "persistent_failure_episodes.parquet"
    if old.exists():
        emit("old_episode_comparison", f"""
            WITH old AS (SELECT channel_id,t_fail_start FROM read_parquet('{old.as_posix()}')
                         WHERE sensor_type IN ('Состояние фазы','ИБП','Переключатель'))
            SELECT (SELECT count(*) FROM old) old_count,
                   (SELECT count(*) FROM episodes) new_count,
                   (SELECT count(*) FROM old o JOIN episodes e
                    ON o.channel_id=e.channel_id AND o.t_fail_start=e.episode_start) matching_starts
        """)
    parity = con.execute(f"""
        SELECT count(*) n,count(*) FILTER(WHERE a.channel_id IS NULL OR b.channel_id IS NULL) unmatched,
               max(abs(a.score-b.score)) max_score_difference
        FROM read_parquet('{(data / 'threshold_2024_scores.parquet').as_posix()}') a
        FULL JOIN read_parquet('{(data / 'threshold_2024_bundle_check.parquet').as_posix()}') b
        USING(channel_id,obs_time)
    """).fetchone()
    print(json.dumps({"check": "train_inference_parity", "rows": parity}), flush=True)
    hashes = json.loads((bundle / "sha256.json").read_text(encoding="utf-8"))
    actual = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in hashes}
    contract = json.loads((bundle / "contract.json").read_text(encoding="utf-8"))
    policy = json.loads((bundle / "policy.json").read_text(encoding="utf-8"))
    meta = json.loads((bundle / "model_meta.json").read_text(encoding="utf-8"))
    print(json.dumps({"check": "bundle", "hashes_match": hashes == actual,
                      "feature_contract_match": tuple(contract["model_inputs"]) == MODEL_FEATURES == tuple(meta["model_features"]),
                      "version_match": len({contract["version"], policy["version"], meta["version"]}) == 1}), flush=True)


if __name__ == "__main__":
    main()
