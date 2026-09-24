"""Проверки temperature_scada_v1."""

import hashlib
import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.package_temperature import canonical_json
from production_ml.pipeline.temperature_model import MODEL_FEATURES


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "temperature_v1"
    bundle = root / "production_ml" / "models" / "temperature_scada_v1"
    con = duckdb.connect()
    con.execute("SET threads=4")
    for name in ("events", "episodes", "features", "labels"):
        path = (data / f"{name}.parquet").as_posix()
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")

    failures = []

    def emit(name, sql, invalid_fields=()):
        cursor = con.execute(sql)
        fields = [column[0] for column in cursor.description]
        rows = [dict(zip(fields, row)) for row in cursor.fetchall()]
        print(json.dumps(
            {"check": name, "rows": rows},
            ensure_ascii=False,
            default=str,
        ), flush=True)
        for row in rows:
            for field in invalid_fields:
                if row[field] != 0:
                    failures.append(f"{name}.{field}={row[field]}")

    emit("counts", """
        SELECT
          (SELECT count(*) FROM events) events,
          (SELECT count(*) FROM episodes) episodes,
          (SELECT count(*) FROM features) features,
          (SELECT count(*) FROM labels) labels
    """)
    emit("duplicate_keys", """
        SELECT
          (SELECT count(*) FROM (
             SELECT event_id,channel_id,event_time,is_alarm,sensor_value
             FROM events GROUP BY ALL HAVING count(*)>1
          )) event_duplicates,
          (SELECT count(*) FROM (
             SELECT channel_id,obs_time FROM features
             GROUP BY ALL HAVING count(*)>1
          )) feature_duplicates
    """, ("event_duplicates", "feature_duplicates"))
    emit("feature_availability", """
        WITH hourly AS (
          SELECT channel_id,date_trunc('hour',event_time)+INTERVAL 1 HOUR obs_time,
                 max(event_time) max_event,count(*) event_count
          FROM events GROUP BY 1,2
        )
        SELECT
          count(*) FILTER(WHERE max_event>=obs_time) future_event_violations,
          count(*) FILTER(WHERE event_count!=event_count_1h) count_mismatches
        FROM hourly JOIN features USING(channel_id,obs_time)
    """, ("future_event_violations", "count_mismatches"))
    emit("episode_order", """
        WITH ordered AS (
          SELECT *,lead(episode_start) OVER (
            PARTITION BY channel_id ORDER BY episode_start,start_event_id
          ) next_start
          FROM episodes
        )
        SELECT
          count(*) FILTER(WHERE recovery_time<=episode_start) bad_recovery,
          count(*) FILTER(WHERE next_start IS NOT NULL
                            AND (recovery_time>next_start OR recovery_time IS NULL)) overlap
        FROM ordered
    """, ("bad_recovery", "overlap"))
    emit("label_rules", """
        SELECT
          count(*) FILTER(WHERE NOT future_observed AND target_1_48h!=0) censored_with_target,
          count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows,
          min(target_lead_hours) FILTER(WHERE target_1_48h=1) min_lead,
          max(target_lead_hours) FILTER(WHERE target_1_48h=1) max_lead
        FROM labels
    """, ("censored_with_target",))
    emit("feature_values", """
        SELECT
          count(*) FILTER(WHERE numeric_fraction_24h NOT BETWEEN 0 AND 1) invalid_fraction,
          count(*) FILTER(WHERE observed_hours_72h NOT BETWEEN 1 AND 72) invalid_observed_hours,
          count(*) FILTER(WHERE numeric_min_24h>numeric_max_24h) invalid_range
        FROM features
    """, ("invalid_fraction", "invalid_observed_hours", "invalid_range"))
    emit("split_episode_overlap", """
        WITH split_targets AS (
          SELECT DISTINCT channel_id,target_episode_id,
            CASE
              WHEN year(obs_time) IN (2020,2022,2023)
                   AND obs_time<TIMESTAMP '2023-12-30' THEN 'train'
              WHEN obs_time>=TIMESTAMP '2024-01-03'
                   AND obs_time<TIMESTAMP '2024-06-29' THEN 'calibration'
              WHEN obs_time>=TIMESTAMP '2024-07-03'
                   AND obs_time<TIMESTAMP '2024-12-30' THEN 'policy'
              WHEN obs_time>=TIMESTAMP '2025-01-01' THEN 'diagnostic'
            END split_name
          FROM labels
          WHERE training_eligible AND target_1_48h=1
        )
        SELECT left_side.split_name left_split,right_side.split_name right_split,count(*) overlap
        FROM split_targets left_side
        JOIN split_targets right_side USING(channel_id,target_episode_id)
        WHERE left_side.split_name<right_side.split_name
        GROUP BY 1,2
    """)
    overlap_count = con.execute("""
        WITH split_targets AS (
          SELECT DISTINCT channel_id,target_episode_id,
            CASE
              WHEN year(obs_time) IN (2020,2022,2023)
                   AND obs_time<TIMESTAMP '2023-12-30' THEN 'train'
              WHEN obs_time>=TIMESTAMP '2024-01-03'
                   AND obs_time<TIMESTAMP '2024-06-29' THEN 'calibration'
              WHEN obs_time>=TIMESTAMP '2024-07-03'
                   AND obs_time<TIMESTAMP '2024-12-30' THEN 'policy'
              WHEN obs_time>=TIMESTAMP '2025-01-01' THEN 'diagnostic'
            END split_name
          FROM labels WHERE training_eligible AND target_1_48h=1
        )
        SELECT count(*) FROM split_targets a JOIN split_targets b
          USING(channel_id,target_episode_id)
        WHERE a.split_name<b.split_name
    """).fetchone()[0]
    if overlap_count:
        failures.append(f"split_episode_overlap={overlap_count}")
    parity = con.execute(f"""
        SELECT count(*) common,
               count(*) FILTER(WHERE abs(train.score-inference.score)>1e-12) differences,
               max(abs(train.score-inference.score)) max_difference
        FROM read_parquet('{(data / 'policy_2024_train_scores.parquet').as_posix()}') train
        JOIN read_parquet('{(data / 'policy_2024_scores.parquet').as_posix()}') inference
          USING(channel_id,obs_time)
    """).fetchone()
    print(json.dumps({
        "check": "train_inference_parity",
        "common": parity[0],
        "differences": parity[1],
        "max_difference": parity[2],
    }), flush=True)
    if parity[1] != 0:
        failures.append(f"train_inference_parity={parity[1]}")

    hashes = json.loads((bundle / "sha256.json").read_text(encoding="utf-8"))
    actual = {}
    for name, spec in hashes.items():
        if spec["mode"] == "bytes":
            content = (bundle / name).read_bytes()
        else:
            content = canonical_json(bundle / name)
        actual[name] = hashlib.sha256(content).hexdigest()
    contract = json.loads((bundle / "contract.json").read_text(encoding="utf-8"))
    meta = json.loads((bundle / "model_meta.json").read_text(encoding="utf-8"))
    policy = json.loads((bundle / "policy.json").read_text(encoding="utf-8"))
    bundle_check = {
        "check": "bundle",
        "hashes_match": all(
            actual[name] == spec["sha256"] for name, spec in hashes.items()
        ),
        "schema_match": (
            tuple(contract["model_inputs"])
            == MODEL_FEATURES
            == tuple(meta["model_features"])
        ),
        "version_match": len({
            contract["version"], meta["version"], policy["version"]
        }) == 1,
    }
    print(json.dumps(bundle_check), flush=True)
    if not all(bundle_check[key] for key in (
        "hashes_match", "schema_match", "version_match"
    )):
        failures.append("bundle")
    if failures:
        raise AssertionError("; ".join(failures))


if __name__ == "__main__":
    main()
