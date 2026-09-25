"""Синхронные исходные точки для исторической ситуации или черновика."""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb


def quote(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--situation-id")
    selector.add_argument("--draft-id")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parents[4]
                        / "dataset" / "справочник_каналов_датчиков.csv")
    parser.add_argument("--view-at", type=datetime.fromisoformat)
    parser.add_argument("--before-hours", type=int, default=2)
    parser.add_argument("--after-hours", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.before_hours<0 or args.after_hours<0:
        raise ValueError("Окна должны быть неотрицательными")
    for path in (args.catalog,args.root / "observed_v1" / "situations.parquet",
                 args.root / "observed_v1" / "evidence.parquet"):
        if not path.exists():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True,exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW catalog AS SELECT * FROM read_csv({quote(args.catalog)})")
    con.execute(f"CREATE VIEW situations AS SELECT * FROM read_parquet("
                f"{quote(args.root / 'observed_v1' / 'situations.parquet')})")
    con.execute(f"CREATE VIEW evidence AS SELECT * FROM read_parquet("
                f"{quote(args.root / 'observed_v1' / 'evidence.parquet')})")
    case_kind = "situation" if args.situation_id else "draft"
    if args.situation_id:
        rows = con.execute("SELECT situation_id,situation_kind,object_id,first_seen,"
                           "last_seen,location_key,limitations FROM situations "
                           "WHERE situation_id=?",[args.situation_id]).fetchall()
        if len(rows)!=1:
            raise ValueError("Ситуация не найдена или повторяется")
        case_id,kind,object_id,signal_time,last_seen,location_key,limitations = rows[0]
        channels = [row[0] for row in con.execute(
            "SELECT DISTINCT channel_id FROM evidence WHERE situation_id=?",
            [case_id]).fetchall()]
        related_reason = "source_situation_evidence"
        if kind.startswith("OBSERVED_SMOKE") and location_key and location_key.startswith("piket:"):
            piket = location_key.split(":",1)[1]
            related = con.execute("""
                SELECT "ид_канала_данных" FROM catalog
                WHERE "ид_объект"=? AND "тип_датчика"='Датчик температуры'
                  AND replace(regexp_extract("название_датчика",
                    '(?i)ПК\\s*([0-9]+(?:[.,][0-9]+)?)',1),',','.')=?
            """,[object_id,piket]).fetchall()
            channels += [row[0] for row in related]
            if related:
                related_reason += ";temperature_same_object_exact_piket_from_name"
        view_end = last_seen + timedelta(hours=args.after_hours)
    else:
        members = [args.root / "dispatch_review_v2" / period / "members.parquet"
                   for period in ("policy_2024","diagnostic_2025_2026")]
        for path in members:
            if not path.exists():
                raise FileNotFoundError(path)
        con.execute("CREATE VIEW members AS SELECT * FROM read_parquet(["
                    + ",".join(quote(path) for path in members) + "])")
        rows = con.execute("SELECT draft_id,group_id,object_id,obs_time,basis_kind,"
                           "target_kind,limitations FROM members WHERE draft_id=?",
                           [args.draft_id]).fetchall()
        if len(rows)!=1:
            raise ValueError("Черновик не найден или повторяется")
        case_id,group_id,object_id,signal_time,basis_kind,kind,limitations = rows[0]
        channels = [row[0] for row in con.execute(
            "SELECT DISTINCT channel_id FROM members WHERE group_id=?",[group_id]).fetchall()]
        related_reason = "channels_of_review_group"
        view_end = signal_time + timedelta(hours=args.after_hours)
        location_key = None
    channels = sorted(set(channels))
    if not channels:
        raise ValueError("Нет связанных исходных каналов")
    if args.view_at is not None and args.view_at.tzinfo is not None:
        raise ValueError("В журнале время без часового пояса")
    as_of = args.view_at or view_end
    if as_of<signal_time-timedelta(hours=args.before_hours):
        raise ValueError("Время просмотра раньше начала окна")
    start = signal_time-timedelta(hours=args.before_hours)
    end = min(view_end,as_of)
    journals = [args.root / "source_v2" / f"journal_{year}.parquet"
                for year in range(start.year,end.year+1)]
    for path in journals:
        if not path.exists():
            raise FileNotFoundError(path)
    con.execute("CREATE VIEW journal AS SELECT * FROM read_parquet(["
                + ",".join(quote(path) for path in journals) + "])")
    con.execute("CREATE TEMP TABLE selected_channels(channel_id BIGINT)")
    con.executemany("INSERT INTO selected_channels VALUES (?)",[(channel,) for channel in channels])
    con.execute("""
        CREATE TABLE points AS
        WITH raw AS (
            SELECT j.channel_id,c."ид_объект" object_id,
                   c."тип_датчика" sensor_type,c."название_датчика" channel_name,
                   j.event_time,j.event_id,j.sensor_value,j.is_alarm,
                   try_cast(replace(j.sensor_value,',','.') AS DOUBLE) parsed_numeric
            FROM journal j JOIN selected_channels ids USING(channel_id)
            JOIN catalog c ON j.channel_id=c."ид_канала_данных"
            WHERE j.event_time BETWEEN ? AND ? AND c."ид_объект"=?
        ), ordered AS (
            SELECT *,lag(event_time) OVER(PARTITION BY channel_id
                     ORDER BY event_time,event_id,sensor_value,is_alarm)
                     previous_event_time
            FROM raw
        )
        SELECT channel_id,object_id,sensor_type,channel_name,event_time,event_id,
               sensor_value,is_alarm,
               CASE WHEN isfinite(parsed_numeric) THEN parsed_numeric ELSE NULL END
                   numeric_value,
               CASE WHEN isfinite(parsed_numeric) THEN 'numeric' ELSE 'status' END
                   value_kind,
               previous_event_time,
               date_diff('second',previous_event_time,event_time)/3600.0 gap_hours,
               CASE WHEN event_time<=? THEN 'known_at_signal' ELSE 'later_history' END
                   time_relation,
               CASE WHEN sensor_type='Газовый датчик' THEN 'vol_percent_methane'
                    ELSE NULL END numeric_unit,
               CASE WHEN sensor_type='Газовый датчик' THEN 1.0 ELSE NULL END
                   stated_device_threshold,
               concat('source_v2/journal_',year(event_time)::VARCHAR,
                      '.parquet:channel_id+event_time+event_id+sensor_value+is_alarm')
                   source_ref
        FROM ordered
    """,[start,end,object_id,signal_time])
    con.execute(f"COPY points TO {quote(args.output / 'points.parquet')} "
                "(FORMAT PARQUET,COMPRESSION ZSTD)")
    inventory = con.execute("""
        SELECT ids.channel_id,c."тип_датчика" sensor_type,
               c."название_датчика" channel_name,
               count(p.event_time) plotted_records
        FROM selected_channels ids LEFT JOIN catalog c
          ON ids.channel_id=c."ид_канала_данных"
        LEFT JOIN points p ON ids.channel_id=p.channel_id
        GROUP BY 1,2,3 ORDER BY 1
    """).df()
    con.register("inventory_frame",inventory)
    con.execute(f"COPY inventory_frame TO {quote(args.output / 'channels.parquet')} "
                "(FORMAT PARQUET,COMPRESSION ZSTD)")
    count = con.execute("SELECT count(*) FROM points").fetchone()[0]
    meta = {
        "case_kind":case_kind,"case_id":case_id,"kind":kind,"object_id":object_id,
        "location_key":location_key,"signal_time":signal_time.isoformat(sep=" "),
        "window_start":start.isoformat(sep=" "),"window_end":end.isoformat(sep=" "),
        "view_at":as_of.isoformat(sep=" "),"records":count,"channels":len(channels),
        "related_channel_rule":related_reason,"limitations":limitations,
        "delivery_time_available":False,
        "plot_rule":"Plot raw points; do not connect across absent intervals or infer a heartbeat.",
        "fire_confirmation":"NO_CONFIRMED_FIRE_SOURCE" if kind.startswith("OBSERVED_SMOKE") else None,
        "maintenance_schedule_available":False,
    }
    (args.output / "case_meta.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"case_id":case_id,"points":count,"channels":len(channels),
                      "view_at":meta["view_at"]},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
