"""Снимок покрытия всех каналов на указанное историческое время."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb

from production_ml.pipeline.sensor_coverage import assess_channel, describe_type


def quoted(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def build(catalog: Path, journals: list[Path], as_of: datetime, output: Path) -> None:
    if as_of.tzinfo is not None:
        raise ValueError("В исходном журнале время без часового пояса; as_of тоже должен быть без него")
    if not journals:
        raise ValueError("Нужен хотя бы один файл журнала")
    output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    temp = output / "duckdb_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory={quoted(temp)}")
    con.execute(f"CREATE TEMP TABLE catalog AS SELECT * FROM read_csv({quoted(catalog)},header=true)")
    duplicate_ids = con.execute("""
        SELECT count(*) FROM (SELECT "ид_канала_данных" FROM catalog
        GROUP BY 1 HAVING count(*)>1)
    """).fetchone()[0]
    if duplicate_ids:
        raise ValueError(f"В справочнике повторяются ID каналов: {duplicate_ids}")
    source = "[" + ",".join(quoted(path) for path in journals) + "]"
    con.execute(f"CREATE TEMP VIEW source_events AS SELECT * FROM read_parquet({source})")
    con.execute("""
        CREATE TEMP TABLE event_summary AS
        SELECT channel_id, count(*) event_count, min(event_time) first_event_time,
               max(event_time) last_event_time,
               arg_max(sensor_value, struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) last_recorded_value,
               arg_max(is_alarm, struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) last_recorded_is_alarm,
               count(*) FILTER(WHERE event_time > ? - INTERVAL 72 HOUR) events_72h,
               count(*) FILTER(WHERE event_time > ? - INTERVAL 30 DAY) events_30d,
               count(*) FILTER(WHERE event_time > ? - INTERVAL 30 DAY
                 AND isfinite(try_cast(replace(sensor_value,',','.') AS DOUBLE))) finite_numeric_events_30d
        FROM source_events WHERE event_time <= ? GROUP BY channel_id
    """, [as_of] * 4)
    con.execute("""
        CREATE TEMP TABLE conflicts AS
        SELECT channel_id,count(*) mixed_alarm_timestamps_72h FROM (
            SELECT channel_id,event_time
            FROM source_events
            WHERE event_time > ? - INTERVAL 72 HOUR AND event_time <= ?
            GROUP BY channel_id,event_time
            HAVING min(is_alarm) != max(is_alarm)
        ) GROUP BY channel_id
    """, [as_of, as_of])
    rows = con.execute("""
        SELECT coalesce(c."ид_канала_данных",e.channel_id) channel_id,
               c."тип_датчика" sensor_type,c."ид_объект" object_id,
               c."ид_канала_данных" IS NOT NULL in_catalog,
               e.event_count,e.first_event_time,e.last_event_time,
               e.last_recorded_value,e.last_recorded_is_alarm,
               e.events_72h,e.events_30d,e.finite_numeric_events_30d,
               coalesce(x.mixed_alarm_timestamps_72h,0) mixed_alarm_timestamps_72h
        FROM catalog c FULL OUTER JOIN event_summary e
          ON c."ид_канала_данных"=e.channel_id
        LEFT JOIN conflicts x ON x.channel_id=e.channel_id
        ORDER BY channel_id
    """).fetchall()
    columns = [item[0] for item in con.description]
    snapshot = [assess_channel(dict(zip(columns, row)), as_of) for row in rows]
    with (output / "channels.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(snapshot[0]))
        writer.writeheader()
        writer.writerows(snapshot)

    types = con.execute("SELECT \"тип_датчика\",count(*) FROM catalog GROUP BY 1 ORDER BY 1").fetchall()
    type_summary = []
    for sensor_type, catalog_channels in types:
        selected = [row for row in snapshot if row["sensor_type"] == sensor_type]
        type_summary.append({
            **describe_type(sensor_type),
            "catalog_channels": catalog_channels,
            "channels_with_history": sum(row["event_count"] > 0 for row in selected),
            "channels_with_events_72h": sum(row["events_72h"] > 0 for row in selected),
            "channels_with_mixed_alarm_72h": sum(row["mixed_alarm_timestamps_72h"] > 0 for row in selected),
            "recorded_events": sum(row["event_count"] for row in selected),
            "events_30d": sum(row["events_30d"] for row in selected),
            "finite_numeric_events_30d": sum(row["finite_numeric_events_30d"] for row in selected),
        })
    with (output / "types.json").open("w", encoding="utf-8") as file:
        json.dump({"schema_version": "sensor_coverage_v1", "as_of": as_of.isoformat(sep=" "),
                   "channels_without_catalog_metadata": sum(not row["in_catalog"] for row in snapshot),
                   "types": type_summary}, file, ensure_ascii=False, indent=2)
    object_types = {}
    for row in snapshot:
        if row["object_id"] is None:
            continue
        key = (row["object_id"], row["sensor_type"])
        summary = object_types.setdefault(key, {
            "object_id": row["object_id"], "sensor_type": row["sensor_type"],
            "catalog_channels": 0, "channels_with_history": 0,
            "channels_with_events_72h": 0, "channels_with_mixed_alarm_72h": 0,
            "active_model_type_channels": 0,
        })
        summary["catalog_channels"] += 1
        summary["channels_with_history"] += row["event_count"] > 0
        summary["channels_with_events_72h"] += row["events_72h"] > 0
        summary["channels_with_mixed_alarm_72h"] += row["mixed_alarm_timestamps_72h"] > 0
        summary["active_model_type_channels"] += row["forecast_capability"] == "active"
    with (output / "object_type_coverage.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(next(iter(object_types.values()))))
        writer.writeheader()
        writer.writerows(object_types[key] for key in sorted(object_types))
    result = {
        "as_of": as_of.isoformat(sep=" "), "catalog_channels": sum(n for _, n in types),
        "types": len(types), "snapshot_channels": len(snapshot),
        "missing_catalog": sum(not row["in_catalog"] for row in snapshot),
        "without_history": sum(row["event_count"] == 0 for row in snapshot),
        "no_events_72h": sum(row["event_count"] > 0 and row["events_72h"] == 0 for row in snapshot),
        "recent_conflicts": sum(row["mixed_alarm_timestamps_72h"] > 0 for row in snapshot),
        "active_model_type_channels": sum(row["forecast_capability"] == "active" for row in snapshot),
    }
    print(json.dumps(result, ensure_ascii=False))
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--journals", type=Path, nargs="+", required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    build(args.catalog, args.journals, args.as_of, args.output)


if __name__ == "__main__":
    main()
