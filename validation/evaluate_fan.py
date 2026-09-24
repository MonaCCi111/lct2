"""Проверить зафиксированную политику вентилятора на уровне заявок."""

import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.alerts import select_alerts


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "fan_v1"
    policy = json.loads((root / "production_ml" / "models" / "fan_scada_v1" / "policy.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    labels = (data / "labels.parquet").as_posix()
    for split,score_name in (
        ("policy_2024","policy_2024_scores.parquet"),
        ("diagnostic_2025_2026","diagnostic_scores.parquet"),
    ):
        scores = (data / score_name).as_posix()
        rows = con.execute(f"""
            SELECT s.channel_id,s.obs_time,s.score,l.target_1_48h,l.target_episode_id
            FROM read_parquet('{scores}') s
            JOIN read_parquet('{labels}') l USING(channel_id,obs_time)
            WHERE l.training_eligible
            ORDER BY s.obs_time,s.score DESC,s.channel_id
        """).fetchall()
        available = {(r[0],r[4]) for r in rows if r[3]==1}
        targets = {(r[0],r[1]): (r[3],r[4]) for r in rows}
        selected,daily = select_alerts([(r[0],r[1],r[2]) for r in rows],policy)
        matched = [targets[(channel_id,obs_time)] for _,channel_id,obs_time,_ in selected]
        covered = {(selected[i][1],value[1]) for i,value in enumerate(matched) if value[0]==1}
        print(json.dumps({
            "split":split,"threshold":policy["score_threshold"],
            "eligible_rows":len(rows),"available_episodes":len(available),
            "tickets":len(selected),"matched_tickets":sum(value[0] for value in matched),
            "covered_episodes":len(covered),"days_at_limit":sum(n==policy["daily_ticket_limit"] for n in daily.values()),
            "max_daily":max(daily.values(),default=0),
        }),flush=True)


if __name__ == "__main__":
    main()
