"""Проверить, что группировка и ранги не теряют черновики."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    periods = (
        ("policy_2024", root / "review_queue" / "policy_2024.parquet"),
        ("diagnostic_2025_2026", root / "review_queue" / "diagnostic_2025_2026.parquet"),
        ("empty", root / "review_queue" / "empty.parquet"),
    )
    con = duckdb.connect()
    for name, source in periods:
        folder = root / "dispatch_review" / name
        con.execute(f"CREATE OR REPLACE VIEW source AS SELECT * FROM read_parquet('{source.as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW members AS SELECT * FROM read_parquet('{(folder / 'review_members.parquet').as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW groups AS SELECT * FROM read_parquet('{(folder / 'review_groups.parquet').as_posix()}')")
        result = con.execute("""
            WITH ranked AS (
                SELECT *,row_number() OVER (
                    PARTITION BY model_version,cast(obs_time AS DATE)
                    ORDER BY score DESC,obs_time,channel_id,draft_id
                ) expected_rank
                FROM members
            ), ordered AS (
                SELECT *,lag(obs_time) OVER(
                    PARTITION BY group_id ORDER BY obs_time,model_version,channel_id,draft_id
                ) previous_time
                FROM members
            )
            SELECT (SELECT count(*) FROM source) source_drafts,
                   (SELECT count(*) FROM members) members,
                   (SELECT count(*) FROM groups) groups_count,
                   (SELECT sum(draft_count) FROM groups) grouped_drafts,
                   (SELECT count(*) FROM members m LEFT JOIN source s USING(draft_id)
                      WHERE s.draft_id IS NULL) missing_sources,
                   (SELECT count(*) FROM source s LEFT JOIN members m USING(draft_id)
                      WHERE m.draft_id IS NULL) lost_drafts,
                   (SELECT count(*) FROM members)-(SELECT count(DISTINCT draft_id) FROM members)
                      duplicate_drafts,
                   (SELECT count(*) FROM groups)-(SELECT count(DISTINCT group_id) FROM groups)
                      duplicate_groups,
                   (SELECT count(*) FROM ranked WHERE rank_in_model_day!=expected_rank) wrong_rank,
                   (SELECT count(*) FROM ordered WHERE previous_time IS NOT NULL
                      AND obs_time>previous_time+INTERVAL 1 HOUR) broken_group_gap,
                   (SELECT count(*) FROM members m JOIN groups g USING(group_id)
                      WHERE m.object_id!=g.object_id OR m.obs_time<g.first_obs_time
                        OR m.obs_time>g.last_obs_time) wrong_membership,
                   (SELECT count(*) FROM members WHERE review_status!='draft') wrong_member_status,
                   (SELECT count(*) FROM groups WHERE review_status!='draft') wrong_group_status
        """)
        facts = dict(zip([d[0] for d in result.description], result.fetchone()))
        print(json.dumps({"period": name, **facts}, ensure_ascii=False), flush=True)
        if facts["source_drafts"] != facts["members"] or (
                facts["grouped_drafts"] or 0) != facts["members"] or any(
                facts[key] for key in ("missing_sources", "lost_drafts", "duplicate_drafts",
                                       "duplicate_groups", "wrong_rank", "broken_group_gap",
                                       "wrong_membership", "wrong_member_status", "wrong_group_status")):
            raise AssertionError(facts)


if __name__ == "__main__":
    main()
