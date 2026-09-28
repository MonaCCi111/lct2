"""Фиксированное обучение temperature_scada_v1."""

import json
import pickle
import sys
from pathlib import Path

import duckdb
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .temperature_model import MODEL_FEATURES, model_frame


VERSION = "temperature_scada_v1"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = Path(__file__).resolve().parents[1] / "data" / "temperature_v1"
    con = duckdb.connect()
    con.execute("SET threads=4")
    feature_columns = ",".join(f'f."{name}"' for name in MODEL_FEATURES)

    def load(where):
        return con.execute(f"""
            SELECT {feature_columns},l.target_1_48h,f.channel_id,f.obs_time
            FROM read_parquet('{(data / 'features.parquet').as_posix()}') f
            JOIN read_parquet('{(data / 'labels.parquet').as_posix()}') l
              USING(channel_id,obs_time)
            WHERE l.training_eligible AND ({where})
            ORDER BY f.obs_time,f.channel_id
        """).df()

    train = load(
        "year(f.obs_time) IN (2020,2022) "
        "OR (year(f.obs_time)=2023 AND f.obs_time<TIMESTAMP '2023-12-30')"
    )
    if train.empty or train.target_1_48h.nunique() != 2:
        raise ValueError("Обучающая выборка пуста или содержит один класс")
    model = LGBMClassifier(
        n_estimators=220,
        num_leaves=31,
        learning_rate=0.05,
        min_child_samples=100,
        random_state=42,
        n_jobs=4,
        verbosity=-1,
    )
    model.fit(model_frame(train), train.target_1_48h)
    print(json.dumps({
        "split": "train",
        "rows": len(train),
        "positives": int(train.target_1_48h.sum()),
    }), flush=True)

    calibration = load(
        "f.obs_time>=TIMESTAMP '2024-01-03' "
        "AND f.obs_time<TIMESTAMP '2024-06-29'"
    )
    raw = model.predict_proba(model_frame(calibration))[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        raw, calibration.target_1_48h
    )
    calibrated = calibrator.transform(raw)
    print(json.dumps({
        "split": "calibration",
        "rows": len(calibration),
        "positives": int(calibration.target_1_48h.sum()),
        "raw_brier": float(brier_score_loss(calibration.target_1_48h, raw)),
        "calibrated_brier": float(
            brier_score_loss(calibration.target_1_48h, calibrated)
        ),
    }), flush=True)

    policy = load(
        "f.obs_time>=TIMESTAMP '2024-07-03' "
        "AND f.obs_time<TIMESTAMP '2024-12-30'"
    )
    score = calibrator.transform(model.predict_proba(model_frame(policy))[:, 1])
    quantiles = {
        str(q): float(np.quantile(score, q))
        for q in (0.5, 0.9, 0.95, 0.99, 0.995, 0.999, 1.0)
    }
    print(json.dumps({
        "split": "policy_2024",
        "rows": len(policy),
        "positives": int(policy.target_1_48h.sum()),
        "roc_auc": float(roc_auc_score(policy.target_1_48h, score)),
        "average_precision": float(
            average_precision_score(policy.target_1_48h, score)
        ),
        "score_quantiles": quantiles,
    }), flush=True)
    stored = policy[["channel_id", "obs_time", "target_1_48h"]].copy()
    stored["score"] = score
    con.register("temperature_policy_scores", stored)
    con.execute(f"""
        COPY temperature_policy_scores
        TO '{(data / 'policy_2024_train_scores.parquet').as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.unregister("temperature_policy_scores")
    with (data / "model.pkl").open("wb") as handle:
        pickle.dump(model, handle)
    with (data / "calibrator.pkl").open("wb") as handle:
        pickle.dump(calibrator, handle)
    meta = {
        "version": VERSION,
        "model_features": MODEL_FEATURES,
        "random_state": 42,
        "train": "2020, 2022, 2023 through 2023-12-29",
        "calibration": "2024-01-03 through 2024-06-28",
        "policy_period": "2024-07-03 through 2024-12-29",
        "model_parameters": model.get_params(),
    }
    (data / "model_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
