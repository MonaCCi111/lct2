"""Сверить расчёт из ограниченной истории с исторической витриной."""

import json
import sys
from datetime import timedelta
from pathlib import Path

import duckdb

from production_ml.pipeline.smoke_live_evidence import build_signal_evidence


def rows_as_dicts(result):
    columns = [d[0] for d in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    evidence = root / "production_ml" / "data" / "smoke_evidence" / "signals.parquet"
    catalog = root / "dataset" / "справочник_каналов_датчиков.csv"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW evidence AS SELECT * FROM read_parquet('{evidence.as_posix()}')")
    con.execute(f"""
        CREATE VIEW temperature_locations AS
        SELECT "ид_канала_данных" channel_id,"ид_объект" object_id,
               replace(regexp_extract("название_датчика",
                   '(?i)ПК\\s*([0-9]+(?:[.,][0-9]+)?)',1),',','.') piket
        FROM read_csv('{catalog.as_posix()}',header=true)
        WHERE "тип_датчика"='Датчик температуры'
    """)
    cases = ((98194, "2025-09-09 14:14:33"),
             (212526, "2024-04-05 10:35:22"),
             (212285, "2025-10-29 00:24:16"))
    for channel_id, timestamp in cases:
        result = con.execute("SELECT * FROM evidence WHERE channel_id=? AND event_time=?",
                             [channel_id, timestamp])
        signals = rows_as_dicts(result)
        if len(signals) != 1:
            raise AssertionError((channel_id, timestamp, len(signals)))
        signal = signals[0]
        time = signal["event_time"]
        smoke = rows_as_dicts(con.execute("""
            SELECT channel_id,event_time,object_id,piket FROM evidence
            WHERE object_id=? AND event_time BETWEEN ? AND ?
        """, [signal["object_id"], time - timedelta(minutes=15), time]))
        journal = root / "production_ml" / "data" / "source_v2" / f"journal_{time.year}.parquet"
        temp = rows_as_dicts(con.execute(f"""
            SELECT j.channel_id,j.event_time,l.object_id,l.piket,
                   try_cast(replace(j.sensor_value,',','.') AS DOUBLE) numeric_value
            FROM read_parquet('{journal.as_posix()}') j
            JOIN temperature_locations l USING(channel_id)
            WHERE l.object_id=? AND l.piket=?
              AND j.event_time BETWEEN ? AND ?
        """, [signal["object_id"], signal["piket"], time - timedelta(hours=30), time]))
        actual = build_signal_evidence(signal, smoke, temp)
        mismatches = {key: [signal[key], value] for key, value in actual.items()
                      if signal[key] != value}
        print(json.dumps({"channel_id": channel_id, "event_time": timestamp,
                          "smoke_rows": len(smoke), "temperature_rows": len(temp),
                          "mismatches": mismatches}, ensure_ascii=False, default=str), flush=True)
        if mismatches:
            raise AssertionError(mismatches)


if __name__ == "__main__":
    main()
