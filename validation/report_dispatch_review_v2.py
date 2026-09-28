"""Измерить нагрузку очереди по календарным дням и двенадцатичасовым сменам."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    con = duckdb.connect()
    for period in ("policy_2024", "diagnostic_2025_2026"):
        folder = root / "dispatch_review_v2" / period
        con.execute(f"CREATE OR REPLACE VIEW members AS SELECT * FROM "
                    f"read_parquet('{(folder / 'members.parquet').as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW groups AS SELECT * FROM "
                    f"read_parquet('{(folder / 'groups.parquet').as_posix()}')")
        daily = con.execute("""
            WITH days AS (
                SELECT d::DATE date FROM generate_series(
                    (SELECT min(obs_time)::DATE FROM members),
                    (SELECT max(obs_time)::DATE FROM members),INTERVAL 1 DAY) x(d)
            ), counts AS (
                SELECT first_obs_time::DATE date,count(*) group_count,
                       sum(draft_count) drafts
                FROM groups GROUP BY 1
            )
            SELECT count(*) day_count,quantile_cont(coalesce(group_count,0),[.5,.9,.95,.99])
                   group_quantiles,max(coalesce(group_count,0)) max_groups,
                   max(coalesce(drafts,0)) max_drafts
            FROM days LEFT JOIN counts USING(date)
        """).fetchone()
        shifts = con.execute("""
            WITH bounds AS (
                SELECT date_trunc('day',min(obs_time)) first_day,
                       date_trunc('day',max(obs_time)) last_day FROM members
            ), slots AS (
                SELECT start_time FROM bounds,
                     generate_series(first_day,last_day+INTERVAL 12 HOUR,
                                     INTERVAL 12 HOUR) t(start_time)
            ), counts AS (
                SELECT date_trunc('day',first_obs_time)+
                       CASE WHEN hour(first_obs_time)<12 THEN INTERVAL 0 HOUR
                            ELSE INTERVAL 12 HOUR END start_time,
                       count(*) group_count,sum(draft_count) drafts
                FROM groups GROUP BY 1
            )
            SELECT count(*) shift_count,quantile_cont(coalesce(group_count,0),[.5,.9,.95,.99])
                   group_quantiles,max(coalesce(group_count,0)) max_groups,
                   max(coalesce(drafts,0)) max_drafts
            FROM slots LEFT JOIN counts USING(start_time)
        """).fetchone()
        top = con.execute("""
            WITH shifts AS (
                SELECT date_trunc('day',first_obs_time)+
                       CASE WHEN hour(first_obs_time)<12 THEN INTERVAL 0 HOUR
                            ELSE INTERVAL 12 HOUR END shift_start,
                       count(*) group_count,sum(draft_count) draft_count
                FROM groups GROUP BY 1
            ), peak AS (
                SELECT * FROM shifts ORDER BY group_count DESC,draft_count DESC,
                         shift_start LIMIT 3
            )
            SELECT p.shift_start,p.group_count,p.draft_count,g.group_id,g.object_id,
                   g.first_obs_time,g.draft_count,g.forecast_count,g.observed_count
            FROM peak p JOIN groups g ON g.first_obs_time>=p.shift_start
                  AND g.first_obs_time<p.shift_start+INTERVAL 12 HOUR
            ORDER BY p.group_count DESC,p.draft_count DESC,p.shift_start,
                     g.draft_count DESC,g.first_obs_time
        """).fetchall()
        report = {
            "period": period,
            "calendar_days": daily[0], "daily_group_quantiles": daily[1],
            "max_daily_groups": daily[2], "max_daily_drafts": daily[3],
            "twelve_hour_shifts": shifts[0], "shift_group_quantiles": shifts[1],
            "max_shift_groups": shifts[2], "max_shift_drafts": shifts[3],
            "top_shift_groups": [dict(zip((
                "shift_start", "shift_groups", "shift_drafts", "group_id", "object_id",
                "first_obs_time", "draft_count", "forecast_count", "observed_count"), row))
                for row in top],
        }
        path = folder / "workload.json"
        path.write_text(json.dumps(report, ensure_ascii=False, default=str, indent=2),
                        encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items()
                          if key != "top_shift_groups"}, ensure_ascii=False), flush=True)
        print(json.dumps({"period": period, "peak_shift_groups": report["top_shift_groups"][:5]},
                         ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
