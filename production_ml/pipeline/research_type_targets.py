"""Измерить источник и возможные цели неисправности по всем типам."""

import argparse
import json
import sys
from pathlib import Path

import duckdb


FAULT_STATUSES = (
    "Неисправен", "Отключено устройство", "Обесточен",
    "Батарея разряжена", "Много неисправных устройств",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "type_targets.json")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    source = args.source_root / "production_ml/data/source_v2"
    journals = [source / f"journal_{year}.parquet" for year in range(2019,2027)]
    catalog = args.source_root / "dataset/справочник_каналов_датчиков.csv"
    for path in [*journals,catalog]:
        if not path.exists():
            raise FileNotFoundError(path)
    files = "["+",".join("'"+path.as_posix()+"'" for path in journals)+"]"
    args.output.parent.mkdir(parents=True,exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads=6")
    con.execute("SET memory_limit='8GB'")
    temp = args.output.parent / "type_targets_temp"
    temp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory='{temp.as_posix()}'")
    con.execute(f"CREATE TEMP VIEW catalog AS SELECT * FROM read_csv('{catalog.as_posix()}',header=true)")
    con.execute(f"CREATE TEMP VIEW events AS SELECT * FROM read_parquet({files})")
    annual = con.execute("""
        SELECT c."тип_датчика",year(j.event_time),count(*),
               count(DISTINCT j.channel_id),count(*) FILTER(WHERE j.is_alarm),
               count(DISTINCT j.channel_id) FILTER(WHERE j.is_alarm)
        FROM events j JOIN catalog c ON j.channel_id=c."ид_канала_данных"
        GROUP BY 1,2 ORDER BY 1,2
    """).fetchall()
    faults = con.execute("""
        SELECT c."тип_датчика",year(j.event_time),
               CASE WHEN month(j.event_time)<=6 THEN 'H1' ELSE 'H2' END,
               j.sensor_value,count(*),count(DISTINCT j.channel_id),
               count(DISTINCT (j.channel_id,CAST(j.event_time AS DATE))),
               count(DISTINCT c."ид_объект")
        FROM events j JOIN catalog c ON j.channel_id=c."ид_канала_данных"
        WHERE j.is_alarm AND j.sensor_value IN (?,?,?,?,?)
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """, FAULT_STATUSES).fetchall()
    fault_totals = con.execute("""
        SELECT c."тип_датчика",year(j.event_time),
               CASE WHEN month(j.event_time)<=6 THEN 'H1' ELSE 'H2' END,
               count(*),count(DISTINCT j.channel_id),
               count(DISTINCT (j.channel_id,CAST(j.event_time AS DATE))),
               count(DISTINCT c."ид_объект")
        FROM events j JOIN catalog c ON j.channel_id=c."ид_канала_данных"
        WHERE j.is_alarm AND j.sensor_value IN (?,?,?,?,?)
        GROUP BY 1,2,3 ORDER BY 1,2,3
    """, FAULT_STATUSES).fetchall()
    statuses = con.execute("""
        SELECT c."тип_датчика",j.sensor_value,j.is_alarm,
               count(*),count(DISTINCT j.channel_id)
        FROM events j JOIN catalog c ON j.channel_id=c."ид_канала_данных"
        WHERE c."тип_датчика" NOT IN ('Газовый датчик','Датчик температуры')
          AND j.event_time>=TIMESTAMP '2022-01-01'
        GROUP BY 1,2,3
    """).fetchall()
    con.close()
    by_type = {}
    for typ,year,events,channels,alarms,alarm_channels in annual:
        entry = by_type.setdefault(typ, {"sensor_type":typ,"annual":[],"fault_totals":[],
                                         "fault_statuses":[],"top_statuses":[]})
        entry["annual"].append({"year":year,"events":events,"channels":channels,
                                "alarm_records":alarms,"alarm_channels":alarm_channels})
    for typ,year,half,status,records,channels,channel_days,objects in faults:
        by_type[typ]["fault_statuses"].append({
            "year":year,"half":half,"status":status,"records":records,
            "channels":channels,"channel_days":channel_days,"objects":objects,
        })
    for typ,year,half,records,channels,channel_days,objects in fault_totals:
        by_type[typ]["fault_totals"].append({
            "year":year,"half":half,"records":records,"channels":channels,
            "channel_days":channel_days,"objects":objects,
        })
    for typ in by_type:
        for alarm in (True,False):
            top = sorted((row for row in statuses if row[0]==typ and row[2]==alarm),
                         key=lambda row:row[3],reverse=True)[:8]
            by_type[typ]["top_statuses"].extend({
                "value":value,"is_alarm":flag,"records":n,"channels":channels,
            } for _,value,flag,n,channels in top)
    result = {"schema_version":"type_target_profile_v1",
              "fault_statuses_examined":FAULT_STATUSES,
              "types":[by_type[key] for key in sorted(by_type)]}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"types":len(by_type),"annual_rows":len(annual),
                      "fault_rows":len(faults),"fault_total_rows":len(fault_totals),
                      "status_rows":len(statuses),
                      "output":str(args.output)},ensure_ascii=False))


if __name__ == "__main__":
    main()
