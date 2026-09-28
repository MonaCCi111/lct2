"""Read-only checks of the rebuilt hourly SCADA labels."""
import json
import os
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
source = Path(os.environ.get("LCT2_SOURCE_ROOT", root))
data = root / "production_ml" / "data"
episodes = source / "production_ml" / "data" / "cache_v6" / "persistent_failure_episodes.parquet"
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='4GB'")
con.execute(f"CREATE VIEW episodes AS SELECT * FROM read_parquet('{episodes.as_posix()}')")

def emit(name, sql):
    cursor = con.execute(sql)
    fields = [x[0] for x in cursor.description]
    rows = [dict(zip(fields, row)) for row in cursor.fetchall()]
    print(json.dumps({"check": name, "rows": rows}, ensure_ascii=False, default=str), flush=True)

for name, filename in (("train", "v6_2_train_full_multihorizon.parquet"), ("stream", "v6_2_stream_18m.parquet"), ("matched", "v6_2_matched_18m.parquet")):
    path = data / filename
    con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    emit(name + "_summary", f"SELECT count(*) n_rows, count(DISTINCT channel_id) channels, min(obs_time) first_obs, max(obs_time) last_obs, sum(target_combined_1_48h) positives FROM {name}")
    emit(name + "_duplicates", f"SELECT coalesce(sum(n-1),0) extra_rows FROM (SELECT channel_id,obs_time,count(*) n FROM {name} GROUP BY 1,2 HAVING n>1)")
    emit(name + "_inside_episode", f"SELECT count(*) n_rows FROM {name} s WHERE EXISTS (SELECT 1 FROM episodes e WHERE e.channel_id=s.channel_id AND e.t_fail_start < s.obs_time AND e.t_fail_end >= s.obs_time - INTERVAL 1 HOUR)")
    emit(name + "_target_consistency", f"SELECT count(*) n_rows FROM {name} WHERE target_combined_1_48h != target_flash_1_6h + target_urgent_6_24h + target_planned_24_48h")

emit("positive_lead_range", "SELECT count(*) positive_rows, min(epoch(e.t_fail_start-s.obs_time)/3600) min_hours, max(epoch(e.t_fail_start-s.obs_time)/3600) max_hours FROM stream s JOIN episodes e ON e.channel_id=s.channel_id AND e.t_fail_start BETWEEN s.obs_time + INTERVAL 1 HOUR AND s.obs_time + INTERVAL 48 HOUR WHERE s.target_combined_1_48h=1")
emit("train_years", "SELECT year(obs_time) yr,count(*) n_rows,sum(target_combined_1_48h) positives FROM train GROUP BY 1 ORDER BY 1")
emit("stream_years", "SELECT year(obs_time) yr,count(*) n_rows,sum(target_combined_1_48h) positives FROM stream GROUP BY 1 ORDER BY 1")
