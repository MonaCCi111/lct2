"""Структурные проверки исследовательской ветки fan_scada_v1."""

import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.fan_model import MODEL_FEATURES
from production_ml.pipeline.package_fan import verify_bundle


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "fan_v1"
    bundle = root / "production_ml" / "models" / "fan_scada_v1"
    verify_bundle(bundle)
    contract = json.loads((bundle / "contract.json").read_text(encoding="utf-8"))
    meta = json.loads((bundle / "model_meta.json").read_text(encoding="utf-8"))
    policy = json.loads((bundle / "policy.json").read_text(encoding="utf-8"))
    assert tuple(contract["model_inputs"]) == MODEL_FEATURES == tuple(meta["model_features"])
    assert len({contract["version"],meta["version"],policy["version"]}) == 1
    con = duckdb.connect()
    for name in ("events", "clear_events", "episodes", "features", "labels"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(data / (name + '.parquet')).as_posix()}')")

    checks = {
        "time_conflicts": """
            WITH t AS (SELECT channel_id,event_time,bool_and(is_alarm) a,bool_or(is_alarm) b
                       FROM events GROUP BY 1,2)
            SELECT count(*) FILTER(WHERE a!=b) conflicting_times,
                   (SELECT count(*) FROM events)-(SELECT count(*) FROM clear_events) removed_events
            FROM t
        """,
        "duplicate_keys": """
            SELECT (SELECT count(*) FROM (SELECT channel_id,obs_time FROM features GROUP BY 1,2 HAVING count(*)>1)) feature_duplicates,
                   (SELECT count(*) FROM (SELECT channel_id,obs_time FROM labels GROUP BY 1,2 HAVING count(*)>1)) label_duplicates
        """,
        "feature_availability": """
            WITH h AS (
              SELECT channel_id,date_trunc('hour',event_time)+INTERVAL 1 HOUR obs_time,
                     max(event_time) max_event,count(*) n
              FROM clear_events GROUP BY 1,2
            )
            SELECT count(*) FILTER(WHERE h.max_event>=h.obs_time) future_events,
                   count(*) FILTER(WHERE h.n!=f.event_count_1h) count_mismatches,
                   count(*) FILTER(WHERE f.observed_hours_72h NOT BETWEEN 1 AND 72) bad_observed_hours,
                   count(*) FILTER(WHERE f.on_fraction_24h NOT BETWEEN 0 AND 1
                     OR f.off_fraction_24h NOT BETWEEN 0 AND 1
                     OR f.undefined_fraction_24h NOT BETWEEN 0 AND 1) bad_fractions
            FROM h JOIN features f USING(channel_id,obs_time)
        """,
        "episode_order": """
            WITH x AS (
              SELECT *,lead(episode_start) OVER(PARTITION BY channel_id ORDER BY episode_start) next_start
              FROM episodes
            )
            SELECT count(*) FILTER(WHERE recovery_time<=episode_start) bad_recovery,
                   count(*) FILTER(WHERE next_start IS NOT NULL
                     AND (recovery_time>next_start OR recovery_time IS NULL)) overlapping
            FROM x
        """,
        "label_rules": """
            SELECT count(*) FILTER(WHERE NOT future_observed AND target_1_48h!=0) censored_with_target,
                   count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows,
                   min(target_lead_hours) FILTER(WHERE target_1_48h=1) min_lead,
                   max(target_lead_hours) FILTER(WHERE target_1_48h=1) max_lead
            FROM labels
        """,
        "score_parity": f"""
            SELECT count(*) common,
                   count(*) FILTER(WHERE abs(t.score-i.score)>1e-12) differences,
                   max(abs(t.score-i.score)) max_difference
            FROM read_parquet('{(data / 'policy_2024_train_scores.parquet').as_posix()}') t
            JOIN read_parquet('{(data / 'policy_2024_scores.parquet').as_posix()}') i
              USING(channel_id,obs_time)
        """,
        "score_eligibility": f"""
            WITH s AS (
              SELECT channel_id,obs_time FROM read_parquet('{(data / 'diagnostic_scores.parquet').as_posix()}')
            ), l AS (
              SELECT channel_id,obs_time,operational_eligible FROM labels
              WHERE obs_time>=TIMESTAMP '2025-01-01' AND obs_time<TIMESTAMP '2026-07-01'
            )
            SELECT (SELECT count(*) FROM s LEFT JOIN l USING(channel_id,obs_time)
                    WHERE l.channel_id IS NULL OR NOT l.operational_eligible) ineligible_scores,
                   (SELECT count(*) FROM l LEFT JOIN s USING(channel_id,obs_time)
                    WHERE l.operational_eligible AND s.channel_id IS NULL) missing_scores
        """,
        "empty_input": f"""
            SELECT count(*) n_rows FROM read_parquet('{(data / 'empty_scores.parquet').as_posix()}')
        """,
    }
    failures = []
    zero_fields = {
        "duplicate_keys": ("feature_duplicates","label_duplicates"),
        "feature_availability": ("future_events","count_mismatches","bad_observed_hours","bad_fractions"),
        "episode_order": ("bad_recovery","overlapping"),
        "label_rules": ("censored_with_target",),
        "score_parity": ("differences",),
        "score_eligibility": ("ineligible_scores","missing_scores"),
        "empty_input": ("n_rows",),
    }
    for name,sql in checks.items():
        result = con.execute(sql)
        fields = [d[0] for d in result.description]
        rows = [dict(zip(fields,r)) for r in result.fetchall()]
        print(json.dumps({"check": name,"rows": rows},ensure_ascii=False,default=str),flush=True)
        for row in rows:
            for field in zero_fields.get(name,()):
                if row[field] != 0:
                    failures.append(f"{name}.{field}={row[field]}")
    overlap = con.execute("""
        WITH x AS (
          SELECT DISTINCT channel_id,target_episode_id,
            CASE
              WHEN year(obs_time) IN (2020,2022) OR (year(obs_time)=2023 AND obs_time<TIMESTAMP '2023-12-30') THEN 'train'
              WHEN obs_time>=TIMESTAMP '2024-01-03' AND obs_time<TIMESTAMP '2024-06-29' THEN 'calibration'
              WHEN obs_time>=TIMESTAMP '2024-07-03' AND obs_time<TIMESTAMP '2024-12-30' THEN 'policy'
              WHEN obs_time>=TIMESTAMP '2025-01-01' THEN 'diagnostic'
            END split
          FROM labels WHERE training_eligible AND target_1_48h=1
        )
        SELECT a.split,b.split,count(*) n FROM x a JOIN x b USING(channel_id,target_episode_id)
        WHERE a.split<b.split GROUP BY 1,2
    """).fetchall()
    print(json.dumps({"check":"split_overlap","rows":overlap}),flush=True)
    if overlap:
        failures.append("split_overlap")
    empty_columns = [row[0] for row in con.execute(f"""
        DESCRIBE SELECT * FROM read_parquet('{(data / 'empty_scores.parquet').as_posix()}')
    """).fetchall()]
    print(json.dumps({"check":"empty_schema","columns":empty_columns}),flush=True)
    if empty_columns != contract["output"]:
        failures.append("empty_schema")
    if failures:
        raise AssertionError("; ".join(failures))


if __name__ == "__main__":
    main()
