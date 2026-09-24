"""Вывести нагрузку групп и совпадения с автоматическими эпизодами SCADA."""

import json
import sys
from pathlib import Path

import duckdb


def emit(con, name, query):
    result = con.execute(query)
    print(json.dumps({"scope": name, "columns": [d[0] for d in result.description],
                      "rows": result.fetchall()}, ensure_ascii=False, default=str), flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    phase = root / "power_phase_v2" / "labels.parquet"
    pump = root / "pump_v1" / "labels.parquet"
    con = duckdb.connect()
    for name in ("policy_2024", "diagnostic_2025_2026"):
        folder = root / "dispatch_review" / name
        con.execute(f"CREATE OR REPLACE VIEW members AS SELECT * FROM read_parquet('{(folder / 'review_members.parquet').as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW groups AS SELECT * FROM read_parquet('{(folder / 'review_groups.parquet').as_posix()}')")
        con.execute(f"""
            CREATE OR REPLACE VIEW labeled AS
            SELECT m.*,l.training_eligible,l.target_1_48h
            FROM members m LEFT JOIN read_parquet('{phase.as_posix()}') l
              USING(channel_id,obs_time)
            WHERE m.model_version='power_phase_scada_v2'
            UNION ALL
            SELECT m.*,l.training_eligible,l.target_1_48h
            FROM members m LEFT JOIN read_parquet('{pump.as_posix()}') l
              USING(channel_id,obs_time)
            WHERE m.model_version='pump_scada_v1';
        """)
        emit(con, name + "/workload", """
            WITH daily AS (
                SELECT cast(first_obs_time AS DATE) d,count(*) n
                FROM groups GROUP BY 1
            )
            SELECT (SELECT count(*) FROM members) drafts,
                   (SELECT count(*) FROM groups) review_groups,
                   (SELECT max(draft_count) FROM groups) largest_group,
                   (SELECT count(*) FROM groups WHERE draft_count>1) multi_draft_groups,
                   (SELECT quantile_cont(n,[0.5,0.9,0.95,0.99]) FROM daily)
                     active_day_group_quantiles,
                   (SELECT max(n) FROM daily) max_daily_groups
        """)
        emit(con, name + "/groups_by_size", """
            WITH g AS (
                SELECT group_id,count(*) draft_count,
                       count(*) FILTER(WHERE training_eligible) evaluable,
                       sum(coalesce(target_1_48h,0)) n_matched
                FROM labeled GROUP BY 1
            )
            SELECT CASE WHEN draft_count=1 THEN '1'
                        WHEN draft_count<=4 THEN '2-4' ELSE '5+' END size_class,
                   count(*) group_count,sum(draft_count) drafts,
                   count(*) FILTER(WHERE n_matched>0) groups_with_match,
                   sum(n_matched) matched_drafts
            FROM g GROUP BY 1 ORDER BY 1
        """)
        emit(con, name + "/score_rank", """
            SELECT model_version,
                   CASE WHEN rank_in_model_day=1 THEN '1'
                        WHEN rank_in_model_day<=3 THEN '2-3' ELSE '4+' END rank_class,
                   count(*) drafts,
                   count(*) FILTER(WHERE training_eligible) evaluable,
                   sum(coalesce(target_1_48h,0)) n_matched
            FROM labeled GROUP BY 1,2 ORDER BY 1,2
        """)


if __name__ == "__main__":
    main()
