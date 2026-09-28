"""Воспроизводимое исследование будущих статусов неисправности трёх типов."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CONFIG = {
    "ИБП": {
        "fault": {"Батарея разряжена", "Неисправен", "Отключено устройство"},
        "recovery": {"Питание от сети", "Норма"},
    },
    "КД АВ": {
        "fault": {"Неисправен", "Отключено устройство"},
        "recovery": {"Норма"},
    },
    "Состояние охраны": {
        "fault": {"Много неисправных устройств"},
        "recovery": {"Устройства на объекте исправны"},
    },
}
NUMERIC = ("events_1h", "events_24h", "alarms_24h", "changes_24h",
           "observed_hours_72h", "hours_since_fault")


def episodes_from_events(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    records = []
    current = {}
    for row in events.itertuples(index=False):
        channel = row.channel_id
        if row.is_alarm and row.sensor_value in config["fault"] and channel not in current:
            records.append({"channel_id": channel, "episode_id": len(records) + 1,
                            "episode_start": row.event_time, "first_status": row.sensor_value,
                            "recovery_time": pd.NaT})
            current[channel] = len(records) - 1
        elif not row.is_alarm and row.sensor_value in config["recovery"] and channel in current:
            records[current.pop(channel)]["recovery_time"] = row.event_time
    return pd.DataFrame(records)


def queue(rows: pd.DataFrame, score: np.ndarray, threshold: float) -> dict:
    found = rows[["channel_id", "obs_time", "target", "target_episode_id"]].copy()
    found["score"] = score
    found = found[found.score >= threshold].sort_values(
        ["obs_time", "score", "channel_id"], ascending=[True, False, True]
    )
    selected = []
    last = {}
    for row in found.itertuples(index=False):
        if row.channel_id in last and row.obs_time < last[row.channel_id] + pd.Timedelta(hours=48):
            continue
        selected.append(row)
        last[row.channel_id] = row.obs_time
    days = Counter(row.obs_time.date() for row in selected)
    return {
        "candidate_rows": len(found), "drafts": len(selected),
        "matched_drafts": sum(row.target for row in selected),
        "matched_unique_episodes": len({(row.channel_id, row.target_episode_id)
                                        for row in selected if row.target}),
        "max_daily_drafts": max(days.values(), default=0),
        "channels": len({row.channel_id for row in selected}),
    }


def run_type(con: duckdb.DuckDBPyConnection, files: str, catalog: Path,
             sensor_type: str, output: Path) -> dict:
    config = CONFIG[sensor_type]
    events = con.execute(f"""
        SELECT j.channel_id,j.event_time,j.event_id,j.sensor_value,j.is_alarm
        FROM read_parquet({files}) j
        JOIN read_csv('{catalog.as_posix()}',header=true) c
          ON j.channel_id=c."ид_канала_данных"
        WHERE c."тип_датчика"=?
        ORDER BY j.channel_id,j.event_time,j.event_id,j.sensor_value,j.is_alarm
    """, [sensor_type]).df()
    mixed = events.groupby(["channel_id", "event_time"]).is_alarm.transform("nunique") > 1
    mixed_rows = int(mixed.sum())
    events = events.loc[~mixed].copy()
    episodes = episodes_from_events(events, config)
    if episodes.empty:
        return {"sensor_type": sensor_type, "reason": "no_unambiguous_fault_episodes"}
    con.register("ev", events)
    con.register("ep", episodes)
    features = con.execute("""
        WITH ordered AS (
            SELECT *,lag(sensor_value) OVER
              (PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value,is_alarm) prior_value
            FROM ev
        ), hours AS (
            SELECT channel_id,date_trunc('hour',event_time) hour_bin,
                   count(*) events_1h,
                   max(event_time) latest_input_time,
                   count(*) FILTER(WHERE is_alarm) alarms_1h,
                   count(*) FILTER(WHERE prior_value IS NOT NULL AND prior_value!=sensor_value) changes_1h,
                   arg_max(sensor_value,struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) last_status
            FROM ordered GROUP BY 1,2
        ), rolling AS (
            SELECT *,sum(events_1h) OVER w24 events_24h,
                   sum(alarms_1h) OVER w24 alarms_24h,
                   sum(changes_1h) OVER w24 changes_24h,
                   count(*) OVER w72 observed_hours_72h
            FROM hours
            WINDOW w24 AS (PARTITION BY channel_id ORDER BY hour_bin
                           RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
                   w72 AS (PARTITION BY channel_id ORDER BY hour_bin
                           RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW)
        ), base AS (
            SELECT channel_id,hour_bin+INTERVAL 1 HOUR obs_time,
                   latest_input_time,events_1h,events_24h,alarms_24h,changes_24h,observed_hours_72h,
                   CASE WHEN last_status IN ('Норма','Неопределен','На охране',
                        'Снято с охраны','Устройства на объекте исправны',
                        'Питание от сети','Питание от батарей','Батарея неисправна',
                        'Не замкнут','Выключен') THEN last_status ELSE 'Другое' END current_status
            FROM rolling
        ), history AS (
            SELECT b.*,p.episode_id previous_episode_id,
                   p.episode_start previous_episode_start,p.recovery_time previous_recovery_time
            FROM base b ASOF LEFT JOIN ep p
              ON b.channel_id=p.channel_id AND b.obs_time>=p.episode_start
        ), future AS (
            SELECT h.*,n.episode_id target_episode_id_raw,
                   n.episode_start target_episode_start
            FROM history h ASOF LEFT JOIN ep n
              ON h.channel_id=n.channel_id AND h.obs_time<n.episode_start
        ), bounds AS (
            SELECT channel_id,min(event_time) first_event_time,max(event_time) last_event_time
            FROM ev GROUP BY 1
        )
        SELECT f.*,b.first_event_time,b.last_event_time,
               epoch(f.obs_time-f.previous_episode_start)/3600.0 hours_since_fault
        FROM future f JOIN bounds b USING(channel_id)
        ORDER BY f.obs_time,f.channel_id
    """).df()
    con.unregister("ev")
    con.unregister("ep")
    if features.duplicated(["channel_id", "obs_time"]).any():
        raise ValueError(f"Повтор ключа признаков: {sensor_type}")
    if (features.latest_input_time >= features.obs_time).any():
        raise ValueError(f"Событие недоступно к obs_time: {sensor_type}")
    eligibility = (
        (features.first_event_time <= features.obs_time-pd.Timedelta(hours=72)) &
        (features.last_event_time >= features.obs_time+pd.Timedelta(hours=48)) &
        (features.previous_episode_id.isna() |
         (features.previous_recovery_time <= features.obs_time-pd.Timedelta(hours=48)))
    )
    features = features.loc[eligibility].copy()
    hit = ((features.target_episode_start >= features.obs_time+pd.Timedelta(hours=1)) &
           (features.target_episode_start <= features.obs_time+pd.Timedelta(hours=48)))
    features["target"] = hit.astype("int8")
    features["target_episode_id"] = features.target_episode_id_raw.where(hit)
    leads = (features.loc[hit,"target_episode_start"]-features.loc[hit,"obs_time"]).dt.total_seconds()/3600
    if not leads.empty and (leads.min()<1 or leads.max()>48):
        raise ValueError(f"Метка вне горизонта: {sensor_type}")
    features["hours_since_fault"] = features.hours_since_fault.fillna(10000).clip(0,10000)
    features["current_status"] = pd.Categorical(features.current_status, categories=[
        "Норма", "Неопределен", "На охране", "Снято с охраны",
        "Устройства на объекте исправны", "Питание от сети",
        "Питание от батарей", "Батарея неисправна", "Не замкнут",
        "Выключен", "Другое",
    ])
    time = features.obs_time
    splits = {
        "train": features[(time.dt.year.isin([2020,2022])) |
                          ((time.dt.year==2023) & (time < "2023-12-30"))],
        "cal": features[(time >= "2024-01-03") & (time < "2024-06-29")],
        "policy": features[(time >= "2024-07-03") & (time < "2024-12-30")],
        "diag": features[time >= "2025-01-01"],
    }
    split_facts = {
        name: {"rows":len(rows),"positives":int(rows.target.sum()),
               "unique_target_episodes":len(rows.loc[rows.target==1,
                   ["channel_id","target_episode_id"]].drop_duplicates())}
        for name,rows in splits.items()
    }
    split_targets = [set(map(tuple,rows.loc[rows.target==1,
                     ["channel_id","target_episode_id"]].itertuples(index=False,name=None)))
                     for key,rows in splits.items() if key in ("train","cal","policy","diag")]
    for i,left in enumerate(split_targets):
        for right in split_targets[i+1:]:
            if left & right:
                raise ValueError(f"Целевой эпизод пересекает выборки: {sensor_type}")
    result = {
        "sensor_type": sensor_type, "source_events": len(events)+mixed_rows,
        "mixed_rows_excluded": mixed_rows, "episodes": len(episodes),
        "split_facts": split_facts, "variants": [],
    }
    if any(rows.empty or rows.target.nunique()<2 for key,rows in splits.items()
           if key in ("train","cal","policy")):
        result["reason"] = "insufficient_split_classes"
        return result
    xcols = ["current_status", *NUMERIC]
    models = {
        "compact_lgbm": LGBMClassifier(n_estimators=100,num_leaves=7,learning_rate=0.04,
                                       min_child_samples=100,random_state=42,n_jobs=4,verbosity=-1),
        "linear": Pipeline([
            ("columns",ColumnTransformer([
                ("status",OneHotEncoder(handle_unknown="ignore"),["current_status"]),
                ("numbers",StandardScaler(),list(NUMERIC)),
            ])),
            ("model",LogisticRegression(max_iter=1000,random_state=42)),
        ]),
    }
    for name,model in models.items():
        model.fit(splits["train"][xcols],splits["train"].target)
        scores = {key:model.predict_proba(rows[xcols])[:,1] for key,rows in splits.items()}
        variant = {"name": name, "quality": {}, "thresholds": []}
        for key in ("cal","policy","diag"):
            rows = splits[key]
            if rows.target.nunique() == 2:
                variant["quality"][key] = {
                    "roc_auc":float(roc_auc_score(rows.target,scores[key])),
                    "ap":float(average_precision_score(rows.target,scores[key])),
                    "prevalence":float(rows.target.mean()),
                }
        for q in (0.90,0.95,0.98,0.99,0.995):
            threshold = float(np.quantile(scores["cal"],q))
            variant["thresholds"].append({
                "cal_quantile":q,"threshold":threshold,
                "cal":queue(splits["cal"],scores["cal"],threshold),
                "policy":queue(splits["policy"],scores["policy"],threshold),
                "diag":queue(splits["diag"],scores["diag"],threshold),
            })
        result["variants"].append(variant)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root",type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"data"/"fault_candidate_results.jsonl")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    source = args.source_root/"production_ml/data/source_v2"
    files = [source/f"journal_{year}.parquet" for year in range(2019,2027)]
    catalog = args.source_root/"dataset/справочник_каналов_датчиков.csv"
    for path in [*files,catalog]:
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='8GB'")
    temp = args.output.parent/"fault_candidate_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory='{temp.as_posix()}'")
    sources = "["+",".join("'"+file.as_posix()+"'" for file in files)+"]"
    with args.output.open("w",encoding="utf-8") as file:
        for sensor_type in CONFIG:
            result = run_type(con,sources,catalog,sensor_type,args.output)
            file.write(json.dumps(result,ensure_ascii=False)+"\n")
            file.flush()
            print(json.dumps({"type":sensor_type,"episodes":result["episodes"],
                              "split_facts":result["split_facts"],
                              "models":len(result["variants"])},ensure_ascii=False),flush=True)
    con.close()


if __name__ == "__main__":
    main()
