"""Fixed ticket-count diagnostic against automatic SCADA episodes."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
source = Path(os.environ.get("LCT2_SOURCE_ROOT", root))
data = root / "production_ml" / "data"
scores = ",".join(f"'{p.as_posix()}'" for p in sorted(data.glob("v6_2_scores_*.parquet")))
episodes = (source / "production_ml" / "data" / "cache_v6" / "persistent_failure_episodes.parquet").as_posix()
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='4GB'")
con.execute(f"CREATE VIEW scored AS SELECT * FROM read_parquet([{scores}])")
con.execute(f"CREATE VIEW episodes AS SELECT * FROM read_parquet('{episodes}')")

period_start = "2025-01-01 01:00:00"
period_end = "2026-07-01 00:00:00"
all_episodes = con.execute(f"SELECT count(*) FROM episodes WHERE sensor_type IN (SELECT DISTINCT sensor_type FROM scored) AND t_fail_start >= TIMESTAMP '{period_start}' AND t_fail_start < TIMESTAMP '{period_end}'").fetchone()[0]
observable = con.execute(f"SELECT count(*) FROM episodes e WHERE e.sensor_type IN (SELECT DISTINCT sensor_type FROM scored) AND e.t_fail_start >= TIMESTAMP '{period_start}' AND e.t_fail_start < TIMESTAMP '{period_end}' AND EXISTS (SELECT 1 FROM scored s WHERE s.channel_id=e.channel_id AND s.obs_time BETWEEN e.t_fail_start - INTERVAL 48 HOUR AND e.t_fail_start - INTERVAL 1 HOUR)").fetchone()[0]
print(json.dumps({"check": "episode_denominators", "all_episodes": all_episodes, "observable_episodes": observable}), flush=True)

model_threshold = float(os.environ.get("ML_MODEL_THRESHOLD", "0.30"))
baseline_threshold = float(os.environ.get("ML_BASELINE_THRESHOLD", "0.05"))
for method, column, threshold in (("saved_model", "saved_model_score", model_threshold), ("alarm_ratio_24h", "baseline_score", baseline_threshold)):
    candidates = con.execute(f"SELECT channel_id,obs_time,sensor_type,{column} score FROM scored WHERE {column} >= {threshold} AND obs_time < TIMESTAMP '{period_end}' ORDER BY obs_time,score DESC,channel_id").fetchall()
    last_alert = {}
    daily_count = {}
    alerts = []
    for channel_id, obs_time, sensor_type, score in candidates:
        day = obs_time.date()
        if daily_count.get(day, 0) >= 10:
            continue
        if channel_id in last_alert and obs_time < last_alert[channel_id] + timedelta(hours=48):
            continue
        alerts.append((len(alerts), channel_id, obs_time, sensor_type, float(score)))
        last_alert[channel_id] = obs_time
        daily_count[day] = daily_count.get(day, 0) + 1
    con.register("alerts", pd.DataFrame(alerts, columns=["alert_id", "channel_id", "obs_time", "sensor_type", "score"]))
    matched_alerts, caught_episodes, median_lead = con.execute(f"""
        SELECT count(DISTINCT a.alert_id), count(DISTINCT (e.channel_id,e.ep_id)),
               median(epoch(e.t_fail_start-a.obs_time)/3600)
        FROM alerts a JOIN episodes e ON a.channel_id=e.channel_id
        AND e.t_fail_start BETWEEN a.obs_time + INTERVAL 1 HOUR AND a.obs_time + INTERVAL 48 HOUR
        AND e.t_fail_start < TIMESTAMP '{period_end}'
    """).fetchone()
    days = con.execute(f"SELECT date_diff('day', TIMESTAMP '{period_start}', TIMESTAMP '{period_end}')").fetchone()[0]
    print(json.dumps({
        "method": method, "threshold": threshold, "daily_limit": 10, "cooldown_hours": 48,
        "candidates": len(candidates), "tickets": len(alerts), "tickets_per_day": len(alerts)/days,
        "days_at_limit": sum(n == 10 for n in daily_count.values()), "matched_tickets": matched_alerts,
        "ticket_match_rate": matched_alerts/len(alerts) if alerts else None,
        "caught_episodes": caught_episodes, "all_episodes": all_episodes,
        "observable_episodes": observable,
        "recall_all": caught_episodes/all_episodes if all_episodes else None,
        "recall_observable": caught_episodes/observable if observable else None,
        "median_lead_hours": median_lead,
    }), flush=True)
    con.unregister("alerts")
