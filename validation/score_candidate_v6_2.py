"""Measure fixed candidate scores on 2024 and the later diagnostic stream."""
import json
import pickle
import sys
from pathlib import Path

import duckdb
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
data = root / "production_ml" / "data"
manifest = json.loads((root / "production_ml" / "models" / "models_meta.json").read_text(encoding="utf-8"))
features = [
    "flips_count_1h", "flips_count_24h", "flips_count_72h", "events_count_24h",
    "sub2s_flips_24h", "micro_burst_sub2s_ratio", "period_jitter_cv",
    "undefined_count_24h", "undefined_ratio_24h", "alarm_ratio_24h",
    "analog_std_24h", "analog_drift_12h",
]
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='4GB'")
sources = {
    "validation_2024": (data / "v6_2_train_full_multihorizon.parquet", "obs_time >= TIMESTAMP '2024-02-01' AND obs_time < TIMESTAMP '2024-12-30'"),
    "diagnostic_2025_2026": (data / "v6_2_stream_18m.parquet", "obs_time >= TIMESTAMP '2025-02-01' AND obs_time < TIMESTAMP '2026-07-01'"),
}
for split, (path, dates) in sources.items():
    for domain, head in manifest["heads"].items():
        sensors = ",".join("'" + sensor.replace("'", "''") + "'" for sensor in head["sensors"])
        columns = ",".join(features + ["channel_id", "obs_time", "sensor_type", "target_combined_1_48h"])
        frame = con.execute(f"SELECT {columns} FROM read_parquet('{path.as_posix()}') WHERE sensor_type IN ({sensors}) AND {dates}").df()
        with (data / "candidate_models_v6_2" / f"{domain.lower()}.pkl").open("rb") as handle:
            model = pickle.load(handle)
        score = model.predict_proba(frame[features])[:, 1]
        print(json.dumps({"split": split, "domain": domain, "n": len(score), "quantiles": dict(zip(["p99", "p995", "p998", "p999"], [float(x) for x in np.quantile(score, [0.99, 0.995, 0.998, 0.999])]))}), flush=True)
        output = frame[["channel_id", "obs_time", "sensor_type", "target_combined_1_48h"]].copy()
        output["candidate_score"] = score
        con.register("score_rows", output)
        target_path = data / f"candidate_scores_{split}_{domain.lower()}.parquet"
        con.execute(f"COPY score_rows TO '{target_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.unregister("score_rows")
    paths = ",".join(f"'{p.as_posix()}'" for p in sorted(data.glob(f"candidate_scores_{split}_*.parquet")))
    quantiles = con.execute(f"SELECT count(*) n, quantile_cont(candidate_score,[0.99,0.995,0.998,0.999]) q FROM read_parquet([{paths}])").fetchone()
    print(json.dumps({"split": split, "all_domains_n": quantiles[0], "all_domains_quantiles": quantiles[1]}), flush=True)
