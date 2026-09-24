"""Проверки исследовательской витрины неисправности дымовых датчиков."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root=Path(__file__).resolve().parents[1]
    data=root/"production_ml"/"data"/"smoke_fault_v1"
    con=duckdb.connect()
    for name in ("events","clear_events","states","episodes","features","labels"):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(data/(name+'.parquet')).as_posix()}')")
    checks={
      "counts":"SELECT (SELECT count(*) FROM events) events,(SELECT count(*) FROM clear_events) clear_events,(SELECT count(*) FROM states) states,(SELECT count(*) FROM episodes) episodes,(SELECT count(*) FROM features) features,(SELECT count(*) FROM labels) labels",
      "duplicate_keys":"SELECT (SELECT count(*) FROM (SELECT channel_id,obs_time FROM features GROUP BY 1,2 HAVING count(*)>1)) feature_duplicates,(SELECT count(*) FROM (SELECT channel_id,obs_time FROM labels GROUP BY 1,2 HAVING count(*)>1)) label_duplicates",
      "time_conflicts":"WITH t AS (SELECT channel_id,event_time,bool_and(is_alarm) a,bool_or(is_alarm) b,count(*) n FROM events GROUP BY 1,2) SELECT count(*) FILTER(WHERE a!=b) conflicting_times,sum(n) FILTER(WHERE a!=b) removed_events FROM t",
      "feature_availability":"WITH h AS (SELECT channel_id,date_trunc('hour',event_time)+INTERVAL 1 HOUR obs_time,max(event_time) max_event,count(*) n FROM clear_events GROUP BY 1,2) SELECT count(*) FILTER(WHERE h.max_event>=h.obs_time) future_events,count(*) FILTER(WHERE h.n!=f.event_count_1h) count_mismatches,count(*) FILTER(WHERE observed_hours_72h NOT BETWEEN 1 AND 72) invalid_hours FROM h JOIN features f USING(channel_id,obs_time)",
      "episode_order":"WITH x AS (SELECT *,lead(episode_start) OVER(PARTITION BY channel_id ORDER BY episode_start) next_start FROM episodes) SELECT count(*) FILTER(WHERE recovery_time<=episode_start) bad_recovery,count(*) FILTER(WHERE next_start<recovery_time) overlap_n FROM x",
      "label_rules":"SELECT count(*) FILTER(WHERE NOT future_observed AND target_1_48h!=0) censored_with_target,count(*) FILTER(WHERE operational_eligible AND NOT future_observed) censored_rows,min(target_lead_hours) FILTER(WHERE target_1_48h=1) min_lead,max(target_lead_hours) FILTER(WHERE target_1_48h=1) max_lead FROM labels",
    }
    failures=[]
    zero={
      "duplicate_keys":("feature_duplicates","label_duplicates"),
      "feature_availability":("future_events","count_mismatches","invalid_hours"),
      "episode_order":("bad_recovery","overlap_n"),
      "label_rules":("censored_with_target",),
    }
    for name,sql in checks.items():
        r=con.execute(sql)
        fields=[d[0] for d in r.description]
        row=dict(zip(fields,r.fetchone()))
        print(json.dumps({"check":name,**row},ensure_ascii=False,default=str),flush=True)
        for field in zero.get(name,()):
            if row[field]!=0:
                failures.append(f"{name}.{field}={row[field]}")
    if failures:
        raise AssertionError("; ".join(failures))


if __name__=="__main__":
    main()
