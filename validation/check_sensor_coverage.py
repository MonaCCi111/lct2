"""Сквозные сценарии нового канала, молчания, восстановления и конфликта."""

import csv
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import duckdb

from production_ml.pipeline.build_sensor_coverage import build


def read_snapshot(path: Path) -> dict:
    with (path / "channels.csv").open(encoding="utf-8-sig", newline="") as file:
        return {int(row["channel_id"]): row for row in csv.DictReader(file)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    local_data = Path("production_ml/data")
    with tempfile.TemporaryDirectory(prefix="coverage_check_", dir=local_data) as dirname:
        root = Path(dirname)
        catalog = root / "catalog.csv"
        with catalog.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["ид_канала_данных", "тип_датчика", "ид_объект"])
            writer.writerows([
                [900001, "Состояние фазы", 100],  # Новый ID, которого модель не видела.
                [900002, "Состояние фазы", 100],  # Канал без истории.
                [900003, "Датчик дыма", 100],
                [900004, "Новый тип датчика", 100],
            ])
        parquet = root / "journal.parquet"
        con = duckdb.connect()
        con.execute("""
            CREATE TABLE journal(event_id BIGINT,channel_id BIGINT,event_time TIMESTAMP,
                                 is_alarm BOOLEAN,sensor_value VARCHAR)
        """)
        con.executemany("INSERT INTO journal VALUES (?,?,?,?,?)", [
            (1, 900001, datetime(2024, 1, 1), False, "Норма"),
            (2, 900001, datetime(2024, 1, 5), False, "Норма"),
            (3, 900001, datetime(2024, 1, 5), True, "Обесточен"),
            (4, 900001, datetime(2024, 1, 6), False, "Норма"),
            (5, 900003, datetime(2024, 1, 5), True, "Обнаружен дым"),
            (6, 900004, datetime(2024, 1, 5), False, "X"),
            (7, 999999, datetime(2024, 1, 5), False, "X"),
        ])
        con.execute(f"COPY journal TO '{parquet.as_posix()}' (FORMAT PARQUET)")
        con.close()

        before = root / "before"
        build(catalog, [parquet], datetime(2024, 1, 1), before)
        a = read_snapshot(before)
        assert a[900001]["observation_state"] == "recent_events"
        assert a[900001]["recent_input_context"] == "limited_72h_history"
        assert a[900001]["event_count"] == "1"  # Будущее не прочитано.
        assert a[900002]["observation_state"] == "no_historical_events"

        conflict = root / "conflict"
        build(catalog, [parquet], datetime(2024, 1, 5, 12), conflict)
        b = read_snapshot(conflict)
        assert b[900001]["observation_state"] == "recent_conflicting_events"
        assert b[900001]["recent_input_context"] == "conflicting_recent_events"
        assert b[900003]["forecast_capability"] == "not_released"
        assert b[900004]["forecast_capability"] == "not_assessed"
        assert b[999999]["in_catalog"] == "False"
        assert b[999999]["observation_state"] == "recent_events"

        after = root / "after"
        build(catalog, [parquet], datetime(2024, 1, 8, 1), after)
        c = read_snapshot(after)
        assert c[900001]["observation_state"] == "recent_events"
        assert c[900001]["recent_input_context"] == "recent_input_present"

        silent = root / "silent"
        build(catalog, [parquet], datetime(2024, 1, 10), silent)
        d = read_snapshot(silent)
        assert d[900001]["observation_state"] == "no_recent_events"
        assert d[900001]["recent_input_context"] == "no_recent_events"
        assert d[900001]["last_event_time"] == "2024-01-06 00:00:00"
        print("Сквозные сценарии пройдены: новый канал, пустая история, ограниченная история, конфликт, восстановление, молчание, неизвестный тип и ID, отсутствие будущего.")


if __name__ == "__main__":
    main()
