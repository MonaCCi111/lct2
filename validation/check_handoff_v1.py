"""Сквозная сверка ML/data-выпуска для продуктовых команд."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.delivery_audit_v1 import audit_deliveries


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE / "production_ml" / "data"
HANDOFF = ROOT / "handoff_v1"
CON = duckdb.connect()


def q(path):
    return "'" + path.as_posix().replace("'", "''") + "'"


def table(name):
    return f"read_parquet({q(HANDOFF / (name + '.parquet'))})"


def scalar(sql):
    return CON.execute(sql).fetchone()[0]


def check(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: {actual} != {expected}")
    print(f"OK {label}: {actual}")


def source_union(name):
    files = [ROOT / "dispatch_review_v2" / period / f"{name}.parquet"
             for period in ("policy_2024", "diagnostic_2025_2026")]
    return "read_parquet([" + ",".join(q(path) for path in files) + "])"


def verify_manifest():
    manifest = json.loads((HANDOFF / "schema_manifest.json").read_text(encoding="utf-8"))
    check("версия схемы",manifest["schema_version"],"ml_handoff_v1")
    check("число ресурсов",len(manifest["resources"]),14)
    for name,relative in manifest["json_resources"].items():
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"JSON ресурс отсутствует: {name}: {path}")
    for name,item in manifest["resources"].items():
        path = ROOT / item["path"]
        if not path.is_file():
            raise AssertionError(f"Ресурс отсутствует: {path}")
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        if value != item["sha256"]:
            raise AssertionError(f"Контрольная сумма не совпадает: {name}")
        relation = f"read_parquet({q(path)})"
        check(f"{name}: число строк",scalar(f"SELECT count(*) FROM {relation}"),item["rows"])
        fields = CON.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        if [(row[0],row[1],row[2]=="YES") for row in fields] != [
                (field["name"],field["type"],field["nullable"])
                for field in item["fields"]]:
            raise AssertionError(f"Схема не совпадает: {name}")
        if item["key"]:
            columns = ",".join(item["key"])
            duplicate = scalar(f"SELECT count(*)-count(DISTINCT ({columns})) FROM {relation}")
            check(f"{name}: повтор ключа",duplicate,0)
    return manifest


def verify_relations():
    channels = table("channel_current")
    snapshots = table("observation_snapshots")
    situations = table("situation_cards")
    evidence = table("situation_evidence")
    drafts = table("draft_cards")
    groups = table("group_cards")
    check("каналы",scalar(f"SELECT count(*) FROM {channels}"),12627)
    check("каналы без справочника",scalar(f"SELECT count(*) FROM {channels} "
                                       "WHERE NOT in_catalog"),1142)
    check("помесячные снимки",scalar(f"SELECT count(*) FROM {snapshots}"),378810)
    check("будущее в первом известном событии",
          scalar(f"SELECT count(*) FROM {snapshots} WHERE first_known_event_time>available_at"),0)
    check("будущее в последнем событии",
          scalar(f"SELECT count(*) FROM {snapshots} WHERE last_event_time>available_at"),0)
    check("выдуманные числовые ИТС",scalar(f"SELECT count(*) FROM {snapshots} "
                                          "WHERE its_value IS NOT NULL"),0)
    check("неизвестное состояние справочника",scalar(f"SELECT count(*) FROM {snapshots} "
          "WHERE dictionary_state NOT IN ('no_text_status','not_listed_for_type',"
          "'dictionary_conflict','source_dictionary_disagreement',"
          "'listed_consistently')"),0)
    dictionary = table("state_dictionary")
    check("строки справочника состояний",scalar(f"SELECT count(*) FROM {dictionary}"),62)
    check("неоднозначные тип и текст в справочнике",
          scalar(f"SELECT count(*) FROM (SELECT sensor_type,state_text FROM {dictionary} "
                 "GROUP BY 1,2 HAVING count(DISTINCT dictionary_alarm)>1)"),1)
    check("ситуации",scalar(f"SELECT count(*) FROM {situations}"),11704)
    check("свидетельства",scalar(f"SELECT count(*) FROM {evidence}"),120593)
    check("свидетельства без ситуации",scalar(f"SELECT count(*) FROM {evidence} e "
          f"LEFT JOIN {situations} s USING(situation_id) WHERE s.situation_id IS NULL"),0)
    check("свидетельства после карточки",scalar(f"SELECT count(*) FROM {evidence} e "
          f"JOIN {situations} s USING(situation_id) WHERE e.available_at>s.available_at"),0)
    check("газовый час раньше его закрытия",scalar(f"SELECT count(*) FROM {evidence} "
          "WHERE evidence_kind='GAS_NUMERIC_HOURLY' "
          "AND available_at<source_time+INTERVAL 1 HOUR"),0)
    check("все физические инциденты не подтверждены",scalar(f"SELECT count(*) FROM {situations} "
          "WHERE confirmed_physical_incident IS NOT NULL"),0)
    check("черновики",scalar(f"SELECT count(*) FROM {drafts}"),2191)
    check("группы",scalar(f"SELECT count(*) FROM {groups}"),1621)
    check("черновики без группы",scalar(f"SELECT count(*) FROM {drafts} d "
          f"LEFT JOIN {groups} g USING(group_id) WHERE g.group_id IS NULL"),0)
    check("группа до последнего черновика",scalar(f"SELECT count(*) FROM {drafts} d "
          f"JOIN {groups} g USING(group_id) WHERE d.available_at>g.available_at"),0)
    check("наблюдаемый черновик раньше ситуации",scalar(f"SELECT count(*) FROM {drafts} d "
          f"JOIN {situations} s USING(situation_id) WHERE d.basis_kind='observed_status' "
          "AND d.available_at<s.available_at"),0)
    check("прогнозный черновик не в своё время",scalar(f"SELECT count(*) FROM {drafts} "
          "WHERE basis_kind='forecast' AND available_at!=source_obs_time"),0)
    check("другие модельные версии в рабочем прогнозе",scalar(f"SELECT count(*) FROM {drafts} "
          "WHERE basis_kind='forecast' AND model_version NOT IN "
          "('power_phase_scada_v2','pump_scada_v1')"),0)
    check("число черновиков по группам",scalar(f"SELECT sum(draft_count) FROM {groups}"),2191)
    check("счётчик обзора и карточки",scalar(f"SELECT sum(draft_count) FROM "
          f"read_parquet({q(ROOT / 'visualization_v1' / 'object_day.parquet')})"),2191)
    check("число ситуаций в обзоре",scalar(f"SELECT sum(observed_situations) FROM "
          f"read_parquet({q(ROOT / 'visualization_v1' / 'object_day.parquet')})"),11704)
    chart = table("chart_examples")
    check("примерные графические точки",scalar(f"SELECT count(*) FROM {chart}"),977)
    check("будущие точки в примерах",scalar(f"SELECT count(*) FROM {chart} "
          "WHERE event_time>view_at"),0)
    fire = json.loads((HANDOFF / "fire_history_view.json").read_text(encoding="utf-8"))
    feedback = json.loads((HANDOFF / "feedback_availability.json").read_text(encoding="utf-8"))
    check("реальное число пожаров",fire["real_fire_count"],None)
    check("дым не равен пожару",fire["smoke_signal_statistics_are_fires"],False)
    check("реальные решения",feedback["decision_counts"],None)
    check("причины отклонения",feedback["rejection_reasons"],None)
    source_members = source_union("members")
    check("сверка ID черновиков с источником",scalar(f"SELECT count(*) FROM "
          f"((SELECT draft_id FROM {drafts}) EXCEPT ALL "
          f"(SELECT draft_id FROM {source_members}))"),0)


def verify_edge_cases():
    subprocess.run([sys.executable,"-m","validation.check_sensor_coverage"],
                   cwd=BASE,check=True,capture_output=True)
    print("OK новый канал, неизвестный тип, пустая история и восстановление")
    empty = ROOT / "handoff_v1" / "empty_period_probe"
    subprocess.run([sys.executable,str(BASE / "production_ml" / "pipeline" /
                                       "build_replay_v1.py"),
                    "--object-id","5113","--start","2026-07-10T00:00:00",
                    "--end","2026-07-10T01:00:00","--output",str(empty)],
                   cwd=BASE,check=True,capture_output=True)
    relation = f"read_parquet({q(empty / 'timeline.parquet')})"
    check("пустой период без выдуманных событий",scalar(f"SELECT count(*) FROM {relation} "
          "WHERE event_kind!='coverage_baseline'"),0)
    rows = [
        {"event_id":1,"channel_id":100,"event_time":"2025-01-01 10:00:00",
         "sensor_value":"Норма","is_alarm":False},
        {"event_id":1,"channel_id":100,"event_time":"2025-01-01 10:00:00",
         "sensor_value":"Норма","is_alarm":False},
        {"event_id":1,"channel_id":100,"event_time":"2025-01-01 09:00:00",
         "sensor_value":"Обесточен","is_alarm":True},
        {"event_id":1,"channel_id":100,"event_time":"2025-01-01 09:00:00",
         "sensor_value":"Норма","is_alarm":False},
    ]
    audit = audit_deliveries(rows)
    check("повторная доставка одной и той же строки",len(audit["duplicate"]),1)
    check("разное содержимое одного event_id сохранено",len(audit["accepted"]),3)
    check("поздние записи отмечены для перерасчёта",len(audit["late"]),2)
    check("коллизии event_id измерены",len(audit["reused_event_id"]),2)
    check("повторное применение не добавляет записей",
          len(audit_deliveries(rows+rows)["accepted"]),3)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    verify_manifest()
    verify_relations()
    verify_edge_cases()


if __name__ == "__main__":
    main()
