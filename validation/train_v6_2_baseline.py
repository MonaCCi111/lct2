"""Fixed, untuned baseline on the corrected SCADA proxy labels."""
import json
import pickle
import sys
from pathlib import Path

import duckdb
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

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
train = (data / "v6_2_train_full_multihorizon.parquet").as_posix()
stream = (data / "v6_2_stream_18m.parquet").as_posix()
candidate_dir = data / "candidate_models_v6_2"
candidate_dir.mkdir(exist_ok=True)

def metrics(domain, split, method, target, scores):
    print(json.dumps({
        "domain": domain, "split": split, "method": method,
        "rows": len(target), "positives": int(target.sum()),
        "roc_auc": float(roc_auc_score(target, scores)),
        "average_precision": float(average_precision_score(target, scores)),
    }), flush=True)

for domain, head in manifest["heads"].items():
    sensors = ",".join("'" + sensor.replace("'", "''") + "'" for sensor in head["sensors"])
    columns = ",".join(features + ["target_combined_1_48h"])
    training = con.execute(f"SELECT {columns} FROM read_parquet('{train}') WHERE sensor_type IN ({sensors}) AND year(obs_time) IN (2020,2022,2023) AND month(obs_time)>1 AND obs_time < TIMESTAMP '2023-12-30'").df()
    model = LGBMClassifier(n_estimators=160, num_leaves=15, learning_rate=0.05, min_child_samples=100, random_state=42, n_jobs=4, verbosity=-1)
    model.fit(training[features], training.target_combined_1_48h)
    print(json.dumps({"domain": domain, "split": "train", "rows": len(training), "positives": int(training.target_combined_1_48h.sum())}), flush=True)
    with (candidate_dir / f"{domain.lower()}.pkl").open("wb") as handle:
        pickle.dump(model, handle)
    del training
    for split, source, dates in (
        ("validation_2024", train, "obs_time >= TIMESTAMP '2024-02-01' AND obs_time < TIMESTAMP '2024-12-30'"),
        ("diagnostic_2025_2026", stream, "obs_time >= TIMESTAMP '2025-02-01'"),
    ):
        test = con.execute(f"SELECT {columns} FROM read_parquet('{source}') WHERE sensor_type IN ({sensors}) AND {dates}").df()
        target = test.target_combined_1_48h.to_numpy()
        metrics(domain, split, "fixed_lightgbm", target, model.predict_proba(test[features])[:, 1])
        metrics(domain, split, "alarm_ratio_24h", target, test.alarm_ratio_24h.fillna(0).to_numpy())
        del test
