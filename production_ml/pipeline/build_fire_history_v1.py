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
    con.execute(f"CREATE VIEW smoke AS SELECT * FROM read_parquet('{smoke.as_posix()}')")
    stats = con.execute("""
        SELECT year(event_time) yr,count(*) signal_records,
               count(DISTINCT channel_id) channels,count(DISTINCT object_id) objects,
               count(*) FILTER(WHERE recent_numeric_count>0) with_recent_temperature,
               count(*) FILTER(WHERE recent_numeric_count>0 AND baseline_numeric_count>0)
                   with_comparable_temperature
        FROM smoke GROUP BY 1 ORDER BY 1
    """)
    with (output / "smoke_signal_statistics.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([d[0] for d in stats.description])
        writer.writerows(stats.fetchall())
    manifest = {
        "version": "fire_history_v1",
        "confirmed_fire_register_available": False,
        "confirmed_fire_count": 0,
        "count_meaning": "0 подтверждённых записей в предоставленных данных; число реальных пожаров неизвестно",
        "telemetry_match_count": 0,
        "telemetry_match_meaning": "не вычисляется без подтверждённых записей с датой и местом",
        "smoke_statistics_are_fires": False,
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
