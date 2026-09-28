"""Сопоставить фиксированные варианты насоса по временным периодам и нагрузке."""

import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from production_ml.pipeline.pump_model import MODEL_FEATURES, model_frame


sys.stdout.reconfigure(encoding="utf-8")
data = Path(__file__).resolve().parents[1] / "data" / "pump_v1"
con = duckdb.connect()
con.execute("SET threads=4")
frame = con.execute(f"""
    SELECT f.*,l.target_1_48h,l.target_episode_id
    FROM read_parquet('{(data/'features.parquet').as_posix()}') f
    JOIN read_parquet('{(data/'labels.parquet').as_posix()}') l
      USING(channel_id,obs_time)
    WHERE l.training_eligible
      AND (year(f.obs_time) IN (2020,2021,2022,2023,2025,2026)
           OR f.obs_time BETWEEN TIMESTAMP '2024-01-03' AND TIMESTAMP '2024-12-29 23:59:59')
    ORDER BY f.obs_time,f.channel_id
""").df()
con.close()
time = frame.obs_time
train = frame[(time.dt.year.isin([2020,2022])) |
              ((time.dt.year==2023) & (time < "2023-12-30"))]
cal = frame[(time >= "2024-01-03") & (time < "2024-06-29")]
policy = frame[(time >= "2024-07-03") & (time < "2024-12-30")]
diag = frame[time >= "2025-01-01"]
holdout_2021 = frame[time.dt.year == 2021]


def queue(rows, scores, threshold):
    selected = rows[["channel_id", "obs_time", "target_1_48h", "target_episode_id"]].copy()
    selected["score"] = scores
    selected = selected[selected.score >= threshold].sort_values(
        ["obs_time", "score", "channel_id"], ascending=[True, False, True]
    )
    last = {}
    keep = []
    for item in selected.itertuples():
        if item.channel_id in last and item.obs_time < last[item.channel_id] + np.timedelta64(48, "h"):
            continue
        last[item.channel_id] = item.obs_time
        keep.append(item)
    days = Counter(item.obs_time.date() for item in keep)
    return {
        "candidates": len(selected), "drafts": len(keep),
        "matched_drafts": sum(item.target_1_48h for item in keep),
        "unique_target_episodes": len({(item.channel_id, item.target_episode_id)
                                        for item in keep if item.target_1_48h}),
        "max_daily_drafts": max(days.values(), default=0),
        "channels": len({item.channel_id for item in keep}),
    }


with (data/"model.pkl").open("rb") as file:
    current = pickle.load(file)
with (data/"calibrator.pkl").open("rb") as file:
    old_calibrator = pickle.load(file)
current_cal = old_calibrator.transform(current.predict_proba(model_frame(cal))[:, 1])
baseline_cal_candidates = int((current_cal >= 0.11).sum())
print("SPLITS",json.dumps({name:{"rows":len(rows),"positives":int(rows.target_1_48h.sum()),
                                  "target_episodes":rows.loc[rows.target_1_48h==1,["channel_id","target_episode_id"]].drop_duplicates().shape[0]}
                           for name,rows in (("train",train),("cal",cal),("policy",policy),("diag",diag),
                                             ("holdout_2021",holdout_2021))}),flush=True)
print("BASELINE_CAL_CANDIDATES",baseline_cal_candidates,flush=True)

variants = {
    "v1_existing": current,
    "compact_lgbm": LGBMClassifier(n_estimators=100,num_leaves=7,learning_rate=0.04,
                                   min_child_samples=300,random_state=42,n_jobs=4,verbosity=-1),
    "status_free_lgbm": LGBMClassifier(n_estimators=120,num_leaves=15,learning_rate=0.04,
                                       min_child_samples=200,random_state=42,n_jobs=4,verbosity=-1),
    "linear": Pipeline([
        ("columns",ColumnTransformer([
            ("status",OneHotEncoder(handle_unknown="ignore"),["current_status"]),
            ("numbers",StandardScaler(),list(MODEL_FEATURES[1:])),
        ])),
        ("model",LogisticRegression(max_iter=1000,random_state=42)),
    ]),
}

for name, model in variants.items():
    features = list(MODEL_FEATURES[1:]) if name == "status_free_lgbm" else list(MODEL_FEATURES)
    x_train = model_frame(train)[features]
    x_cal = model_frame(cal)[features]
    x_policy = model_frame(policy)[features]
    x_diag = model_frame(diag)[features]
    x_holdout = model_frame(holdout_2021)[features]
    if name != "v1_existing":
        model.fit(x_train, train.target_1_48h)
    score_cal = model.predict_proba(x_cal)[:, 1]
    score_policy = model.predict_proba(x_policy)[:, 1]
    score_diag = model.predict_proba(x_diag)[:, 1]
    score_holdout = model.predict_proba(x_holdout)[:, 1]
    threshold = float(np.sort(score_cal)[-baseline_cal_candidates]) if baseline_cal_candidates else 1.0
    result = {"variant":name,"threshold_equal_cal_candidates":threshold}
    for split, rows, scores in (("cal",cal,score_cal),("policy",policy,score_policy),
                                ("diag",diag,score_diag),("holdout_2021",holdout_2021,score_holdout)):
        result[split] = {
            "roc_auc":float(roc_auc_score(rows.target_1_48h,scores)),
            "ap":float(average_precision_score(rows.target_1_48h,scores)),
            "brier":float(brier_score_loss(rows.target_1_48h,scores)),
            "queue":queue(rows,scores,threshold),
        }
    print("VARIANT",json.dumps(result,ensure_ascii=False),flush=True)
    if name == "compact_lgbm":
        for q in (0.90,0.92,0.94,0.96,0.97,0.98,0.99):
            cut = float(np.quantile(score_cal,q))
            print("COMPACT_GRID",json.dumps({
                "cal_quantile":q,"threshold":cut,
                "cal":queue(cal,score_cal,cut),
                "policy":queue(policy,score_policy,cut),
                "diag":queue(diag,score_diag,cut),
                "holdout_2021":queue(holdout_2021,score_holdout,cut),
            }),flush=True)

current_policy = old_calibrator.transform(current.predict_proba(model_frame(policy))[:, 1])
current_diag = old_calibrator.transform(current.predict_proba(model_frame(diag))[:, 1])
current_holdout = old_calibrator.transform(current.predict_proba(model_frame(holdout_2021))[:, 1])
print("CURRENT_RELEASED",json.dumps({"policy":queue(policy,current_policy,0.11),
                                     "diag":queue(diag,current_diag,0.11),
                                     "holdout_2021":queue(holdout_2021,current_holdout,0.11)}),flush=True)
