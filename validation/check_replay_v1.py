"""Сверка исторического потока с источником, пакетными карточками и повторами."""

import json
import subprocess
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.replay_cli_v1 import ReplaySession


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE / "production_ml" / "data"
SCENARIOS = json.loads((BASE / "production_ml" / "pipeline" /
                        "replay_scenarios_v1.json").read_text(encoding="utf-8"))
CON = duckdb.connect()


def quoted(path):
    return "'" + path.as_posix().replace("'", "''") + "'"


def scalar(query):
    return CON.execute(query).fetchone()[0]


def require(label, condition):
    if not condition:
        raise AssertionError(label)
    print("OK",label)


def source_union(name):
    paths = [ROOT / "dispatch_review_v2" / period / f"{name}.parquet"
             for period in ("policy_2024", "diagnostic_2025_2026")]
    return "read_parquet([" + ",".join(quoted(path) for path in paths) + "])"


def check_scenario(scenario):
    folder = ROOT / "replay_v1" / scenario["id"]
    timeline = f"read_parquet({quoted(folder / 'timeline.parquet')})"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    obj = scenario["object_id"]
    start = scenario["start"].replace("T"," ")
    end = scenario["end"].replace("T"," ")
    total = scalar(f"SELECT count(*) FROM {timeline}")
    require(f"{scenario['id']}: нумерация и время",
            scalar(f"SELECT count(*)=max(seq) AND min(seq)=1 AND "
                   f"count(*) FILTER(WHERE event_time<TIMESTAMP '{start}' "
                   f"OR event_time>=TIMESTAMP '{end}')=0 FROM {timeline}"))
    require(f"{scenario['id']}: число событий в манифесте",
            total == sum(manifest["event_counts"].values()))
    require(f"{scenario['id']}: нет выдуманных исторических решений и пожаров",
            not manifest["historical_feedback_available"] and
            not manifest["confirmed_fire_register_available"] and
            scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind IN "
                   "('historical_decision','confirmed_fire')") == 0)
    catalog = quoted(BASE.parent.parent / "dataset" / "справочник_каналов_датчиков.csv")
    years = range(int(scenario["start"][:4]),int(scenario["end"][:4])+1)
    journals = "read_parquet([" + ",".join(quoted(ROOT / "source_v2" /
                                                    f"journal_{year}.parquet")
                                             for year in years) + "])"
    reading_source = (f"SELECT j.event_id,j.channel_id,j.event_time,j.sensor_value,j.is_alarm "
                      f"FROM {journals} j JOIN read_csv({catalog}) c "
                      'ON j.channel_id=c."ид_канала_данных" '
                      f'WHERE c."ид_объект"={obj} '
                      f"AND j.event_time>=TIMESTAMP '{start}' "
                      f"AND j.event_time<TIMESTAMP '{end}'")
    reading_replay = (f"SELECT CAST(json_extract_string(payload,'$.event_id') AS BIGINT) event_id,"
                      "channel_id,event_time,json_extract_string(payload,'$.sensor_value') "
                      "sensor_value,CAST(json_extract_string(payload,'$.is_alarm') AS BOOLEAN) "
                      f"is_alarm FROM {timeline} WHERE event_kind='reading'")
    require(f"{scenario['id']}: исходные показания без потерь и добавлений",
            scalar(f"SELECT count(*) FROM (({reading_source}) EXCEPT ALL "
                   f"({reading_replay}))") == 0 and
            scalar(f"SELECT count(*) FROM (({reading_replay}) EXCEPT ALL "
                   f"({reading_source}))") == 0)
    members = source_union("members")
    ready = ("SELECT s.situation_id,greatest(s.last_seen,max(CASE WHEN "
             "e.evidence_kind='GAS_NUMERIC_HOURLY' THEN "
             "e.event_time+INTERVAL 1 HOUR ELSE e.event_time END))"
             "+INTERVAL 1 HOUR+INTERVAL 1 SECOND release_time FROM "
             f"read_parquet({quoted(ROOT / 'observed_v1' / 'situations.parquet')}) s "
             f"JOIN read_parquet({quoted(ROOT / 'observed_v1' / 'evidence.parquet')}) e "
             f"USING(situation_id) WHERE s.object_id={obj} "
             "GROUP BY s.situation_id,s.last_seen")
    source_drafts = (f"SELECT m.draft_id FROM {members} m "
                     f"LEFT JOIN ({ready}) r ON m.situation_id=r.situation_id "
                     f"WHERE m.object_id={obj} AND "
                     "(CASE WHEN m.basis_kind='observed_status' THEN r.release_time "
                     "ELSE m.obs_time END)"
                     f">=TIMESTAMP '{start}' AND "
                     "(CASE WHEN m.basis_kind='observed_status' THEN r.release_time "
                     "ELSE m.obs_time END)"
                     f"<TIMESTAMP '{end}'")
    replay_drafts = (f"SELECT source_id draft_id FROM {timeline} "
                     "WHERE event_kind='draft_created'")
    require(f"{scenario['id']}: черновики равны пакетной очереди",
            scalar(f"SELECT count(*) FROM (({source_drafts}) EXCEPT ALL "
                   f"({replay_drafts}))") == 0 and
            scalar(f"SELECT count(*) FROM (({replay_drafts}) EXCEPT ALL "
                   f"({source_drafts}))") == 0)
    situation_source = (f"SELECT situation_id FROM ({ready}) "
                        f"WHERE release_time>=TIMESTAMP '{start}' "
                        f"AND release_time<TIMESTAMP '{end}'")
    situation_replay = (f"SELECT source_id situation_id FROM {timeline} "
                        "WHERE event_kind='situation_ready'")
    require(f"{scenario['id']}: карточки равны пакетному расчёту",
            scalar(f"SELECT count(*) FROM (({situation_source}) EXCEPT ALL "
                   f"({situation_replay}))") == 0 and
            scalar(f"SELECT count(*) FROM (({situation_replay}) EXCEPT ALL "
                   f"({situation_source}))") == 0)
    require(f"{scenario['id']}: итог карточки после всех свидетельств и окна группировки",
            scalar(f"SELECT count(*) FROM {timeline} t JOIN "
                   f"read_parquet({quoted(ROOT / 'observed_v1' / 'evidence.parquet')}) e "
                   "ON t.source_id=e.situation_id "
                   "WHERE t.event_kind='situation_ready' AND "
                   "t.event_time<(CASE WHEN e.evidence_kind='GAS_NUMERIC_HOURLY' "
                   "THEN e.event_time+INTERVAL 2 HOUR+INTERVAL 1 SECOND "
                   "ELSE e.event_time+INTERVAL 1 HOUR+INTERVAL 1 SECOND END)") == 0)
    require(f"{scenario['id']}: наблюдаемый черновик после готовности карточки",
            scalar(f"SELECT count(*) FROM {timeline} d JOIN {members} m "
                   "ON d.source_id=m.draft_id JOIN "
                   f"{timeline} s ON s.source_id=m.situation_id "
                   "AND s.event_kind='situation_ready' "
                   "WHERE d.event_kind='draft_created' "
                   "AND m.basis_kind='observed_status' "
                   "AND d.event_time<s.event_time") == 0)
    require(f"{scenario['id']}: газовые часы доступны только после закрытия",
            scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='observed_signal' "
                   "AND json_extract_string(payload,'$.evidence_kind')="
                   "'GAS_NUMERIC_HOURLY' AND event_time<"
                   "CAST(json_extract_string(payload,'$.source_time') AS TIMESTAMP)"
                   "+INTERVAL 1 HOUR") == 0)
    if "expected_situations" in scenario:
        require(f"{scenario['id']}: заданное число ситуаций",
                scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='situation_ready'")
                == scenario["expected_situations"])
    if "expected_drafts" in scenario:
        require(f"{scenario['id']}: заданное число черновиков",
                scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='draft_created'")
                == scenario["expected_drafts"])
    if "expected_situation_id" in scenario:
        require(f"{scenario['id']}: ожидаемая карточка",
                scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='situation_ready' "
                       "AND source_id=?".replace("?", "'" +
                       scenario["expected_situation_id"].replace("'","''") + "'")) == 1)
    if "expected_group_id" in scenario:
        require(f"{scenario['id']}: группа из пакетного расчёта",
                scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='draft_created' "
                       "AND json_extract_string(payload,'$.group_id')='"+
                       scenario["expected_group_id"]+"'") == 31)
    if "expected_draft_id" in scenario:
        require(f"{scenario['id']}: ожидаемый наблюдаемый черновик",
                scalar(f"SELECT count(*) FROM {timeline} WHERE event_kind='draft_created' "
                       "AND source_id='"+scenario["expected_draft_id"]+"'") == 1)
    if "expected_coverage_channel_id" in scenario:
        channel = scenario["expected_coverage_channel_id"]
        require(f"{scenario['id']}: пауза и возвращение канала {channel}",
                scalar(f"SELECT count(*) FROM {timeline} WHERE channel_id={channel} "
                       "AND event_kind='coverage_lost'") == 1 and
                scalar(f"SELECT count(*) FROM {timeline} WHERE channel_id={channel} "
                       "AND event_kind='coverage_restored'") == 1)
    repeat = ROOT / "replay_v1" / ("repeat_" + scenario["id"])
    subprocess.run([sys.executable,str(BASE / "production_ml" / "pipeline" /
                                       "build_replay_v1.py"),"--object-id",str(obj),
                    "--start",scenario["start"],"--end",scenario["end"],
                    "--output",str(repeat)],check=True,capture_output=True)
    second = f"read_parquet({quoted(repeat / 'timeline.parquet')})"
    require(f"{scenario['id']}: повторный запуск совпал построчно",
            scalar(f"SELECT count(*) FROM ((SELECT * FROM {timeline}) EXCEPT ALL "
                   f"(SELECT * FROM {second}))") == 0 and
            scalar(f"SELECT count(*) FROM ((SELECT * FROM {second}) EXCEPT ALL "
                   f"(SELECT * FROM {timeline}))") == 0)
    print(f"Сценарий {scenario['id']}: {total} событий")


def check_player():
    folder = ROOT / "replay_v1" / "linked_drafts"
    player = ReplaySession(folder)
    first = player.next_batch()[0]
    require("переход к следующему событию", first["event_kind"]=="draft_created")
    draft = first["payload"]["draft_id"]
    try:
        player.decide(draft,"approved","demo")
    except ValueError:
        pass
    else:
        raise AssertionError("Решение стало доступно до появления черновика")
    player.move(first)
    snapshot = player.snapshot()
    require("срез показывает только уже прошедшие черновики и каналы",
            snapshot["drafts"]==1 and
            sum(snapshot["coverage"].values())==player.manifest["catalog_channels"])
    decision = player.decide(draft,"approved","ручная проверка в эмуляции")
    require("имитационное решение помечено отдельно от исторического",
            decision["kind"]=="SIMULATED_DISPATCHER_DECISION" and
            len(player.simulated_decisions)==1)
    player.seek(0)
    require("перемотка сбрасывает имитационные решения",
            player.cursor==0 and not player.simulated_decisions)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for scenario in SCENARIOS:
        check_scenario(scenario)
    check_player()


if __name__ == "__main__":
    main()
