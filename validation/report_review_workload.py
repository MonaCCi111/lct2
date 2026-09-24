"""Вывести сырые показатели нагрузки и совпадений для очереди черновиков."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    con = duckdb.connect()
    labels = {
        "power_phase_scada_v2": root / "power_phase_v2" / "labels.parquet",
        "pump_scada_v1": root / "pump_v1" / "labels.parquet",
    }
    queues = {
        "policy_uncapped": root / "review_queue" / "policy_2024.parquet",
        "diagnostic_uncapped": root / "review_queue" / "diagnostic_2025_2026.parquet",
        "diagnostic_capped": root / "review_queue" / "diagnostic_2025_2026_legacy_cap.parquet",
    }
    for name, path in queues.items():
        con.execute(f"CREATE OR REPLACE VIEW q AS SELECT * FROM read_parquet('{path.as_posix()}')")
        result = con.execute("""
            WITH daily AS (
                SELECT cast(obs_time AS DATE) d,count(*) n FROM q GROUP BY 1
            )
            SELECT count(*) drafts,count(DISTINCT cast(obs_time AS DATE)) active_days,
                   (SELECT quantile_cont(n,[0.5,0.9,0.95,0.99]) FROM daily) daily_quantiles,
                   (SELECT max(n) FROM daily) max_daily,
                   (SELECT count(*) FROM daily WHERE n>10) days_over_ten
            FROM q
        """)
        facts = dict(zip([d[0] for d in result.description], result.fetchone()))
        print(json.dumps({"period": name, "scope": "workload", **facts}, ensure_ascii=False), flush=True)
        for model, label_path in labels.items():
            result = con.execute(f"""
                SELECT count(*) drafts,
                       count(*) FILTER(WHERE l.training_eligible) evaluable,
                       count(*) FILTER(WHERE l.target_1_48h=1) matched_drafts,
                       count(DISTINCT concat(q.channel_id,':',l.target_episode_id))
                         FILTER(WHERE l.target_1_48h=1) matched_episodes
                FROM q LEFT JOIN read_parquet('{label_path.as_posix()}') l
                  USING(channel_id,obs_time)
                WHERE q.model_version=?
            """, [model])
            facts = dict(zip([d[0] for d in result.description], result.fetchone()))
            print(json.dumps({"period": name, "scope": model, **facts}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
