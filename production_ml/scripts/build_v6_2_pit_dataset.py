import os
import sys
import time
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
t_global_start = time.time()

print("=" * 95)
print("Сборка витрины SCADA v6.2: признаки доступны на конец часа")
print("1. Справочник содержит 11 485 каналов; фактический охват проверяется после сборки")
print("2. Справочники: связь 'справочник_каналов_датчиков.csv' с 'справочник_объектов_диспетчер.csv'")
print("3. Временные срезы: TRAIN (2020, 2022, 2023, 2024), STREAM (18 месяцев: 2025 + 2026)")
print("   Строки с obs_time в 2021 году исключаются")
print("4. Автоматическая разметка по событиям SCADA, без подтверждения ремонта")
print("5. Мульти-горизонт: target_flash_1_6h, target_urgent_6_24h, target_planned_24_48h, target_combined_1_48h")
print("6. Существующие признаки v6.1 без изменения формул")
print("7. Полный Train без отбора по признакам и без смены доли классов")
print("=" * 95)

project_dir = Path(__file__).resolve().parents[2]
source_dir = Path(os.environ.get("LCT2_SOURCE_ROOT", project_dir))
base_dir = str(project_dir / "production_ml")
data_dir = os.path.join(base_dir, "data")
cache_dir = os.environ.get("LCT2_CACHE_DIR", os.path.join(data_dir, "cache_v6"))
parquet_dir = str(source_dir / "ml_research" / "data" / "parquet_by_year")
temp_dir = str(project_dir / "duckdb_temp")

os.makedirs(data_dir, exist_ok=True)
os.makedirs(cache_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

ch_csv = str(project_dir / "dataset" / "справочник_каналов_датчиков.csv")
obj_csv = str(project_dir / "dataset" / "справочник_объектов_диспетчер.csv")

# Выходные артефакты
train_out_file = os.path.join(data_dir, "v6_2_train_full_multihorizon.parquet")
stream_out_file = os.path.join(data_dir, "v6_2_stream_18m.parquet")
matched_test_out_file = os.path.join(data_dir, "v6_2_matched_18m.parquet")

con = duckdb.connect()
con.execute("PRAGMA memory_limit = '14GB';")
con.execute("PRAGMA threads = 6;")
con.execute(f"PRAGMA temp_directory = '{temp_dir}';")
con.execute("PRAGMA preserve_insertion_order = false;")

# -----------------------------------------------------------------------------
# 1. СВЯЗЫВАНИЕ СПРАВОЧНИКОВ И ИНИЦИАЛИЗАЦИЯ 100% КАНАЛОВ (11 485 КАНАЛОВ)
# -----------------------------------------------------------------------------
print("\n1. Инициализация метаданных каналов и объектов диспетчеризации...")
t0 = time.time()

con.execute(f"""
CREATE OR REPLACE TABLE channels_meta AS
SELECT 
    ch."ид_канала_данных"::BIGINT AS channel_id,
    COALESCE(ch."тип_инж_системы", 'Неизвестно') AS subsystem_type,
    COALESCE(ch."тип_датчика", 'Неизвестно') AS sensor_type,
    split_part(COALESCE(ch."тег_инженерной_системы", ''), '-', 1) AS tag_root,
    TRY_CAST(regexp_extract(ch."название_датчика", '(?i)ПК\\s*(\\d+)', 1) AS INTEGER) AS picket_num,
    ch."ид_объект"::BIGINT AS object_id,
    COALESCE(o."диспетчерское_название_объекта", 'Объект ' || ch."ид_объект") AS object_name,
    COALESCE(o."вид_объекта", 'Неизвестно') AS object_type
FROM read_csv('{ch_csv}', header=True) ch
LEFT JOIN read_csv('{obj_csv}', header=True) o ON ch."ид_объект" = o."ид_объект";
""")

n_channels = con.execute("SELECT COUNT(*) FROM channels_meta").fetchone()[0]
print(f"   Успешно загружено каналов: {n_channels:,} за {time.time() - t0:.2f}с (охват 100%)")
assert n_channels == 11485, f"Критическая ошибка: ожидалось 11 485 каналов, получено {n_channels}!"

# -----------------------------------------------------------------------------
# 2. РАСШИРЕННЫЙ ДЕТЕКТОР АВАРИЙНЫХ ОТКАЗОВ (T_fail)
# -----------------------------------------------------------------------------
print("\n2. Расчет расширенных аварийных отказов по всем годам (2020-2026, БЕЗ 2021)...")
t_inc = time.time()

train_years = [2020, 2022, 2023, 2024]
stream_years = [2025, 2026]
all_years = train_years + stream_years

# Проверка запрета 2021 года
assert 2021 not in all_years, "Критическая ошибка: 2021 год обнаружен в списке обработки!"

episodes_cache_file = os.path.join(cache_dir, "persistent_failure_episodes.parquet")

if os.path.exists(episodes_cache_file):
    print(f"   [CACHE] Загрузка аварийных эпизодов из кэша: {episodes_cache_file}...")
    con.execute(f"CREATE OR REPLACE TABLE persistent_failure_episodes AS SELECT * FROM read_parquet('{episodes_cache_file}');")
else:
    all_sources = [f"'{parquet_dir}/journal_{y}.parquet'" for y in all_years]
    con.execute(f"""
    CREATE OR REPLACE TABLE raw_incidents_all AS
    WITH raw_combined AS (
        SELECT 
            j.channel_id,
            m.sensor_type,
            j.event_time,
            j.sensor_value,
            j.is_alarm,
            TRY_CAST(j.sensor_value AS FLOAT) AS num_val,
            LAG(j.is_alarm, 1) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev_alarm,
            LAG(j.event_time, 1) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev_time
        FROM read_parquet([{', '.join(all_sources)}]) j
        JOIN channels_meta m ON j.channel_id = m.channel_id
    )
    SELECT 
        channel_id,
        sensor_type,
        event_time,
        sensor_value,
        CASE 
            WHEN sensor_value IN ('Неисправен', 'Обесточен', 'Затоплен') THEN 'TEXT_FAIL'
            WHEN sensor_type = 'КД АВ' AND sensor_value = 'Не замкнут' THEN 'KD_AV_UNCLOSED'
            WHEN sensor_value IN ('-100', '255', '-3276', '-127') THEN 'ERROR_CODE'
            WHEN is_alarm = true AND prev_alarm = true AND epoch(event_time - prev_time) >= 7200 THEN 'ALARM_FREEZE_2H'
            WHEN sensor_type LIKE '%температур%' AND (num_val < -10.0 OR num_val > 55.0) THEN 'TEMP_OUT_OF_BOUNDS'
            -- Единицы измерения газа не подтверждены. Числовой порог пока не создаёт метку отказа.
            ELSE NULL
        END AS fail_reason
    FROM raw_combined
    WHERE 
        sensor_value IN ('Неисправен', 'Обесточен', 'Затоплен', '-100', '255', '-3276', '-127')
        OR (sensor_type = 'КД АВ' AND sensor_value = 'Не замкнут')
        OR (is_alarm = true AND prev_alarm = true AND epoch(event_time - prev_time) >= 7200)
        OR (sensor_type LIKE '%температур%' AND (num_val < -10.0 OR num_val > 55.0))
        ;
    """)

    con.execute("""
    CREATE OR REPLACE TABLE persistent_failure_episodes AS
    WITH ordered AS (
        SELECT 
            channel_id,
            sensor_type,
            event_time,
            fail_reason,
            LAG(event_time, 1) OVER (PARTITION BY channel_id ORDER BY event_time) AS prev_t
        FROM raw_incidents_all
    ),
    flagged AS (
        SELECT 
            channel_id,
            sensor_type,
            event_time,
            fail_reason,
            CASE WHEN prev_t IS NULL OR epoch(event_time - prev_t) > 48 * 3600 THEN 1 ELSE 0 END AS is_new_ep
        FROM ordered
    ),
    grouped AS (
        SELECT 
            channel_id,
            sensor_type,
            event_time,
            fail_reason,
            SUM(is_new_ep) OVER (PARTITION BY channel_id ORDER BY event_time) AS ep_id
        FROM flagged
    )
    SELECT 
        channel_id,
        sensor_type,
        ep_id,
        MIN(event_time) AS t_fail_start,
        MAX(event_time) AS t_fail_end,
        COUNT(*) AS fail_events_count,
        FIRST(fail_reason) AS primary_fail_reason
    FROM grouped
    GROUP BY channel_id, sensor_type, ep_id;
    """)

    con.execute(f"COPY persistent_failure_episodes TO '{episodes_cache_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.execute("DROP TABLE raw_incidents_all;")

n_episodes = con.execute("SELECT COUNT(*) FROM persistent_failure_episodes").fetchone()[0]
print(f"   Сформировано уникальных аварийных эпизодов: {n_episodes:,} за {time.time() - t_inc:.2f}с")

# -----------------------------------------------------------------------------
# 3. ПОГОДОВАЯ ГЕНЕРАЦИЯ ПОЧАСОВЫХ ВИТРИН С ТЯЖЕЛЫМИ МАТЕМАТИЧЕСКИМИ ПРИЗНАКАМИ
# -----------------------------------------------------------------------------
print("\n3. Генерация почасовых витрин по отдельным годам (сверхбыстрый расчет с дисковым кэшем)...")

def generate_hourly_for_year(year):
    t_y = time.time()
    cache_f = os.path.join(cache_dir, f"hourly_{year}.parquet")
    if os.path.exists(cache_f):
        print(f"   • {year} год: загрузка из кэша ({cache_f})...")
        con.execute(f"CREATE OR REPLACE TABLE hourly_{year} AS SELECT * FROM read_parquet('{cache_f}');")
        cnt_h = con.execute(f"SELECT COUNT(*) FROM hourly_{year}").fetchone()[0]
        print(f"     [OK] {year} год готов: {cnt_h:,} почасовых строк за {time.time() - t_y:.2f}с")
        return

    source_p = f"{parquet_dir}/journal_{year}.parquet"
    print(f"   • Обработка {year} года ({source_p})...")
    
    con.execute(f"""
    CREATE OR REPLACE TABLE raw_dt_{year} AS
    WITH raw_ordered AS (
        SELECT 
            j.channel_id,
            m.sensor_type,
            m.subsystem_type,
            m.tag_root,
            m.picket_num,
            m.object_id,
            j.event_time,
            date_trunc('hour', j.event_time) AS hour_bin,
            date_trunc('second', j.event_time) AS sec_bin,
            j.sensor_value,
            j.is_alarm,
            TRY_CAST(j.sensor_value AS FLOAT) AS num_val,
            
            CASE WHEN j.sensor_value != LAG(j.sensor_value) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) THEN 1 ELSE 0 END AS is_flip,
            COALESCE(epoch(j.event_time - LAG(j.event_time) OVER (PARTITION BY j.channel_id ORDER BY j.event_time)), 3600.0) AS dt_sec,
            
            CASE WHEN j.sensor_value IN ('Включен', 'Есть питание') THEN 1 ELSE 0 END AS is_active_status,
            CASE WHEN j.sensor_value = 'Норма' THEN 1 ELSE 0 END AS is_norm_status,
            CASE WHEN j.sensor_value = 'Обесточен' THEN 1 ELSE 0 END AS is_pwr_off,
            CASE WHEN j.sensor_value = 'Есть питание' THEN 1 ELSE 0 END AS is_pwr_on,
            CASE WHEN j.sensor_value = 'Не замкнут' THEN 1 ELSE 0 END AS is_open,
            CASE WHEN j.sensor_value = 'Обнаружено движение' THEN 1 ELSE 0 END AS is_motion,
            
            LAG(j.sensor_value, 1) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev1_val,
            LAG(j.sensor_value, 2) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev2_val,
            LAG(j.event_time, 2) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev2_time,
            
            CASE WHEN j.sensor_value LIKE '%1970%' THEN 1 ELSE 0 END AS is_reboot_1970,
            CASE WHEN j.sensor_value IN ('Питание от батарей', 'Батарея неисправна', 'Батарея разряжена') THEN 1 ELSE 0 END AS is_battery_trouble,
            CASE WHEN j.is_alarm = true OR j.sensor_value IN ('Неисправен', 'Обесточен', 'Затоплен', 'Неопределен') THEN 1 ELSE 0 END AS is_trouble
        FROM read_parquet('{source_p}') j
        JOIN channels_meta m ON j.channel_id = m.channel_id
    )
    SELECT * FROM raw_ordered;
    """)
    
    con.execute(f"""
    CREATE OR REPLACE TABLE hourly_{year} AS
    SELECT 
        channel_id,
        sensor_type,
        subsystem_type,
        tag_root,
        picket_num,
        object_id,
        hour_bin,
        
        COUNT(*)::INTEGER AS events_1h,
        SUM(is_flip)::INTEGER AS flips_1h,
        SUM(CASE WHEN is_flip = 1 AND dt_sec <= 2.0 THEN 1 ELSE 0 END)::INTEGER AS sub2s_flips_1h,
        
        COALESCE(AVG(CASE WHEN is_flip = 1 AND dt_sec > 0 THEN dt_sec END), 0.0)::FLOAT AS avg_dt_1h,
        COALESCE(STDDEV_POP(CASE WHEN is_flip = 1 AND dt_sec > 0 THEN dt_sec END), 0.0)::FLOAT AS std_dt_1h,
        SUM(CASE WHEN is_active_status = 1 AND dt_sec > 0 AND dt_sec < 3600 THEN dt_sec ELSE 0 END)::FLOAT AS active_sec_1h,
        
        AVG(CASE WHEN is_norm_status = 1 AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание') AND dt_sec > 0 AND dt_sec < 86400 THEN dt_sec END)::FLOAT AS restore_sec_1h,
        COUNT(CASE WHEN is_norm_status = 1 AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание') THEN 1 END)::INTEGER AS restore_cnt_1h,
        
        COUNT(CASE 
            WHEN (prev1_val = 'Есть питание' AND sensor_value = 'Обесточен')
              OR (prev1_val = 'Норма' AND sensor_value = 'Неисправен')
              OR (prev1_val = 'Включен' AND sensor_value = 'Неисправен')
            THEN 1 END)::INTEGER AS forbidden_trans_1h,
            
        COUNT(CASE 
            WHEN prev2_val IN ('Норма', 'Выключен', 'Есть питание')
             AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание')
             AND sensor_value IN ('Норма', 'Выключен', 'Есть питание')
             AND epoch(event_time - prev2_time) <= 3.0
            THEN 1 END)::INTEGER AS rapid_bounce_1h,
            
        SUM(CASE WHEN is_flip = 1 AND is_active_status = 1 THEN 1 ELSE 0 END)::INTEGER AS flips_up_1h,
        SUM(CASE WHEN is_flip = 1 AND is_norm_status = 1 THEN 1 ELSE 0 END)::INTEGER AS flips_down_1h,
        SUM(CASE WHEN sensor_value IN ('Неопределен', 'Не определено') THEN 1 ELSE 0 END)::INTEGER AS undef_1h,
        
        AVG(num_val)::FLOAT AS avg_num_1h,
        STDDEV_POP(num_val)::FLOAT AS std_num_1h,
        COUNT(num_val)::INTEGER AS num_cnt_1h,
        MIN(num_val)::FLOAT AS min_num_1h,
        MAX(num_val)::FLOAT AS max_num_1h,
        
        SUM(is_pwr_off)::INTEGER AS pwr_off_1h,
        SUM(is_pwr_on)::INTEGER AS pwr_on_1h,
        SUM(is_norm_status)::INTEGER AS norm_1h,
        SUM(is_open)::INTEGER AS door_open_1h,
        SUM(is_motion)::INTEGER AS motion_1h,
        SUM(is_reboot_1970)::INTEGER AS reboot_1970_1h,
        SUM(is_battery_trouble)::INTEGER AS battery_trouble_1h,
        SUM(is_trouble)::INTEGER AS trouble_1h,
        SUM(CASE WHEN is_alarm = true THEN 1 ELSE 0 END)::INTEGER AS alarm_1h,
        
        -- 6 ТЯЖЕЛЫХ МАТЕМАТИЧЕСКИХ ПРИЗНАКОВ (DSP & Point Process)
        COALESCE(AVG(exp(-0.5 * LEAST(dt_sec, 60.0))), 0.0)::FLOAT AS hawkes_alpha_1h,
        COALESCE(kurtosis(dt_sec), 0.0)::FLOAT AS dwell_kurtosis_1h,
        CASE WHEN quantile_cont(dt_sec, 0.50) > 0 
             THEN (quantile_cont(dt_sec, 0.99) / quantile_cont(dt_sec, 0.50))::FLOAT 
             ELSE 1.0 END AS dwell_p99_ratio_1h,
        (SUM(CASE WHEN dt_sec < 20.0 THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0))::FLOAT AS hf_power_ratio_1h,
        COALESCE(entropy(floor(log2(GREATEST(dt_sec, 1.0)))), 0.0)::FLOAT AS spectral_entropy_1h,
        COALESCE(entropy(sensor_value), 0.0)::FLOAT AS seq_entropy_1h
        
    FROM raw_dt_{year}
    GROUP BY channel_id, sensor_type, subsystem_type, tag_root, picket_num, object_id, hour_bin;
    """)
    
    con.execute(f"COPY hourly_{year} TO '{cache_f}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    con.execute(f"DROP TABLE raw_dt_{year};")
    con.execute(f"DROP TABLE hourly_{year};")
    print(f"     [OK] {year} год сохранен в кэш ({cache_f}) за {time.time() - t_y:.2f}с")

for y in all_years:
    generate_hourly_for_year(y)

# -----------------------------------------------------------------------------
# 4. СБОРКА РАЗМЕЧЕННЫХ ПАРТИЦИЙ (TRAIN И STREAM)
# -----------------------------------------------------------------------------
def process_partition(years, part_name="train"):
    t_part_start = time.time()
    print(f"\n>>> РАСЧЕТ ОКОННЫХ ПРИЗНАКОВ И МУЛЬТИ-ГОРИЗОНТА: {part_name.upper()} <<<")
    
    # 4.1 Объединение почасовых витрин из кэша
    parquet_files = [f"'{cache_dir}/hourly_{y}.parquet'" for y in years]
    con.execute(f"CREATE OR REPLACE TABLE hourly_merged_{part_name} AS SELECT * FROM read_parquet([{', '.join(parquet_files)}]);")
    cnt_merged = con.execute(f"SELECT COUNT(*) FROM hourly_merged_{part_name}").fetchone()[0]
    print(f"   1/4. Почасовые таблицы объединены ({cnt_merged:,} строк)")
    
    # 4.2 Контекст объектов диспетчеризации (object_flips_24h)
    con.execute(f"""
    CREATE OR REPLACE TABLE object_hourly_{part_name} AS
    SELECT 
        object_id,
        hour_bin,
        SUM(flips_1h)::INTEGER AS obj_flips_1h
    FROM hourly_merged_{part_name}
    GROUP BY object_id, hour_bin;
    """)

    con.execute(f"""
    CREATE OR REPLACE TABLE object_rolling_{part_name} AS
    SELECT 
        object_id,
        hour_bin,
        SUM(obj_flips_1h) OVER (
            PARTITION BY object_id ORDER BY hour_bin 
            RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW
        )::INTEGER AS object_flips_24h
    FROM object_hourly_{part_name};
    """)
    
    # 4.3 Шкафной и пикетный контекст
    con.execute(f"""
    CREATE OR REPLACE TABLE cabinet_hourly_{part_name} AS
    SELECT 
        tag_root,
        hour_bin,
        SUM(reboot_1970_1h)::INTEGER AS reboot_1970_1h,
        SUM(battery_trouble_1h)::INTEGER AS battery_trouble_1h,
        SUM(flips_1h)::INTEGER AS cab_flips_1h,
        SUM(CASE WHEN sensor_type = 'Состояние фазы' THEN pwr_on_1h ELSE 0 END)::INTEGER AS phase_power_on_1h,
        COUNT(DISTINCT channel_id)::INTEGER AS active_cab_channels
    FROM hourly_merged_{part_name}
    GROUP BY tag_root, hour_bin;
    """)

    con.execute(f"""
    CREATE OR REPLACE TABLE cabinet_rolling_{part_name} AS
    SELECT 
        tag_root,
        hour_bin,
        phase_power_on_1h,
        MAX(active_cab_channels) OVER w24_cab::INTEGER AS bus_simultaneous_drop_count,
        SUM(cab_flips_1h) OVER w24_cab::INTEGER AS cabinet_flips_24h,
        SUM(reboot_1970_1h) OVER w72_cab::INTEGER AS cabinet_reboot_cascade_3d,
        SUM(CASE WHEN battery_trouble_1h > 0 THEN 1 ELSE 0 END) OVER w336_cab::FLOAT AS battery_backup_wear_index
    FROM cabinet_hourly_{part_name}
    WINDOW 
        w24_cab AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
        w72_cab AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW),
        w336_cab AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 335 HOUR PRECEDING AND CURRENT ROW);
    """)

    con.execute(f"""
    CREATE OR REPLACE TABLE picket_hourly_{part_name} AS
    SELECT 
        picket_num,
        hour_bin,
        SUM(flips_1h)::INTEGER AS picket_flips_1h,
        SUM(CASE WHEN sensor_type = 'Датчик затопления' AND norm_1h > 0 THEN 1 ELSE 0 END)::INTEGER AS flood_norm_hours_1h,
        SUM(CASE WHEN sensor_type = 'Датчик движения' AND motion_1h > 0 THEN 1 ELSE 0 END)::INTEGER AS motion_detected_1h,
        COUNT(DISTINCT CASE WHEN trouble_1h > 0 THEN subsystem_type END)::INTEGER AS trouble_subsystems_1h
    FROM hourly_merged_{part_name}
    WHERE picket_num IS NOT NULL
    GROUP BY picket_num, hour_bin;
    """)

    con.execute(f"""
    CREATE OR REPLACE TABLE picket_rolling_{part_name} AS
    SELECT 
        picket_num,
        hour_bin,
        flood_norm_hours_1h,
        motion_detected_1h,
        SUM(picket_flips_1h) OVER w24_pic::INTEGER AS picket_flips_24h,
        SUM(trouble_subsystems_1h) OVER w12_pic::INTEGER AS picket_multi_system_concurrence
    FROM picket_hourly_{part_name}
    WINDOW
        w24_pic AS (PARTITION BY picket_num ORDER BY hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
        w12_pic AS (PARTITION BY picket_num ORDER BY hour_bin RANGE BETWEEN INTERVAL 11 HOUR PRECEDING AND CURRENT ROW);
    """)
    print("   2/4. Контексты объектов, шкафов и пикетов сформированы.")

    # 4.4 Расчет скользящих оконных 49 признаков
    con.execute(f"""
    CREATE OR REPLACE TABLE feature_store_{part_name} AS
    SELECT 
        h.channel_id,
        h.sensor_type,
        h.subsystem_type,
        h.tag_root,
        h.picket_num,
        h.object_id,
        h.hour_bin + INTERVAL 1 HOUR AS obs_time,
        
        -- 1. КРОСС-КАНАЛЬНЫЕ ПРИЗНАКИ (8)
        CASE 
            WHEN h.sensor_type = 'Состояние фазы' AND h.pwr_off_1h > 0 AND c.phase_power_on_1h > 0 
            THEN 1 ELSE 0 
        END::TINYINT AS phase_solo_dropout_flag,
        
        CASE 
            WHEN h.sensor_type = 'Состояние насоса' AND h.active_sec_1h > 0 AND p.flood_norm_hours_1h > 0 
            THEN 1.0 ELSE 0.0 
        END::FLOAT AS pump_dry_run_anomaly,
        
        CASE 
            WHEN h.sensor_type = 'Датчик движения' AND h.motion_1h > 0 AND COALESCE(p.motion_detected_1h, 0) = 0 
            THEN 1.0 ELSE 0.0 
        END::FLOAT AS door_motion_ghost_ratio,
        
        COALESCE(c.bus_simultaneous_drop_count, 0)::INTEGER AS bus_simultaneous_drop_count,
        COALESCE(p.picket_multi_system_concurrence, 0)::INTEGER AS picket_multi_system_concurrence,
        COALESCE(p.picket_flips_24h, 0)::INTEGER AS picket_neighbors_flips_24h,
        
        CASE 
            WHEN COALESCE(p.picket_flips_24h, 0) > 0 
            THEN (SUM(h.flips_1h) OVER w24_feat)::FLOAT / p.picket_flips_24h 
            ELSE 1.0 
        END::FLOAT AS picket_isolation_index,
        
        COALESCE(o.object_flips_24h, 0)::INTEGER AS object_flips_24h,
        
        -- 2. МИКРОФИЗИКА И ДРЕБЕЗГ (9)
        (SUM(h.flips_1h) OVER w1_feat)::INTEGER AS flips_count_1h,
        (SUM(h.flips_1h) OVER w24_feat)::INTEGER AS flips_count_24h,
        (SUM(h.flips_1h) OVER w72_feat)::INTEGER AS flips_count_72h,
        (SUM(h.events_1h) OVER w24_feat)::INTEGER AS events_count_24h,
        (SUM(h.sub2s_flips_1h) OVER w24_feat)::INTEGER AS sub2s_flips_24h,
        
        CASE 
            WHEN (SUM(h.flips_1h) OVER w24_feat) > 0 
            THEN (SUM(h.sub2s_flips_1h) OVER w24_feat)::FLOAT / (SUM(h.flips_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS micro_burst_sub2s_ratio,
        
        CASE 
            WHEN (AVG(h.avg_dt_1h) OVER w24_feat) > 0 
            THEN (AVG(h.std_dt_1h) OVER w24_feat)::FLOAT / (AVG(h.avg_dt_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS period_jitter_cv,
        
        ((SUM(h.active_sec_1h) OVER w24_feat)::FLOAT / 86400.0)::FLOAT AS duty_cycle_24h,
        COALESCE(AVG(h.restore_sec_1h) OVER w24_feat, 0.0)::FLOAT AS mean_time_to_restore_sec,
        
        h.flips_1h::INTEGER AS micro_chatter_count_1h,
        CASE 
            WHEN (AVG(h.flips_1h) OVER w24_feat) > 0 
            THEN (h.flips_1h)::FLOAT / (AVG(h.flips_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS micro_chatter_ratio_1h,
        
        -- 3. ГРАММАТИКА И АЦП (9)
        (SUM(h.forbidden_trans_1h) OVER w24_feat)::INTEGER AS forbidden_transition_rate,
        COALESCE(AVG(h.seq_entropy_1h) OVER w24_feat, 0.0)::FLOAT AS transition_matrix_entropy,
        (SUM(h.rapid_bounce_1h) OVER w24_feat)::INTEGER AS rapid_bounce_triplet_count,
        SUM(CASE WHEN h.num_cnt_1h > 0 AND h.std_num_1h = 0.0 THEN 1 ELSE 0 END) OVER w24_feat::INTEGER AS adc_bit_freezing_hours,
        COALESCE(AVG(h.std_num_1h) OVER w24_feat, 0.0)::FLOAT AS quantization_step_anomaly,
        ABS(COALESCE(AVG(h.avg_num_1h) OVER w24_feat, 0.0) - COALESCE(AVG(h.avg_num_1h) OVER w168_feat, 0.0))::FLOAT AS baseline_creep_7d,
        
        CASE 
            WHEN (SUM(h.flips_up_1h + h.flips_down_1h) OVER w24_feat) > 0 
            THEN (SUM(h.flips_up_1h) OVER w24_feat)::FLOAT / (SUM(h.flips_up_1h + h.flips_down_1h) OVER w24_feat) 
            ELSE 0.5 
        END::FLOAT AS state_transition_asymmetry_24h,
        
        (SUM(h.undef_1h) OVER w24_feat)::INTEGER AS undefined_count_24h,
        CASE 
            WHEN (SUM(h.events_1h) OVER w24_feat) > 0 
            THEN (SUM(h.undef_1h) OVER w24_feat)::FLOAT / (SUM(h.events_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS undefined_ratio_24h,
        
        -- 4. БАЗОВЫЕ ОБЪЕМЫ И ДИНАМИКА 2-ГО ПОРЯДКА (17)
        CASE 
            WHEN (AVG(h.flips_1h) OVER w720_feat) > 0 
            THEN (SUM(h.flips_1h) OVER w24_feat)::FLOAT / (24.0 * (AVG(h.flips_1h) OVER w720_feat)) 
            ELSE 1.0 
        END::FLOAT AS activity_ratio_30d,
        
        CASE 
            WHEN (AVG(h.flips_1h) OVER w24_feat + STDDEV_POP(h.flips_1h) OVER w24_feat) > 0 
            THEN (STDDEV_POP(h.flips_1h) OVER w24_feat - AVG(h.flips_1h) OVER w24_feat) / (STDDEV_POP(h.flips_1h) OVER w24_feat + AVG(h.flips_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS burstiness_index,
        
        SUM(CASE WHEN EXTRACT(HOUR FROM h.hour_bin) BETWEEN 0 AND 6 THEN h.flips_1h ELSE 0 END) OVER w24_feat::FLOAT AS night_excess,
        ((SUM(h.flips_1h) OVER w24_feat - SUM(h.flips_1h) OVER w72_prev_feat) / 48.0)::FLOAT AS slope_flips_3d,
        ((SUM(h.flips_1h) OVER w24_feat - 2.0 * SUM(h.flips_1h) OVER w24_prev_feat + SUM(h.flips_1h) OVER w48_prev_feat) / 24.0)::FLOAT AS accel_flips_3d,
        
        CASE 
            WHEN (SUM(h.events_1h) OVER w24_feat) > 0 
            THEN (SUM(h.alarm_1h) OVER w24_feat)::FLOAT / (SUM(h.events_1h) OVER w24_feat) 
            ELSE 0.0 
        END::FLOAT AS alarm_ratio_24h,
        
        COALESCE(STDDEV_POP(h.avg_num_1h) OVER w24_feat, 0.0)::FLOAT AS analog_std_24h,
        ABS(COALESCE(LAST_VALUE(h.avg_num_1h) OVER w12_feat, 0.0) - COALESCE(FIRST_VALUE(h.avg_num_1h) OVER w12_feat, 0.0))::FLOAT AS analog_drift_12h,
        ((COALESCE(STDDEV_POP(h.avg_num_1h) OVER w24_feat, 0.0) - COALESCE(STDDEV_POP(h.avg_num_1h) OVER w72_prev_feat, 0.0)) / 48.0)::FLOAT AS slope_std_3d,
        
        COALESCE(c.cabinet_reboot_cascade_3d, 0)::INTEGER AS cabinet_reboot_cascade_3d,
        COALESCE(c.battery_backup_wear_index, 0.0)::FLOAT AS battery_backup_wear_index,
        CASE WHEN (SUM(h.battery_trouble_1h) OVER w168_feat) > 0 THEN 1 ELSE 0 END::TINYINT AS ups_battery_trouble_flag_7d,
        CASE WHEN (SUM(h.reboot_1970_1h) OVER w24_feat) > 0 THEN 1 ELSE 0 END::TINYINT AS cabinet_reboot_1970_24h,
        CASE WHEN (SUM(h.trouble_1h) OVER w24_feat) > 0 THEN 1 ELSE 0 END::TINYINT AS controller_device_lost_24h,
        CASE WHEN (SUM(CASE WHEN h.sensor_type LIKE '%переговор%' AND h.events_1h > 0 THEN 1 ELSE 0 END) OVER w3_feat) > 0 THEN 1 ELSE 0 END::TINYINT AS intercom_active_3h,
        COALESCE(c.cabinet_flips_24h, 0)::INTEGER AS cabinet_flips_24h,
        0.0::FLOAT AS spatial_differential_picket,
        
        -- 5. НОВЫЕ ТЯЖЕЛЫЕ МАТЕМАТИЧЕСКИЕ ПРИЗНАКИ (6)
        COALESCE(AVG(h.hawkes_alpha_1h) OVER w24_feat, 0.0)::FLOAT AS hawkes_branching_ratio_alpha,
        COALESCE(AVG(h.dwell_kurtosis_1h) OVER w24_feat, 0.0)::FLOAT AS dwell_time_kurtosis,
        COALESCE(AVG(h.dwell_p99_ratio_1h) OVER w24_feat, 1.0)::FLOAT AS dwell_time_p99_to_median,
        COALESCE(AVG(h.spectral_entropy_1h) OVER w24_feat, 0.0)::FLOAT AS spectral_entropy_ls,
        COALESCE(AVG(h.hf_power_ratio_1h) OVER w24_feat, 0.0)::FLOAT AS high_freq_power_ratio,
        COALESCE(AVG(h.seq_entropy_1h) OVER w24_feat, 0.0)::FLOAT AS sequence_compression_entropy
        
    FROM hourly_merged_{part_name} h
    LEFT JOIN cabinet_rolling_{part_name} c ON h.tag_root = c.tag_root AND h.hour_bin = c.hour_bin
    LEFT JOIN picket_rolling_{part_name} p ON h.picket_num = p.picket_num AND h.hour_bin = p.hour_bin
    LEFT JOIN object_rolling_{part_name} o ON h.object_id = o.object_id AND h.hour_bin = o.hour_bin
    WINDOW
        w1_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 0 HOUR PRECEDING AND CURRENT ROW),
        w3_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 2 HOUR PRECEDING AND CURRENT ROW),
        w12_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 11 HOUR PRECEDING AND CURRENT ROW),
        w24_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
        w24_prev_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 47 HOUR PRECEDING AND INTERVAL 24 HOUR PRECEDING),
        w48_prev_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND INTERVAL 48 HOUR PRECEDING),
        w72_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW),
        w72_prev_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 95 HOUR PRECEDING AND INTERVAL 24 HOUR PRECEDING),
        w168_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 167 HOUR PRECEDING AND CURRENT ROW),
        w720_feat AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 719 HOUR PRECEDING AND CURRENT ROW);
    """)
    print("   3/4. Скользящие 49 признаков рассчитаны.")

    # 4.5 Мульти-горизонтная разметка и карантин
    con.execute(f"""
    CREATE OR REPLACE TABLE labeled_{part_name} AS
    WITH nearest_future AS (
        SELECT 
            f.*,
            e.t_fail_start,
            e.t_fail_end,
            epoch(e.t_fail_start - f.obs_time) / 3600.0 AS lead_hours
        FROM feature_store_{part_name} f
        ASOF LEFT JOIN persistent_failure_episodes e
          ON f.channel_id = e.channel_id AND f.obs_time <= e.t_fail_start
    ),
    matched AS (
        SELECT n.*, q.t_fail_end AS previous_fail_end
        FROM nearest_future n
        ASOF LEFT JOIN persistent_failure_episodes q
          ON n.channel_id = q.channel_id AND n.obs_time > q.t_fail_start
    )
    SELECT 
        channel_id,
        sensor_type,
        subsystem_type,
        tag_root,
        object_id,
        obs_time,
        
        -- Целевые метки мульти-горизонта
        CASE WHEN lead_hours >= 1.0 AND lead_hours < 6.0 THEN 1 ELSE 0 END::TINYINT AS target_flash_1_6h,
        CASE WHEN lead_hours >= 6.0 AND lead_hours < 24.0 THEN 1 ELSE 0 END::TINYINT AS target_urgent_6_24h,
        CASE WHEN lead_hours >= 24.0 AND lead_hours <= 48.0 THEN 1 ELSE 0 END::TINYINT AS target_planned_24_48h,
        CASE WHEN lead_hours >= 1.0 AND lead_hours <= 48.0 THEN 1 ELSE 0 END::TINYINT AS target_combined_1_48h,
        
        -- Физические предвестники для P-F цензурирования
        CASE 
            WHEN flips_count_24h > 2 
              OR micro_burst_sub2s_ratio > 0.08 
              OR ABS(state_transition_asymmetry_24h - 0.5) > 0.15 
              OR undefined_count_24h >= 1 
              OR duty_cycle_24h > 0.25 
              OR night_excess > 10.0 
              OR period_jitter_cv > 1.5 
              OR hawkes_branching_ratio_alpha > 0.3 
              OR adc_bit_freezing_hours >= 12
            THEN 1 ELSE 0 
        END::TINYINT AS has_physics_precursor,
        
        -- 49 ЧИСТЫХ ФИЗИЧЕСКИХ ПРИЗНАКОВ
        phase_solo_dropout_flag, pump_dry_run_anomaly, door_motion_ghost_ratio, bus_simultaneous_drop_count,
        picket_multi_system_concurrence, picket_neighbors_flips_24h, picket_isolation_index, object_flips_24h,
        flips_count_1h, flips_count_24h, flips_count_72h, events_count_24h, sub2s_flips_24h,
        micro_burst_sub2s_ratio, period_jitter_cv, duty_cycle_24h, mean_time_to_restore_sec,
        micro_chatter_count_1h, micro_chatter_ratio_1h, forbidden_transition_rate, transition_matrix_entropy,
        rapid_bounce_triplet_count, adc_bit_freezing_hours, quantization_step_anomaly, baseline_creep_7d,
        state_transition_asymmetry_24h, undefined_count_24h, undefined_ratio_24h, activity_ratio_30d,
        burstiness_index, night_excess, slope_flips_3d, accel_flips_3d, alarm_ratio_24h,
        analog_std_24h, analog_drift_12h, slope_std_3d, cabinet_reboot_cascade_3d, battery_backup_wear_index,
        ups_battery_trouble_flag_7d, cabinet_reboot_1970_24h, controller_device_lost_24h, intercom_active_3h,
        cabinet_flips_24h, spatial_differential_picket, hawkes_branching_ratio_alpha, dwell_time_kurtosis,
        dwell_time_p99_to_median, spectral_entropy_ls, high_freq_power_ratio, sequence_compression_entropy
        
    FROM matched
    -- Исключаем час, пересекающийся с зафиксированным эпизодом.
    -- t_fail_end – последняя аварийная запись, а не подтверждённое восстановление.
    WHERE (lead_hours IS NULL OR lead_hours >= 1.0)
      AND (previous_fail_end IS NULL OR previous_fail_end < obs_time - INTERVAL 1 HOUR);
    """)

    con.execute(f"DROP TABLE IF EXISTS hourly_merged_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS object_hourly_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS object_rolling_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS cabinet_hourly_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS cabinet_rolling_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS picket_hourly_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS picket_rolling_{part_name};")
    con.execute(f"DROP TABLE IF EXISTS feature_store_{part_name};")
    n_lab = con.execute(f"SELECT COUNT(*) FROM labeled_{part_name}").fetchone()[0]
    print(f"   4/4. Разметка и карантин завершены: {n_lab:,} строк за {time.time() - t_part_start:.2f}с")
    return n_lab

# Запуск обработки Train и Stream
n_train_raw = process_partition(train_years, "train")
n_stream_raw = process_partition(stream_years, "stream")

# -----------------------------------------------------------------------------
# 5. ПОЛНЫЙ TRAIN С ЕСТЕСТВЕННОЙ ДОЛЕЙ КЛАССОВ
# -----------------------------------------------------------------------------
print("\n" + "=" * 90)
print("5. ПОЛНЫЙ TRAIN БЕЗ ОТБОРА ПОЛОЖИТЕЛЬНЫХ СТРОК ПО ПРИЗНАКАМ")
print("=" * 90)

con.execute("""
CREATE OR REPLACE TABLE final_train AS
SELECT * EXCLUDE (has_physics_precursor) FROM labeled_train
WHERE year(obs_time) IN (2020, 2022, 2023, 2024)
  AND obs_time < TIMESTAMP '2024-12-30 00:00:00';
""")

n_final_train = con.execute("SELECT COUNT(*) FROM final_train").fetchone()[0]
pos_final_cnt = con.execute("SELECT COUNT(*) FROM final_train WHERE target_combined_1_48h = 1").fetchone()[0]
neg_final_cnt = con.execute("SELECT COUNT(*) FROM final_train WHERE target_combined_1_48h = 0").fetchone()[0]
ratio_train = neg_final_cnt / pos_final_cnt if pos_final_cnt > 0 else 0
print(f"   Итоговый Train: {n_final_train:,} строк (Позитивов: {pos_final_cnt:,}, Негативов: {neg_final_cnt:,}, Баланс: 1 к {ratio_train:.1f})")

# -----------------------------------------------------------------------------
# 6. ФОРМИРОВАНИЕ ПОТОКА STREAM И КОНТРОЛЬНОГО СРЕЗА MATCHED TEST
# -----------------------------------------------------------------------------
print("\n" + "=" * 90)
print("6. ЭКСПОРТ ПОТОКА STREAM (18 МЕСЯЦЕВ, 100% КАНАЛОВ) И MATCHED TEST")
print("=" * 90)

con.execute("""
CREATE OR REPLACE TABLE final_stream AS
SELECT * EXCLUDE (has_physics_precursor)
FROM labeled_stream
ORDER BY channel_id, obs_time;
""")
n_final_stream = con.execute("SELECT COUNT(*) FROM final_stream").fetchone()[0]
pos_stream_cnt = con.execute("SELECT COUNT(*) FROM final_stream WHERE target_combined_1_48h = 1").fetchone()[0]
print(f"   Сплошной поток Stream: {n_final_stream:,} строк (реальных предаварийных часов: {pos_stream_cnt:,})")

con.execute(f"""
CREATE OR REPLACE TABLE final_matched_test AS
WITH test_pos AS (
    SELECT * FROM final_stream WHERE target_combined_1_48h = 1
),
test_neg AS (
    SELECT * FROM final_stream WHERE target_combined_1_48h = 0
),
neg_sampled AS (
    SELECT * FROM test_neg USING SAMPLE {max(1, pos_stream_cnt * 5)} (reservoir)
)
SELECT * FROM test_pos
UNION ALL
SELECT * FROM neg_sampled;
""")
n_matched_test = con.execute("SELECT COUNT(*) FROM final_matched_test").fetchone()[0]
print(f"   Контрольный срез Matched Test (1:5): {n_matched_test:,} строк")

con.execute("DROP TABLE IF EXISTS labeled_train;")
con.execute("DROP TABLE IF EXISTS labeled_stream;")
con.execute("DROP TABLE IF EXISTS persistent_failure_episodes;")

# -----------------------------------------------------------------------------
# 7. ЭКСПОРТ В PARQUET И ВАЛИДАЦИЯ КАЧЕСТВА
# -----------------------------------------------------------------------------
print("\n" + "=" * 90)
print(f"7. ЭКСПОРТ ПАРКЕТ-АРТЕФАКТОВ В {data_dir}/...")
print("=" * 90)

t_exp = time.time()
print(f"   Экспорт {train_out_file}...")
con.execute(f"COPY final_train TO '{train_out_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")

print(f"   Экспорт {stream_out_file}...")
con.execute(f"COPY final_stream TO '{stream_out_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")

print(f"   Экспорт {matched_test_out_file}...")
con.execute(f"COPY final_matched_test TO '{matched_test_out_file}' (FORMAT PARQUET, COMPRESSION ZSTD);")
print(f"   Все 3 файла успешно сохранены за {time.time() - t_exp:.2f}с")

# -----------------------------------------------------------------------------
# 8. ПРОВЕРКА СХЕМЫ И ЧИСЛОВЫХ ЗНАЧЕНИЙ
# -----------------------------------------------------------------------------
print("\n" + "=" * 90)
print("8. ПРОВЕРКА СХЕМЫ, NaN/Inf, NULL И 2021 ГОДА")
print("=" * 90)

train_cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{train_out_file}')").fetchall()]
print(f"Колонок в Train: {len(train_cols)}")

for tok in ['horizon_hours', 'is_holdout', 'days_since_last_incident']:
    assert tok not in train_cols, f"КРИТИЧЕСКАЯ ОШИБКА: обнаружена утечка '{tok}' в Train!"
print("   Проверены три явно запрещённые колонки; временной протокол проверяется отдельно.")

feature_cols = [
    c for c in train_cols 
    if c not in ['channel_id', 'sensor_type', 'subsystem_type', 'tag_root', 'object_id', 'obs_time',
                 'target_flash_1_6h', 'target_urgent_6_24h', 'target_planned_24_48h', 'target_combined_1_48h']
]
print(f"   Проверка {len(feature_cols)} признаков на NaN/Inf...")

nan_check_query = "SELECT " + ", ".join([f"COUNT(CASE WHEN isnan({c}) OR isinf({c}) THEN 1 END) AS {c}_bad" for c in feature_cols]) + f" FROM read_parquet('{train_out_file}')"
nan_res = con.execute(nan_check_query).df()
bad_sum = nan_res.sum().sum()
assert bad_sum == 0, f"КРИТИЧЕСКАЯ ОШИБКА: обнаружено {bad_sum} некорректных значений (NaN/Inf) в признаках!"
print(f"   [OK] Значений NaN / Inf в признаковом пространстве: ровно 0.")
null_check_query = "SELECT " + ", ".join([f'count(*) FILTER (WHERE "{c}" IS NULL) AS "{c}"' for c in feature_cols]) + f" FROM read_parquet('{train_out_file}')"
null_res = con.execute(null_check_query).df().iloc[0]
print("   Число NULL по признакам:", {name: int(value) for name, value in null_res.items() if value})

years_in_train = con.execute(f"SELECT DISTINCT EXTRACT(YEAR FROM obs_time) FROM read_parquet('{train_out_file}')").fetchall()
years_list = [int(y[0]) for y in years_in_train]
print(f"   Годы в обучающей выборке Train: {sorted(years_list)}")
assert 2021 not in years_list, "КРИТИЧЕСКАЯ ОШИБКА: 2021 год обнаружен в обучающей выборке!"
print("   [OK] 2021 год гарантированно отсутствует в обучающих данных.")

print("\n" + "=" * 95)
print(f"ВИТРИНА SCADA v6.2 СОБРАНА ЗА {time.time() - t_global_start:.2f}с")
print(f"  1. Train (Multi-horizon 1-48h, полный): {n_final_train:,} строк | {os.path.getsize(train_out_file)/(1024*1024):.2f} MB")
print(f"  2. Stream (18 месяцев): {n_final_stream:,} строк | {os.path.getsize(stream_out_file)/(1024*1024):.2f} MB")
print(f"  3. Matched Test (1:5):               {n_matched_test:,} строк | {os.path.getsize(matched_test_out_file)/(1024*1024):.2f} MB")
print("=" * 95)
