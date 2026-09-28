"""Фиксированное обучение и калибровка балла эпизода SCADA."""

import json
import pickle
import sys
from pathlib import Path

import duckdb
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .model import MODEL_FEATURES, model_frame


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "data" / "power_phase_v1"
    features_path = (data / "features.parquet").as_posix()
    labels_path = (data / "labels.parquet").as_posix()
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    select_features = ",".join(f'f."{name}"' for name in MODEL_FEATURES)

    def load(where):
        return con.execute(f"""
            SELECT {select_features}, l.target_1_48h, f.channel_id, f.obs_time
            FROM read_parquet('{features_path}') f
            JOIN read_parquet('{labels_path}') l USING (channel_id,obs_time)
            WHERE l.eligible AND ({where})
        """).df()

    train = load("(year(f.obs_time)=2020 AND f.obs_time>=TIMESTAMP '2020-01-04') OR "
                 "(year(f.obs_time)=2022 AND f.obs_time>=TIMESTAMP '2022-01-04') OR "
                 "(year(f.obs_time)=2023 AND f.obs_time<TIMESTAMP '2023-12-30')")
    model = LGBMClassifier(n_estimators=220, num_leaves=31, learning_rate=0.05,
                           min_child_samples=100, random_state=42, n_jobs=4, verbosity=-1)
    model.fit(model_frame(train), train.target_1_48h)
    print(json.dumps({"split": "train", "rows": len(train), "positives": int(train.target_1_48h.sum())}), flush=True)
    del train

    calibration = load("f.obs_time>=TIMESTAMP '2024-01-03' AND f.obs_time<TIMESTAMP '2024-06-29'")
    raw_score = model.predict_proba(model_frame(calibration))[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_score, calibration.target_1_48h)
    print(json.dumps({"split": "calibration", "rows": len(calibration),
                      "positives": int(calibration.target_1_48h.sum()),
                      "raw_brier": float(brier_score_loss(calibration.target_1_48h, raw_score)),
                      "calibrated_brier_in_sample": float(brier_score_loss(calibration.target_1_48h, calibrator.transform(raw_score)))}), flush=True)
    del calibration

    threshold = load("f.obs_time>=TIMESTAMP '2024-07-03' AND f.obs_time<TIMESTAMP '2024-12-30'")
    score = calibrator.transform(model.predict_proba(model_frame(threshold))[:, 1])
    target = threshold.target_1_48h
    print(json.dumps({"split": "threshold_2024", "rows": len(threshold), "positives": int(target.sum()),
                      "roc_auc": float(roc_auc_score(target, score)),
                      "average_precision": float(average_precision_score(target, score)),
                      "brier": float(brier_score_loss(target, score))}), flush=True)
    output = threshold[["channel_id", "obs_time", "target_1_48h"]].copy()
    output["score"] = score
    con.register("scores", output)
    con.execute(f"COPY scores TO '{(data / 'threshold_2024_scores.parquet').as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("scores")

    with (data / "model.pkl").open("wb") as handle:
        pickle.dump(model, handle)
    with (data / "calibrator.pkl").open("wb") as handle:
        pickle.dump(calibrator, handle)
    meta = {
        "version": "power_phase_scada_v1", "model_features": MODEL_FEATURES,
        "target": "automatic_scada_episode_1_48h", "observation_time": "hour_end",
        "train": "2020, 2022, 2023 through 2023-12-29",
        "calibration": "2024-01-03 through 2024-06-28",
        "threshold_period": "2024-07-03 through 2024-12-29",
        "model_parameters": model.get_params(),
    }
    (data / "model_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
