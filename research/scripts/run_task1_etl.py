import os
import re
import time
import json
import duckdb
import pandas as pd
import numpy as np

start_total = time.time()

print("=" * 60)
print("ЗАДАЧА 1: ETL И FEATURE STORE (2019–2026, 313.5 МЛН СТРОК)")
print("=" * 60)

parquet_dir = r"g:\lct2\ml_research\data\parquet_by_year"
temp_dir = r"g:\lct2\ml_research\data\duckdb_temp"
os.makedirs(parquet_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

con = duckdb.connect()
con.execute("PRAGMA threads=12")
con.execute("PRAGMA memory_limit='16GB'")
con.execute(f"PRAGMA temp_directory='{temp_dir.replace(chr(92), '/')}'")

years = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
converted_files = []
parquet_stats = {}

# 1. Пофайловая конвертация CSV -> Parquet (ZSTD) с all_varchar=true для надежности
for y in years:
    csv_path = f"g:/lct2/dataset/ext-journal-{y}.csv"
    p_path = f"{parquet_dir}/journal_{y}.parquet".replace("\\", "/")
    
    if os.path.exists(csv_path):
        if os.path.exists(p_path) and os.path.getsize(p_path) > 10 * 1024 * 1024:
            row_cnt = con.execute(f"SELECT count(*) FROM read_parquet('{p_path}')").fetchone()[0]
            size_mb = round(os.path.getsize(p_path) / (1024 * 1024), 2)
            print(f"[Пропуск] Год {y} уже сконвертирован: {row_cnt:,} строк ({size_mb} МБ)")
            converted_files.append(p_path)
            parquet_stats[y] = {"rows": row_cnt, "parquet_size_mb": size_mb, "elapsed_sec": 0.0}
            continue

        print(f"\n[Конвертация] Обработка года {y}...")
        t0 = time.time()
        
        query = f"""
        COPY (
            SELECT 
                TRY_CAST(ид_события AS BIGINT) AS event_id,
                TRY_CAST(ид_канала_данных AS BIGINT) AS channel_id,
                TRY_CAST(дата || ' ' || время AS TIMESTAMP) AS event_time,
                CASE 
                    WHEN lower(trim(CAST(тревожное AS VARCHAR))) IN ('true', 't', '1') THEN TRUE 
                    ELSE FALSE 
                END AS is_alarm,
                CAST(значение_датчика AS VARCHAR) AS sensor_value
            FROM read_csv_auto('{csv_path}', all_varchar=true)
            WHERE дата != 'дата' 
              AND дата != '1970-01-01'
              AND TRY_CAST(ид_события AS BIGINT) IS NOT NULL
              AND TRY_CAST(ид_канала_данных AS BIGINT) IS NOT NULL
              AND TRY_CAST(дата || ' ' || время AS TIMESTAMP) IS NOT NULL
        ) TO '{p_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
        """
        con.execute(query)
        dt = round(time.time() - t0, 1)
        
        row_cnt = con.execute(f"SELECT count(*) FROM read_parquet('{p_path}')").fetchone()[0]
        size_mb = round(os.path.getsize(p_path) / (1024 * 1024), 2)
        print(f"[Готово] Год {y}: {row_cnt:,} строк -> {size_mb} МБ Parquet (время: {dt} с)")
        
        converted_files.append(p_path)
        parquet_stats[y] = {
            "rows": row_cnt,
            "parquet_size_mb": size_mb,
            "elapsed_sec": dt
        }

print("\n" + "-" * 50)
print("2. РАСЧЕТ ПОЖИЗНЕННОГО РЕЕСТРА НАДЕЖНОСТИ (SENSOR RELIABILITY STORE)")
print("-" * 50)

t0 = time.time()
channels_csv = "g:/lct2/dataset/справочник_каналов_датчиков.csv"
parquet_glob = f"{parquet_dir}/*.parquet".replace("\\", "/")

reliability_query = f"""
CREATE OR REPLACE TABLE sensor_lifetime_agg AS
SELECT 
    channel_id,
    count(*) AS total_events,
    count(CASE WHEN is_alarm THEN 1 END) AS alarm_events,
    count(CASE WHEN sensor_value IN ('Неисправен', 'Обесточен', 'Отключено устройство', 'Батарея неисправна', 'Затоплен') THEN 1 END) AS failure_events,
    min(event_time) AS first_seen,
    max(event_time) AS last_seen
FROM read_parquet('{parquet_glob}')
GROUP BY channel_id;
"""
print("Агрегирование 313.5 млн записей по всем каналам...")
con.execute(reliability_query)

# Читаем справочник каналов
df_ch = con.execute(f"SELECT * FROM read_csv_auto('{channels_csv}')").df()

def extract_picket(name):
    if not isinstance(name, str): return None
    m = re.search(r'ПК\s*(\d+)(?:\+(\d+))?', name, re.IGNORECASE)
    if m:
        main_pk = float(m.group(1))
        offset = float(m.group(2)) if m.group(2) else 0.0
        return main_pk + offset / 100.0
    return None

df_ch['пикет_км'] = df_ch['название_датчика'].apply(extract_picket)
df_ch['tag_root'] = df_ch['тег_инженерной_системы'].apply(lambda x: re.match(r'^(\d+)-', str(x)).group(1) if re.match(r'^(\d+)-', str(x)) else None)

con.register("df_channels_meta", df_ch)

# Формируем итоговую таблицу надежности
final_rel_query = """
CREATE OR REPLACE TABLE sensor_reliability_8yr AS
SELECT 
    a.channel_id,
    c.название_датчика AS sensor_name,
    c.тип_инж_системы AS subsystem_type,
    c.тип_датчика AS sensor_type,
    c.пикет_км AS picket_km,
    c.tag_root AS tag_root,
    a.total_events,
    a.alarm_events,
    a.failure_events,
    ROUND(a.alarm_events * 100.0 / a.total_events, 2) AS alarm_rate_pct,
    ROUND(a.failure_events * 100.0 / a.total_events, 2) AS failure_rate_pct,
    a.first_seen,
    a.last_seen,
    ROUND(EXTRACT(EPOCH FROM (a.last_seen - a.first_seen)) / 86400.0, 1) AS lifespan_days,
    ROUND((EXTRACT(EPOCH FROM (a.last_seen - a.first_seen)) / 3600.0) / (a.failure_events + 1), 1) AS mtbf_hours
FROM sensor_lifetime_agg a
LEFT JOIN df_channels_meta c ON a.channel_id = c.ид_канала_данных;
"""
con.execute(final_rel_query)

reliability_path = r"g:\lct2\ml_research\data\sensor_reliability_8yr.parquet".replace("\\", "/")
con.execute(f"COPY sensor_reliability_8yr TO '{reliability_path}' (FORMAT PARQUET, COMPRESSION ZSTD);")
rel_count = con.execute("SELECT count(*) FROM sensor_reliability_8yr").fetchone()[0]
print(f"[Готово] Профиль надежности сохранен: {rel_count} каналов (время: {round(time.time() - t0, 1)} с)")

print("\n" + "-" * 50)
print("3. СБОРКА ОБУЧАЮЩЕГО ДАТАСЕТА ПРЕД-ОТКАЗНЫХ СОСТОЯНИЙ (TRAIN / VAL / TEST)")
print("-" * 50)

t0 = time.time()
dataset_query = f"""
CREATE OR REPLACE TABLE ml_events_base AS
WITH failures AS (
    SELECT 
        channel_id,
        event_time AS failure_time,
        event_id
    FROM read_parquet('{parquet_glob}')
    WHERE sensor_value IN ('Неисправен', 'Обесточен', 'Отключено устройство', 'Батарея неисправна', 'Затоплен')
),
pre_failure_windows AS (
    -- Точка наблюдения за 36 часов до отказа
    SELECT 
        f.channel_id,
        f.failure_time - INTERVAL '36 hours' AS obs_time,
        1 AS target_failure_24_72h
    FROM failures f
    USING SAMPLE 15000
),
normal_windows AS (
    -- Случайные срезы нормальной работы без отказов в ближайшие 72 часа
    SELECT 
        p.channel_id,
        p.event_time AS obs_time,
        0 AS target_failure_24_72h
    FROM read_parquet('{parquet_glob}') p
    WHERE p.sensor_value IN ('Норма', 'Есть питание', 'Дыма нет', 'Движения нет')
      AND NOT EXISTS (
          SELECT 1 FROM failures f2 
          WHERE f2.channel_id = p.channel_id 
            AND f2.failure_time BETWEEN p.event_time AND p.event_time + INTERVAL '72 hours'
      )
    USING SAMPLE 25000
)
SELECT * FROM pre_failure_windows
UNION ALL
SELECT * FROM normal_windows;
"""
print("Генерация сбалансированных окон наблюдения (пред-отказы и норма)...")
con.execute(dataset_query)

# Обогащаем фичами надежности и метаданными
ml_features_query = f"""
CREATE OR REPLACE TABLE ml_feature_matrix AS
SELECT 
    b.channel_id,
    b.obs_time,
    b.target_failure_24_72h,
    -- Разделение по времени: Train (2019-2024), Val (2025), Test (2026)
    CASE 
        WHEN EXTRACT(YEAR FROM b.obs_time) <= 2024 THEN 'train'
        WHEN EXTRACT(YEAR FROM b.obs_time) = 2025 THEN 'val'
        ELSE 'test'
    END AS data_split,
    -- Временные фичи
    EXTRACT(HOUR FROM b.obs_time) AS hour_of_day,
    EXTRACT(DOW FROM b.obs_time) AS day_of_week,
    CASE WHEN EXTRACT(MONTH FROM b.obs_time) IN (10, 11, 12, 1, 2, 3, 4) THEN 1 ELSE 0 END AS is_heating_season,
    -- Фичи надежности из реестра
    r.subsystem_type,
    r.sensor_type,
    COALESCE(r.picket_km, -1.0) AS picket_km,
    COALESCE(r.tag_root, '0') AS tag_root,
    r.total_events,
    r.alarm_events,
    r.failure_events,
    r.alarm_rate_pct,
    r.failure_rate_pct,
    COALESCE(r.mtbf_hours, 1000.0) AS mtbf_hours,
    r.lifespan_days
FROM ml_events_base b
JOIN sensor_reliability_8yr r ON b.channel_id = r.channel_id
WHERE b.obs_time IS NOT NULL;
"""
con.execute(ml_features_query)

features_path = r"g:\lct2\ml_research\data\ml_feature_matrix.parquet".replace("\\", "/")
con.execute(f"COPY ml_feature_matrix TO '{features_path}' (FORMAT PARQUET, COMPRESSION ZSTD);")

split_stats = con.execute("""
SELECT 
    data_split,
    count(*) AS count,
    ROUND(mean(target_failure_24_72h) * 100, 1) AS failure_pct
FROM ml_feature_matrix
GROUP BY data_split
ORDER BY data_split
""").df()

print("\nРаспределение обучающей матрицы по годам:")
print(split_stats)

total_rows_all_years = sum(p["rows"] for p in parquet_stats.values())
total_parquet_size = sum(p["parquet_size_mb"] for p in parquet_stats.values())

report = {
    "total_raw_rows": total_rows_all_years,
    "total_parquet_size_mb": round(total_parquet_size, 2),
    "annual_breakdown": parquet_stats,
    "reliability_profile_channels": rel_count,
    "feature_matrix_rows": con.execute("SELECT count(*) FROM ml_feature_matrix").fetchone()[0],
    "split_distribution": split_stats.to_dict(orient="records"),
    "total_elapsed_sec": round(time.time() - start_total, 1)
}

report_path = r"g:\lct2\ml_research\reports\task1_etl_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print(f"ЗАДАЧА 1 ПОЛНОСТЬЮ ВЫПОЛНЕНА за {report['total_elapsed_sec']} секунд!")
print(f"Сжатие: 16 ГБ CSV -> {total_parquet_size:.1f} МБ Parquet")
print(f"Отчет записан в: {report_path}")
print("=" * 60)
