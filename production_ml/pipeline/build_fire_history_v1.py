"""Подготовить пустой подтверждённый реестр и отдельную статистику дыма."""

import argparse
import csv
import json
import sys
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--source-directory", type=Path,
                        default=Path(__file__).resolve().parents[4] / "dataset")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    output = args.data_root / "observed_v1"
    output.mkdir(parents=True, exist_ok=True)
    smoke = args.data_root / "smoke_evidence" / "signals.parquet"
    if not smoke.exists():
        raise FileNotFoundError(smoke)
    # Явный список организаторских файлов. Журналы датчиков не являются реестром пожаров.
    source_names = sorted(p.name for p in args.source_directory.iterdir() if p.is_file())
    fire_source_candidates = [name for name in source_names
                              if "пожар" in name.lower() or "fire" in name.lower()]
    if fire_source_candidates:
        raise RuntimeError("Найден потенциальный источник пожаров: требуется ручная проверка "
                           + ", ".join(fire_source_candidates))
    with (output / "confirmed_fires.csv").open("w", encoding="utf-8", newline="") as file:
        csv.writer(file).writerow(["fire_id", "occurred_at", "object_id", "location",
                                   "source_title", "source_reference", "source_verified",
                                   "telemetry_match_quality"])
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute(f"CREATE VIEW smoke AS SELECT * FROM read_parquet('{smoke.as_posix()}')")
    stats = con.execute("""
        SELECT year(event_time) yr,count(*) signal_records,
               count(DISTINCT channel_id) channels,count(DISTINCT object_id) objects,
               count(*) FILTER(WHERE mixed_alarm_flags_at_time) with_other_status_same_time,
               count(*) FILTER(WHERE recent_numeric_count>0) with_recent_temperature,
               count(*) FILTER(WHERE recent_numeric_count>0 AND baseline_numeric_count>0)
                   with_comparable_temperature
        FROM smoke GROUP BY 1 ORDER BY 1
    """)
    with (output / "smoke_signal_statistics.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([d[0] for d in stats.description])
        writer.writerows(stats.fetchall())
    catalog = args.source_directory / "справочник_каналов_датчиков.csv"
    journals = args.data_root / "source_v2" / "journal_20??.parquet"
    cards = args.data_root / "smoke_evidence" / "cards.parquet"
    for path in (catalog, cards):
        if not path.exists():
            raise FileNotFoundError(path)
    con.execute(f"CREATE VIEW smoke_cards AS SELECT * FROM read_parquet('{cards.as_posix()}')")
    con.execute(f"""
        CREATE TABLE hot_temperature AS
        SELECT j.event_id,j.channel_id,c."ид_объект" object_id,
               replace(regexp_extract(c."название_датчика",
                   '(?i)ПК\\s*([0-9]+(?:[.,][0-9]+)?)',1),',','.') piket,
               j.event_time,try_cast(replace(j.sensor_value,',','.') AS DOUBLE) numeric_value
        FROM read_parquet('{journals.as_posix()}') j
        JOIN read_csv('{catalog.as_posix()}') c
          ON j.channel_id=c."ид_канала_данных"
        WHERE c."тип_датчика"='Датчик температуры'
          AND try_cast(replace(j.sensor_value,',','.') AS DOUBLE)>=40;

        CREATE TABLE hot_temperature_statuses AS
        SELECT j.channel_id,j.event_time,
               string_agg(DISTINCT j.sensor_value,' | ') textual_statuses
        FROM read_parquet('{journals.as_posix()}') j
        JOIN (SELECT DISTINCT channel_id,event_time FROM hot_temperature) t
          USING(channel_id,event_time)
        WHERE try_cast(replace(j.sensor_value,',','.') AS DOUBLE) IS NULL
        GROUP BY 1,2;

        CREATE TABLE candidate_matches AS
        SELECT concat('SMOKE_TEMP:',card.card_id) candidate_id,
               s.object_id,s.piket,s.channel_id smoke_channel_id,
               s.event_time smoke_time,s.mixed_alarm_flags_at_time smoke_mixed_status,
               t.event_id temperature_event_id,t.channel_id temperature_channel_id,
               t.event_time temperature_time,t.numeric_value temperature_numeric,
               coalesce(q.textual_statuses,'') temperature_statuses_same_time
        FROM smoke s JOIN smoke_cards card
          ON s.object_id=card.object_id AND s.piket=card.piket
         AND s.event_time BETWEEN card.first_signal_time AND card.last_signal_time
        JOIN hot_temperature t
          ON s.object_id=t.object_id AND s.piket=t.piket AND s.piket!=''
         AND t.event_time BETWEEN s.event_time-INTERVAL 2 HOUR
                              AND s.event_time+INTERVAL 2 HOUR
        LEFT JOIN hot_temperature_statuses q
          ON t.channel_id=q.channel_id AND t.event_time=q.event_time;

        CREATE TABLE candidate_summary AS
        SELECT candidate_id,object_id,piket,min(smoke_time) first_smoke_time,
               min(temperature_time) first_temperature_time,
               count(DISTINCT smoke_channel_id) smoke_channels,
               count(DISTINCT temperature_channel_id) temperature_channels,
               max(temperature_numeric) maximum_numeric_temperature,
               bool_or(smoke_mixed_status) any_smoke_mixed_status,
               bool_or(contains(temperature_statuses_same_time,'Не определено'))
                   any_temperature_undefined_status,
               'UNCONFIRMED_TELEMETRY_COINCIDENCE' evidence_state
        FROM candidate_matches GROUP BY 1,2,3;
    """)
    for table, name in (("candidate_matches", "smoke_temperature_matches.csv"),
                        ("candidate_summary", "smoke_temperature_candidates.csv")):
        con.execute(f"COPY {table} TO '{(output / name).as_posix()}' (HEADER,DELIMITER ',')")
    candidate_count = con.execute("SELECT count(*) FROM candidate_summary").fetchone()[0]
    manifest = {
        "version": "fire_history_v1",
        "confirmed_fire_register_available": False,
        "confirmed_fire_count": 0,
        "count_meaning": "0 подтверждённых записей в предоставленных данных; число реальных пожаров неизвестно",
        "telemetry_match_count": 0,
        "telemetry_match_meaning": "не вычисляется без подтверждённых записей с датой и местом",
        "smoke_statistics_are_fires": False,
        "telemetry_candidate_count": candidate_count,
        "candidate_meaning": "дымовое сообщение и числовая температура >=40 при совпадении объекта и пикета в пределах двух часов; физический пожар не подтверждён",
        "candidate_file": "smoke_temperature_candidates.csv",
        "candidate_evidence_file": "smoke_temperature_matches.csv",
        "display_state": "NO_CONFIRMED_FIRE_SOURCE",
        "confirmed_fire_file": "confirmed_fires.csv",
        "separate_smoke_file": "smoke_signal_statistics.csv",
        "inspected_source_directory": str(args.source_directory),
    }
    (output / "fire_history_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
