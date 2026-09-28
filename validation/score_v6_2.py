"""Score the existing v7.2 models on corrected SCADA proxy labels."""
import json
import pickle
import sys
from pathlib import Path

import duckdb
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
data = root / "production_ml" / "data"
models = root / "production_ml" / "models"
meta = json.loads((models / "models_meta.json").read_text(encoding="utf-8"))
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='4GB'")
stream = (data / "v6_2_stream_18m.parquet").as_posix()

for domain, head in meta["heads"].items():
    sensors = ",".join("'" + sensor.replace("'", "''") + "'" for sensor in head["sensors"])
    df = con.execute(f"SELECT * FROM read_parquet('{stream}') WHERE sensor_type IN ({sensors})").df()
    df["inter_phase_arc_asym"] = df.state_transition_asymmetry_24h * df.micro_burst_sub2s_ratio
    df["inter_pump_night_duty"] = df.duty_cycle_24h * np.log1p(np.maximum(0, df.night_excess))
    df["inter_temp_std_freeze"] = df.analog_std_24h * np.log1p(df.adc_bit_freezing_hours)
    df["inter_gas_creep_quant"] = df.baseline_creep_7d.abs() * df.quantization_step_anomaly
    df["inter_fire_alarm_bounce"] = df.alarm_ratio_24h * np.log1p(df.rapid_bounce_triplet_count)
    df["inter_jitter_spec_entropy"] = df.period_jitter_cv * df.spectral_entropy_ls
    with (models / head["model_file"]).open("rb") as handle:
        model = pickle.load(handle)
    score = model.predict_proba(df[head["features"]].astype("float32").fillna(0), num_threads=4)[:, 1]
    target = df.target_combined_1_48h.to_numpy()
    baseline = df.alarm_ratio_24h.fillna(0).to_numpy()
    for name, values in (("saved_model", score), ("alarm_ratio_24h", baseline)):
        print(json.dumps({
            "domain": domain, "method": name, "rows": len(df), "positives": int(target.sum()),
            "roc_auc": float(roc_auc_score(target, values)),
            "average_precision": float(average_precision_score(target, values)),
        }), flush=True)
    output = df[["channel_id", "obs_time", "sensor_type", "target_combined_1_48h"]].copy()
    output["saved_model_score"] = score
    output["baseline_score"] = baseline
    path = data / f"v6_2_scores_{domain.lower()}.parquet"
    con.register("output_rows", output)
    con.execute(f"COPY output_rows TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("output_rows")
