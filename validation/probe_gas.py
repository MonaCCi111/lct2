"""Read-only probe of gas-channel values in the local journal files."""
import os
import sys
from pathlib import Path

import duckdb

source = Path(os.environ.get("LCT2_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
parquet = source / "ml_research" / "data" / "parquet_by_year"
channels = source / "dataset" / "справочник_каналов_датчиков.csv"
files = [str(parquet / f"journal_{year}.parquet") for year in (2019, 2020, 2022, 2023, 2024, 2025, 2026)]
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='4GB'")
con.execute(f"CREATE VIEW ch AS SELECT * FROM read_csv_auto('{channels.as_posix()}')")
sources = ",".join(f"'{Path(p).as_posix()}'" for p in files)
con.execute(f"CREATE VIEW gas_events AS SELECT j.*, try_cast(j.sensor_value AS DOUBLE) num_val FROM read_parquet([{sources}]) j JOIN ch c ON j.channel_id=c.\"ид_канала_данных\" WHERE lower(c.\"тип_датчика\") LIKE '%газ%'")
print("gas_channels", con.execute("SELECT count(*) FROM ch WHERE lower(\"тип_датчика\") LIKE '%газ%'").fetchone()[0])
print("summary", con.execute("SELECT count(*) n, count(DISTINCT channel_id) channels, count(num_val) numeric_values, count(*) FILTER(WHERE num_val>4) above_4, count(*) FILTER(WHERE is_alarm) alarms, min(num_val), max(num_val), quantile_cont(num_val, [0.5,0.9,0.99,0.999]) FROM gas_events").fetchone())
print("top_values", con.execute("SELECT sensor_value,count(*) n FROM gas_events GROUP BY 1 ORDER BY 2 DESC LIMIT 20").fetchall())
print("numeric_examples", con.execute("SELECT channel_id,event_time,sensor_value,is_alarm FROM gas_events WHERE num_val>4 ORDER BY event_time LIMIT 15").fetchall())
print("channels_above_4", con.execute("SELECT channel_id,count(*) n,min(num_val),max(num_val) FROM gas_events WHERE num_val>4 GROUP BY 1 ORDER BY 2 DESC LIMIT 20").fetchall())
