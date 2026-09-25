"""Проверить историю наблюдения, отсутствие выдуманного ИТС и края входа."""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb
import pandas as pd


def check_real():
    root = Path(__file__).resolve().parents[1]
    folder = root / "production_ml" / "data" / "its_evidence_v1"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW h AS SELECT * FROM read_parquet('{(folder / 'channel_history.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW o AS SELECT * FROM read_parquet('{(folder / 'object_type_history.parquet').as_posix()}')")
    result = con.execute("""
        SELECT count(*) channel_rows,count(DISTINCT (channel_id,snapshot_date)) unique_keys,
               count(*) FILTER(WHERE its_value IS NOT NULL OR its_status!='unavailable')
                   invented_scores,
               count(*) FILTER(WHERE last_event_time>as_of OR last_text_time>as_of)
                   future_events,
               count(*) FILTER(WHERE observation_state='recent_observation'
                   AND (last_event_time IS NULL OR last_event_time<=as_of-INTERVAL 72 HOUR
                   OR conflicting_status_keys_72h>0)) wrong_recent,
               count(*) FILTER(WHERE observation_state='no_recent_observation'
                   AND (last_event_time IS NULL OR last_event_time>as_of-INTERVAL 72 HOUR))
                   wrong_silent,
               count(*) FILTER(WHERE observation_state='conflicting_recent_status_flag'
                   AND conflicting_status_keys_72h=0) wrong_conflict,
               count(*) FILTER(WHERE observation_state='ambiguous_simultaneous_statuses'
                   AND (mixed_alarm_timestamps_72h=0 OR conflicting_status_keys_72h>0))
                   wrong_ambiguous,
               count(*) FILTER(WHERE observation_state='new_or_never_observed'
                   AND first_event_time IS NOT NULL AND first_event_time<=as_of)
                   wrong_new,
               count(*) FILTER(WHERE observation_state='metadata_missing'
                   AND in_catalog) wrong_metadata,
               count(*) FILTER(WHERE dictionary_state='dictionary_conflict'
                   AND coalesce(alarm_variants,0)<=1) wrong_dictionary,
               count(*) FILTER(WHERE last_text_time IS NOT NULL) with_text_status,
               count(*) FILTER(WHERE dictionary_state='listed_consistently')
                   listed_text_status,
               count(DISTINCT snapshot_date) month_count,
               count(DISTINCT channel_id) channels
        FROM h
    """)
    facts = dict(zip([x[0] for x in result.description],result.fetchone()))
    result = con.execute("""
        SELECT count(*) object_type_rows,
               count(*) FILTER(WHERE its_value IS NOT NULL) invented_object_scores,
               count(*) FILTER(WHERE catalog_channels<=0 OR
                 recently_observed_channels+no_recent_observation_channels+
                 conflicting_channels+ambiguous_simultaneous_channels>
                 catalog_channels) impossible_counts
        FROM o
    """)
    facts.update(dict(zip([x[0] for x in result.description],result.fetchone())))
    print(json.dumps({"real_history": facts},ensure_ascii=False),flush=True)
    if (facts["channel_rows"]!=facts["unique_keys"] or
        facts["channel_rows"]!=facts["channels"]*facts["month_count"] or
        facts["with_text_status"]==0 or facts["listed_text_status"]==0 or
        any(facts[key] for key in (
            "invented_scores","future_events","wrong_recent","wrong_silent",
            "wrong_conflict","wrong_ambiguous","wrong_new","wrong_metadata",
            "wrong_dictionary",
            "invented_object_scores","impossible_counts"))):
        raise AssertionError(facts)
    context = folder / "draft_context.parquet"
    first = root / "production_ml" / "data" / "dispatch_review_v2" / "policy_2024" / "members.parquet"
    second = root / "production_ml" / "data" / "dispatch_review_v2" / "diagnostic_2025_2026" / "members.parquet"
    result = con.execute(f"""
        WITH source AS (SELECT * FROM read_parquet(
            ['{first.as_posix()}','{second.as_posix()}'])),
        context AS (SELECT * FROM read_parquet('{context.as_posix()}'))
        SELECT (SELECT count(*) FROM source) source_drafts,
               (SELECT count(*) FROM context) context_drafts,
               (SELECT count(*)-count(DISTINCT draft_id) FROM context) duplicate_drafts,
               (SELECT count(*) FROM source s LEFT JOIN context c USING(draft_id)
                WHERE c.draft_id IS NULL) lost_drafts,
               (SELECT count(*) FROM context WHERE last_event_time>obs_time)
                future_context,
               (SELECT count(*) FROM context WHERE its_value IS NOT NULL)
                invented_context_scores,
               (SELECT count(*) FROM context WHERE event_count_72h=0)
                without_recent_events
    """)
    draft_facts = dict(zip([x[0] for x in result.description],result.fetchone()))
    print(json.dumps({"draft_context":draft_facts},ensure_ascii=False),flush=True)
    if (draft_facts["source_drafts"]!=draft_facts["context_drafts"] or
        any(draft_facts[key] for key in (
            "duplicate_drafts","lost_drafts","future_context",
            "invented_context_scores"))):
        raise AssertionError(draft_facts)


def synthetic():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        catalog = folder / "catalog.csv"
        with catalog.open("w",encoding="utf-8",newline="") as handle:
            writer = csv.DictWriter(handle,fieldnames=[
                "ид_канала_данных","тип_датчика","ид_объект","название_датчика"])
            writer.writeheader()
            for channel_id in (1,2,3,5,6,7):
                writer.writerow({"ид_канала_данных":channel_id,
                                 "тип_датчика":"Состояние насоса","ид_объект":100,
                                 "название_датчика":f"Проверка {channel_id}"})
        states = folder / "states.csv"
        with states.open("w",encoding="utf-8",newline="") as handle:
            writer = csv.DictWriter(handle,fieldnames=[
                "тип_датчика","ид_набор_состояний","название_состояния","тревожное"])
            writer.writeheader()
            writer.writerow({"тип_датчика":"Состояние насоса","ид_набор_состояний":1,
                             "название_состояния":"Норма","тревожное":"false"})
            writer.writerow({"тип_датчика":"Состояние насоса","ид_набор_состояний":2,
                             "название_состояния":"Норма","тревожное":"true"})
        data = pd.DataFrame([
            (1,1,"2024-01-30 12:00:00",True,"Неисправен"),
            (2,3,"2024-01-31 10:00:00",False,"Норма"),
            (3,3,"2024-01-31 10:00:00",True,"Норма"),
            (4,4,"2024-01-31 10:00:00",False,"Норма"),
            (5,5,"2024-01-01 10:00:00",False,"Норма"),
            (6,6,"2024-01-31 11:00:00",False,"Не определено"),
            (7,7,"2024-01-31 12:00:00",False,"Норма"),
            (8,7,"2024-01-31 12:00:00",True,"Неисправен"),
        ],columns=["event_id","channel_id","event_time","is_alarm","sensor_value"])
        data["event_time"] = pd.to_datetime(data["event_time"])
        journals = folder / "journals"
        journals.mkdir()
        con = duckdb.connect()
        con.register("events",data)
        con.execute(f"COPY events TO '{(journals / 'journal_2024.parquet').as_posix()}' "
                    "(FORMAT PARQUET)")
        output = folder / "output"
        command = [sys.executable,"-m","production_ml.pipeline.build_its_evidence_v1",
                   "--catalog",str(catalog),"--states",str(states),"--journals",str(journals),
                   "--first-month","2024-01-01","--last-month","2024-01-01",
                   "--output",str(output)]
        subprocess.run(command,cwd=root,check=True,capture_output=True,text=True)
        frame = con.execute(f"SELECT channel_id,observation_state,its_value,its_status,"
                            f"fault_reports_72h,service_reports_72h,"
                            f"last_text_time IS NOT NULL,dictionary_state FROM read_parquet("
                            f"'{(output / 'channel_history.parquet').as_posix()}') "
                            "ORDER BY channel_id").fetchall()
        expected = [
            (1,"recent_observation",None,"unavailable",1,0,True,"not_listed_for_type"),
            (2,"new_or_never_observed",None,"unavailable",0,0,False,"no_text_status"),
            (3,"conflicting_recent_status_flag",None,"unavailable",0,0,True,"dictionary_conflict"),
            (4,"metadata_missing",None,"unavailable",0,0,True,"not_listed_for_type"),
            (5,"no_recent_observation",None,"unavailable",0,0,True,"dictionary_conflict"),
            (6,"recent_observation",None,"unavailable",0,1,True,"not_listed_for_type"),
            (7,"ambiguous_simultaneous_statuses",None,"unavailable",1,0,True,
             "not_listed_for_type"),
        ]
        if frame!=expected:
            raise AssertionError({"actual":frame,"expected":expected})
    print(json.dumps({"synthetic_new_silent_conflict": "passed"},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    check_real()
    synthetic()
