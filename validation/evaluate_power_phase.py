"""Проверка баллов и фиксированной политики на эпизодах SCADA."""

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from production_ml.pipeline.alerts import load_policy, select_alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("threshold_2024", "diagnostic_2025_2026"))
    parser.add_argument("--threshold", type=float)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "power_phase_v1"
    episodes = (data / "episodes.parquet").as_posix()
    labels = (data / "labels.parquet").as_posix()
    features = (data / "features.parquet").as_posix()
    policy = load_policy()
    if args.threshold is not None:
        policy["score_threshold"] = args.threshold
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute(f"CREATE VIEW episodes AS SELECT * FROM read_parquet('{episodes}')")

    for split, filename, start, end in (
        ("threshold_2024", "threshold_2024_inference.parquet", "2024-07-03", "2024-12-30"),
        ("diagnostic_2025_2026", "diagnostic_2025_2026_scores.parquet", "2025-01-03", "2026-07-01"),
    ):
        if args.split is not None and split != args.split:
            continue
        scores = (data / filename).as_posix()
        con.execute(f"CREATE OR REPLACE VIEW scored AS SELECT * FROM read_parquet('{scores}')")
        frame = con.execute(f"""
            SELECT s.channel_id,s.obs_time,s.score,l.target_1_48h,
                   f.event_count_24h
            FROM scored s JOIN read_parquet('{labels}') l USING(channel_id,obs_time)
            JOIN read_parquet('{features}') f USING(channel_id,obs_time)
        """).df()
        target = frame.target_1_48h
        baseline = -frame.event_count_24h
        print(json.dumps({
            "split": split, "check": "row_ranking", "rows": len(frame),
            "positives": int(target.sum()),
            "roc_auc": float(roc_auc_score(target, frame.score)),
            "average_precision": float(average_precision_score(target, frame.score)),
            "brier": float(brier_score_loss(target, frame.score)),
            "count_baseline_roc_auc": float(roc_auc_score(target, baseline)),
            "count_baseline_ap": float(average_precision_score(target, baseline)),
        }), flush=True)
        for lower, upper in ((0, .1), (.1, .5), (.5, .8), (.8, .9), (.9, 1.000001)):
            subset = frame[(frame.score >= lower) & (frame.score < upper)]
            print(json.dumps({"split": split, "check": "score_bin", "lower": lower,
                              "upper": upper, "rows": len(subset),
                              "mean_score": float(subset.score.mean()) if len(subset) else None,
                              "event_rate": float(subset.target_1_48h.mean()) if len(subset) else None}), flush=True)
        del frame

        eligible_episodes = con.execute(f"""
            SELECT count(*) FROM episodes e
            WHERE e.episode_start>=TIMESTAMP '{start}' AND e.episode_start<TIMESTAMP '{end}'
              AND EXISTS (SELECT 1 FROM scored s WHERE s.channel_id=e.channel_id
                          AND s.obs_time BETWEEN e.episode_start-INTERVAL 48 HOUR
                                             AND e.episode_start-INTERVAL 1 HOUR)
        """).fetchone()[0]
        all_episodes = con.execute(f"SELECT count(*) FROM episodes WHERE episode_start>=TIMESTAMP '{start}' AND episode_start<TIMESTAMP '{end}'").fetchone()[0]
        candidates = con.execute(f"""
            SELECT channel_id,obs_time,score FROM scored
            WHERE score>={policy['score_threshold']}
            ORDER BY obs_time,score DESC,channel_id
        """).fetchall()
        alerts, daily = select_alerts(candidates, policy)
        con.register("alerts", pd.DataFrame(alerts, columns=["alert_id", "channel_id", "obs_time", "score"]))
        alert_types = con.execute(f"""
            SELECT f.sensor_type,count(*) n
            FROM alerts a JOIN read_parquet('{features}') f USING(channel_id,obs_time)
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        matched_tickets, caught_episodes, median_lead = con.execute(f"""
            SELECT count(DISTINCT a.alert_id), count(DISTINCT (e.channel_id,e.episode_id)),
                   median(epoch(e.episode_start-a.obs_time)/3600)
            FROM alerts a JOIN episodes e ON a.channel_id=e.channel_id
             AND e.episode_start BETWEEN a.obs_time+INTERVAL 1 HOUR
                                     AND a.obs_time+INTERVAL 48 HOUR
             AND e.episode_start<TIMESTAMP '{end}'
        """).fetchone()
        con.unregister("alerts")
        days = con.execute(f"SELECT date_diff('day',TIMESTAMP '{start}',TIMESTAMP '{end}')").fetchone()[0]
        print(json.dumps({
            "split": split, "check": "tickets", "policy": policy["version"],
            "threshold": policy["score_threshold"], "candidates": len(candidates),
            "tickets": len(alerts), "tickets_per_day": len(alerts)/days,
            "days_at_limit": sum(count == policy["daily_ticket_limit"] for count in daily.values()),
            "matched_tickets": matched_tickets,
            "ticket_match_rate": matched_tickets/len(alerts) if alerts else None,
            "caught_episodes": caught_episodes, "all_episodes": all_episodes,
            "observable_episodes": eligible_episodes,
            "recall_all": caught_episodes/all_episodes if all_episodes else None,
            "recall_observable": caught_episodes/eligible_episodes if eligible_episodes else None,
            "median_lead_hours": median_lead,
        }), flush=True)
        print(json.dumps({"split": split, "check": "tickets_by_sensor",
                          "rows": [{"sensor_type": sensor, "tickets": count} for sensor, count in alert_types]},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
