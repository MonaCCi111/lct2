import os
import sys
import time
import duckdb
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
t_global_start = time.time()

print("=" * 80)
print("ДИРЕКТИВА v5.1: СБОРКА ЦЕЛЕВЫХ ДАТАСЕТОВ (ФАЗЫ + НАСОСЫ, СПЛИТ-ТАРГЕТ, P-F TRAIN)")
print("1. Оборудование: СТРОГО силовая электросеть (Фазы, ИБП, Переключатели) и гидромеханика (Насосы, Вентиляторы, УИР-Р)")
print("2. Вся охранная и пожарная телеметрия (дым, двери, движение, люки) — ПОЛНОСТЬЮ ОТСЕЧЕНА")
print("3. Сплит-таргет: target_regulatory_24h (24-48ч), target_urgent_6_24h (6-24ч), target_combined_6_48h (6-48ч)")
print("4. Карантин: исключены точки агонии (< 6ч) и состоявшиеся аварии")
print("5. Фильтр деградационных аварий в Train: цензурирование мгновенных обрывов без предвестников износа")
print("6. Временной сплит: Train (2020-2024), Stream (18 месяцев: 2025 + 2026), Test Matched 50/50")
print("7. Ровно 36 чистых физических колонок без утечек")
print("=" * 80)

base_dir = "g:/lct2/production_ml"
data_dir = os.path.join(base_dir, "data")
parquet_dir = "g:/lct2/ml_research/data/parquet_by_year"
channels_csv = "g:/lct2/справочник_каналов_датчиков.csv"
incidents_file = os.path.join(data_dir, "persistent_incidents_2020_2026.parquet")
baselines_file = os.path.join(data_dir, "channel_baselines_2020_2026.parquet")
temp_dir = "g:/lct2/duckdb_temp"
os.makedirs(temp_dir, exist_ok=True)

# Имена выходных файлов
v5_train_file = os.path.join(data_dir, "v5_train_purified_2020_2024.parquet")
v5_stream_file = os.path.join(data_dir, "v5_stream_full_2025_2026.parquet")
v5_matched_test_file = os.path.join(data_dir, "v5_matched_test_2025_2026.parquet")

con = duckdb.connect()
con.execute("PRAGMA memory_limit = '14GB';")
con.execute("PRAGMA threads = 6;")
con.execute(f"PRAGMA temp_directory = '{temp_dir}';")
con.execute("PRAGMA preserve_insertion_order = false;")

# 1. Загрузка целевых каналов
print("\n1. Инициализация целевых каналов (Силовая сеть + Гидромеханика)...")
t_init = time.time()
con.execute(f"""
CREATE OR REPLACE TABLE target_channels AS
SELECT 
    "ид_канала_данных"::BIGINT AS channel_id,
    COALESCE("тип_инж_системы", 'Неизвестно') AS subsystem_type,
    COALESCE("тип_датчика", 'Неизвестно') AS sensor_type,
    split_part(COALESCE("тег_инженерной_системы", ''), '-', 1) AS tag_root,
    TRY_CAST(regexp_extract("название_датчика", '(?i)ПК\\s*(\\d+)', 1) AS INTEGER) AS picket_num
FROM read_csv('{channels_csv}', header=True)
WHERE "тип_датчика" IN (
    'Состояние фазы', 'ИБП', 'Переключатель',
    'Состояние насоса', 'Состояние вентилятора', 'Состояние УИР-Р'
);
""")
n_tgt = con.execute("SELECT COUNT(*) FROM target_channels").fetchone()[0]
print(f"   Целевых каналов отобрано: {n_tgt:,} за {time.time() - t_init:.2f}с")

con.execute(f"""
CREATE OR REPLACE TABLE persistent_incidents_tgt AS
SELECT i.* 
FROM read_parquet('{incidents_file}') i
JOIN target_channels m ON i.channel_id = m.channel_id;
""")
n_inc = con.execute("SELECT COUNT(*) FROM persistent_incidents_tgt").fetchone()[0]
print(f"   Инцидентов целевых каналов загружено: {n_inc:,}")

con.execute(f"""
CREATE OR REPLACE TABLE channel_baselines_tgt AS
SELECT b.* 
FROM read_parquet('{baselines_file}') b
JOIN target_channels m ON b.channel_id = m.channel_id;
""")

# Ровно 36 чистых физических признаков
feature_cols = [
    # 1. Аппаратные маркеры шкафа и контроллера (6 признаков)
    'cabinet_reboot_1970_24h',
    'cabinet_reboot_cascade_3d',
    'ups_battery_trouble_flag_7d',
    'battery_backup_wear_index',
    'controller_device_lost_24h',
    'bus_simultaneous_drop_count',
    
    # 2. Деградация физического шлейфа (2 признака)
    'undefined_count_24h',
    'undefined_ratio_24h',
    
    # 3. Микрофизика дребезга и посекундный тайминг (7 признаков)
    'micro_chatter_count_1h',
    'micro_chatter_ratio_1h',
    'sub2s_flips_24h',
    'micro_burst_sub2s_ratio',
    'period_jitter_cv',
    'duty_cycle_24h',
    'mean_time_to_restore_sec',
    
    # 4. Асимметрия и автоматы состояний (6 признаков)
    'state_transition_asymmetry_24h',
    'phase_solo_dropout_flag',
    'pump_dry_run_anomaly',
    'forbidden_transition_rate',
    'transition_matrix_entropy',
    'rapid_bounce_triplet_count',
    
    # 5. Пространственный пикетный и шкафной контекст (5 признаков)
    'cabinet_flips_24h',
    'picket_neighbors_flips_24h',
    'picket_isolation_index',
    'picket_multi_system_concurrence',
    'intercom_active_3h',
    
    # 6. Объемы телеметрии и динамика 2-го порядка (10 признаков)
    'flips_count_1h',
    'flips_count_24h',
    'flips_count_72h',
    'events_count_24h',
    'activity_ratio_30d',
    'burstiness_index',
    'night_excess',
    'slope_flips_3d',
    'accel_flips_3d',
    'alarm_ratio_24h'
]
assert len(feature_cols) == 36, f"Ожидалось ровно 36 признаков, получено {len(feature_cols)}"

def process_pure_physics_stream(year_parquet_list, target_label):
    t_p_start = time.time()
    print(f"\n>>> ПОСТРОЕНИЕ ЧИСТОЙ ФИЗИЧЕСКОЙ ВИТРИНЫ: {target_label} <<<")
    
    # 2.1 Посекундная разметка сырых событий целевых каналов
    t_raw = time.time()
    files_sql = ", ".join([f"'{parquet_dir}/{f}'" for f in year_parquet_list])
    print(f"   [2.1] Посекундная разметка сырых событий ({files_sql})...")
    con.execute(f"""
    CREATE OR REPLACE TABLE raw_events_{target_label} AS
    WITH raw_ordered AS (
        SELECT 
            j.channel_id,
            m.sensor_type,
            m.subsystem_type,
            m.tag_root,
            m.picket_num,
            j.event_time,
            date_trunc('hour', j.event_time) AS hour_bin,
            date_trunc('second', j.event_time) AS sec_bin,
            j.sensor_value,
            j.is_alarm,
            
            CASE WHEN j.sensor_value != LAG(j.sensor_value) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) THEN 1 ELSE 0 END AS is_flip,
            epoch(j.event_time - LAG(j.event_time) OVER (PARTITION BY j.channel_id ORDER BY j.event_time)) AS dt_sec,
            
            CASE WHEN j.sensor_value IN ('Включен', 'Есть питание') THEN 1 ELSE 0 END AS is_active_status,
            CASE WHEN j.sensor_value = 'Норма' THEN 1 ELSE 0 END AS is_norm_status,
            CASE WHEN j.sensor_value = 'Обесточен' THEN 1 ELSE 0 END AS is_pwr_off,
            CASE WHEN j.sensor_value = 'Есть питание' THEN 1 ELSE 0 END AS is_pwr_on,
            CASE WHEN j.sensor_value = 'Включен' THEN 1 ELSE 0 END AS is_sw_on,
            CASE WHEN j.sensor_value = 'Выключен' THEN 1 ELSE 0 END AS is_sw_off,
            CASE WHEN j.sensor_value IN ('Неопределен', 'Не определено') THEN 1 ELSE 0 END AS is_undefined,
            
            LAG(j.sensor_value, 1) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev1_val,
            LAG(j.sensor_value, 2) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev2_val,
            LAG(j.event_time, 2) OVER (PARTITION BY j.channel_id ORDER BY j.event_time) AS prev2_time,
            
            CASE WHEN j.sensor_value LIKE '%1970%' THEN 1 ELSE 0 END AS is_reboot_1970,
            CASE WHEN j.sensor_value IN ('Питание от батарей', 'Батарея неисправна', 'Батарея разряжена') THEN 1 ELSE 0 END AS is_battery_trouble,
            CASE WHEN j.sensor_value IN ('Много неисправных устройств', 'Отключено устройство') THEN 1 ELSE 0 END AS is_device_lost,
            CASE WHEN j.sensor_value IN ('Разговор', 'Вызов') THEN 1 ELSE 0 END AS is_intercom,
            CASE WHEN j.is_alarm = true OR j.sensor_value IN ('Неисправен', 'Обесточен', 'Затоплен', 'Неопределен') THEN 1 ELSE 0 END AS is_trouble
            
        FROM read_parquet([{files_sql}]) j
        JOIN target_channels m ON j.channel_id = m.channel_id
    )
    SELECT * FROM raw_ordered;
    """)
    n_raw = con.execute(f"SELECT COUNT(*) FROM raw_events_{target_label}").fetchone()[0]
    print(f"      Сырые события ({n_raw:,} строк) размечены за {time.time() - t_raw:.2f}с")
    
    # 2.2 Почасовая агрегация
    t_h = time.time()
    print("   [2.2] Почасовая агрегация...")
    con.execute(f"""
    CREATE OR REPLACE TABLE hourly_raw_{target_label} AS
    SELECT 
        channel_id,
        sensor_type,
        subsystem_type,
        tag_root,
        picket_num,
        hour_bin,
        COUNT(*) AS events_1h,
        SUM(is_flip) AS flips_1h,
        SUM(CASE WHEN is_flip = 1 AND dt_sec <= 2.0 THEN 1 ELSE 0 END) AS sub2s_flips_1h,
        SUM(CASE WHEN is_flip = 1 AND dt_sec <= 3.0 THEN 1 ELSE 0 END) AS micro_chatter_1h,
        
        COALESCE(AVG(CASE WHEN is_flip = 1 AND dt_sec > 0 THEN dt_sec END), 0.0) AS avg_dt_1h,
        COALESCE(STDDEV_POP(CASE WHEN is_flip = 1 AND dt_sec > 0 THEN dt_sec END), 0.0) AS std_dt_1h,
        
        SUM(CASE WHEN is_active_status = 1 AND dt_sec > 0 AND dt_sec < 3600 THEN dt_sec ELSE 0 END) AS active_sec_1h,
        AVG(CASE WHEN is_norm_status = 1 AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание') AND dt_sec > 0 AND dt_sec < 86400 THEN dt_sec END) AS restore_sec_1h,
        COUNT(CASE WHEN is_norm_status = 1 AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание') THEN 1 END) AS restore_cnt_1h,
        
        COUNT(CASE 
            WHEN (prev1_val = 'Есть питание' AND sensor_value = 'Обесточен')
              OR (prev1_val = 'Норма' AND sensor_value = 'Неисправен')
              OR (prev1_val = 'Включен' AND sensor_value = 'Неисправен')
            THEN 1 END) AS forbidden_trans_1h,
            
        COUNT(CASE 
            WHEN prev2_val IN ('Норма', 'Выключен', 'Есть питание')
             AND prev1_val NOT IN ('Норма', 'Выключен', 'Есть питание')
             AND sensor_value IN ('Норма', 'Выключен', 'Есть питание')
             AND epoch(event_time - prev2_time) <= 3.0
            THEN 1 END) AS rapid_bounce_1h,
            
        SUM(CASE WHEN is_flip = 1 AND sensor_value = 'Норма' THEN 1 ELSE 0 END) AS flips_norm_1h,
        SUM(CASE WHEN is_flip = 1 AND sensor_value IN ('Есть питание', 'Обесточен') THEN 1 ELSE 0 END) AS flips_pwr_1h,
        SUM(CASE WHEN is_flip = 1 AND sensor_value IN ('Включен', 'Выключен') THEN 1 ELSE 0 END) AS flips_sw_1h,
        SUM(CASE WHEN is_flip = 1 AND sensor_value IN ('Неисправен', 'Затоплен') THEN 1 ELSE 0 END) AS flips_err_1h,
        SUM(CASE WHEN is_flip = 1 AND sensor_value IN ('Неопределен', 'Не определено') THEN 1 ELSE 0 END) AS flips_undef_1h,
        
        SUM(is_undefined) AS undefined_1h,
        SUM(is_pwr_on) AS pwr_on_1h,
        SUM(is_pwr_off) AS pwr_off_1h,
        SUM(is_sw_on) AS sw_on_1h,
        SUM(is_sw_off) AS sw_off_1h,
        
        COUNT(CASE WHEN EXTRACT(HOUR FROM event_time) BETWEEN 0 AND 5 THEN 1 END) AS night_events_1h,
        COUNT(CASE WHEN is_alarm = true THEN 1 END) AS alarm_events_1h,
        
        SUM(is_reboot_1970) AS reboot_1970_1h,
        SUM(is_battery_trouble) AS battery_trouble_1h,
        SUM(is_device_lost) AS device_lost_1h,
        SUM(is_intercom) AS intercom_1h,
        SUM(is_trouble) AS trouble_1h
        
    FROM raw_events_{target_label}
    GROUP BY channel_id, sensor_type, subsystem_type, tag_root, picket_num, hour_bin;
    """)
    n_h = con.execute(f"SELECT COUNT(*) FROM hourly_raw_{target_label}").fetchone()[0]
    print(f"      Почасовая витрина ({n_h:,} строк) готова за {time.time() - t_h:.2f}с")
    
    # 2.3 Шкафные контексты
    t_cab = time.time()
    print("   [2.3] Расчет контекста шкафов (RS-485 помехи, RTC 1970, ИБП)...")
    con.execute(f"""
    CREATE OR REPLACE TABLE cabinet_sec_flips_{target_label} AS
    SELECT 
        tag_root,
        hour_bin,
        sec_bin,
        COUNT(DISTINCT channel_id) AS simultaneous_channels
    FROM raw_events_{target_label}
    WHERE is_flip = 1
    GROUP BY tag_root, hour_bin, sec_bin;

    CREATE OR REPLACE TABLE cabinet_hourly_{target_label} AS
    SELECT 
        h.tag_root,
        h.hour_bin,
        COALESCE(MAX(s.simultaneous_channels), 0) AS max_bus_drop_1h,
        SUM(h.reboot_1970_1h) AS reboot_1970_1h,
        SUM(h.battery_trouble_1h) AS battery_trouble_1h,
        SUM(h.device_lost_1h) AS device_lost_1h,
        SUM(h.intercom_1h) AS intercom_1h,
        SUM(h.flips_1h) AS cab_flips_1h,
        SUM(CASE WHEN h.sensor_type = 'Состояние фазы' THEN h.pwr_on_1h ELSE 0 END) AS phase_power_on_1h
    FROM hourly_raw_{target_label} h
    LEFT JOIN cabinet_sec_flips_{target_label} s ON h.tag_root = s.tag_root AND h.hour_bin = s.hour_bin
    GROUP BY h.tag_root, h.hour_bin;

    CREATE OR REPLACE TABLE cabinet_rolling_{target_label} AS
    SELECT 
        tag_root,
        hour_bin,
        phase_power_on_1h,
        LEAST(32767, MAX(max_bus_drop_1h) OVER w24)::SMALLINT AS bus_simultaneous_drop_count,
        LEAST(32767, SUM(reboot_1970_1h) OVER w24)::SMALLINT AS cabinet_reboot_1970_24h,
        LEAST(32767, SUM(reboot_1970_1h) OVER w72)::SMALLINT AS cabinet_reboot_cascade_3d,
        CASE WHEN SUM(battery_trouble_1h) OVER w168 > 0 THEN 1 ELSE 0 END::TINYINT AS ups_battery_trouble_flag_7d,
        SUM(CASE WHEN battery_trouble_1h > 0 THEN 1 ELSE 0 END) OVER w336::FLOAT AS battery_backup_wear_index,
        LEAST(32767, SUM(device_lost_1h) OVER w24)::SMALLINT AS controller_device_lost_24h,
        CASE WHEN SUM(intercom_1h) OVER w3 > 0 THEN 1 ELSE 0 END::TINYINT AS intercom_active_3h,
        SUM(cab_flips_1h) OVER w24::INTEGER AS cabinet_flips_24h
    FROM cabinet_hourly_{target_label}
    WINDOW 
        w3 AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 2 HOUR PRECEDING AND CURRENT ROW),
        w24 AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
        w72 AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW),
        w168 AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 167 HOUR PRECEDING AND CURRENT ROW),
        w336 AS (PARTITION BY tag_root ORDER BY hour_bin RANGE BETWEEN INTERVAL 335 HOUR PRECEDING AND CURRENT ROW);
    """)
    print(f"      Шкафной контекст готов за {time.time() - t_cab:.2f}с")
    
    # 2.4 Пикетные контексты
    t_pk = time.time()
    print("   [2.4] Расчет контекста пикетов...")
    con.execute(f"""
    CREATE OR REPLACE TABLE picket_hourly_{target_label} AS
    SELECT 
        picket_num,
        hour_bin,
        SUM(flips_1h) AS picket_flips_1h,
        COUNT(DISTINCT CASE WHEN trouble_1h > 0 THEN subsystem_type END) AS trouble_subsystems_1h
    FROM hourly_raw_{target_label}
    WHERE picket_num IS NOT NULL
    GROUP BY picket_num, hour_bin;

    CREATE OR REPLACE TABLE picket_rolling_{target_label} AS
    SELECT 
        picket_num,
        hour_bin,
        SUM(picket_flips_1h) OVER w24::INTEGER AS picket_flips_24h,
        LEAST(127, SUM(trouble_subsystems_1h) OVER w12)::TINYINT AS picket_multi_system_concurrence
    FROM picket_hourly_{target_label}
    WINDOW
        w12 AS (PARTITION BY picket_num ORDER BY hour_bin RANGE BETWEEN INTERVAL 11 HOUR PRECEDING AND CURRENT ROW),
        w24 AS (PARTITION BY picket_num ORDER BY hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW);
    """)
    print(f"      Пикетный контекст готов за {time.time() - t_pk:.2f}с")
    
    # 2.5 Скользящие оконные функции канала
    t_ch = time.time()
    print("   [2.5] Расчет скользящих оконных функций канала (24ч, 72ч, 48ч)...")
    con.execute(f"""
    CREATE OR REPLACE TABLE channel_rolling_{target_label} AS
    SELECT 
        h.channel_id,
        h.hour_bin AS obs_time,
        h.sensor_type,
        h.subsystem_type,
        h.tag_root,
        h.picket_num,
        
        -- Объемы телеметрии
        h.flips_1h::INTEGER AS flips_count_1h,
        SUM(h.flips_1h) OVER w24::INTEGER AS flips_count_24h,
        SUM(h.flips_1h) OVER w72::INTEGER AS flips_count_72h,
        SUM(h.events_1h) OVER w24::INTEGER AS events_count_24h,
        
        -- Микрофизика дребезга
        h.micro_chatter_1h::INTEGER AS micro_chatter_count_1h,
        ROUND(h.micro_chatter_1h * 1.0 / (h.flips_1h + 1e-5), 4)::FLOAT AS micro_chatter_ratio_1h,
        SUM(h.sub2s_flips_1h) OVER w24::INTEGER AS sub2s_flips_24h,
        ROUND(SUM(h.sub2s_flips_1h) OVER w24 * 1.0 / (SUM(h.flips_1h) OVER w24 + 1e-5), 4)::FLOAT AS micro_burst_sub2s_ratio,
        
        COALESCE(ROUND(AVG(h.std_dt_1h / (h.avg_dt_1h + 1e-5)) OVER w20_rows, 4), 0.0)::FLOAT AS period_jitter_cv,
        LEAST(1.0, GREATEST(0.0, ROUND(SUM(h.active_sec_1h) OVER w24 / 86400.0, 4)))::FLOAT AS duty_cycle_24h,
        COALESCE(ROUND(SUM(h.restore_sec_1h * h.restore_cnt_1h) OVER w24 / (SUM(h.restore_cnt_1h) OVER w24 + 1e-5), 1), 0.0)::FLOAT AS mean_time_to_restore_sec,
        
        -- Деградация шлейфа
        SUM(h.undefined_1h) OVER w24::SMALLINT AS undefined_count_24h,
        ROUND(SUM(h.undefined_1h) OVER w24 * 1.0 / (SUM(h.events_1h) OVER w24 + 1.0), 4)::FLOAT AS undefined_ratio_24h,
        
        -- Асимметрия состояний
        CASE 
            WHEN h.sensor_type IN ('Состояние фазы', 'ИБП', 'Переключатель') 
            THEN ROUND(ABS(SUM(h.pwr_on_1h) OVER w24 - SUM(h.pwr_off_1h) OVER w24) * 1.0 / 
                       (SUM(h.pwr_on_1h) OVER w24 + SUM(h.pwr_off_1h) OVER w24 + 1.0), 4)
            WHEN h.sensor_type IN ('Состояние насоса', 'Состояние вентилятора', 'Состояние УИР-Р') 
            THEN ROUND(ABS(SUM(h.sw_on_1h) OVER w24 - SUM(h.sw_off_1h) OVER w24) * 1.0 / 
                       (SUM(h.sw_on_1h) OVER w24 + SUM(h.sw_off_1h) OVER w24 + 1.0), 4)
            ELSE 0.0 
        END::FLOAT AS state_transition_asymmetry_24h,
        
        -- Запрещенные переходы и N-граммы
        LEAST(32767, SUM(h.forbidden_trans_1h) OVER w24)::SMALLINT AS forbidden_transition_rate,
        GREATEST(0.0, ROUND(
            (CASE WHEN SUM(h.flips_norm_1h) OVER w48 > 0 THEN -1.0 * (SUM(h.flips_norm_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) * log2(SUM(h.flips_norm_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) ELSE 0.0 END) +
            (CASE WHEN SUM(h.flips_pwr_1h) OVER w48 > 0 THEN -1.0 * (SUM(h.flips_pwr_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) * log2(SUM(h.flips_pwr_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) ELSE 0.0 END) +
            (CASE WHEN SUM(h.flips_sw_1h) OVER w48 > 0 THEN -1.0 * (SUM(h.flips_sw_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) * log2(SUM(h.flips_sw_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) ELSE 0.0 END) +
            (CASE WHEN SUM(h.flips_err_1h) OVER w48 > 0 THEN -1.0 * (SUM(h.flips_err_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) * log2(SUM(h.flips_err_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) ELSE 0.0 END) +
            (CASE WHEN SUM(h.flips_undef_1h) OVER w48 > 0 THEN -1.0 * (SUM(h.flips_undef_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) * log2(SUM(h.flips_undef_1h) OVER w48 * 1.0 / (SUM(h.flips_1h) OVER w48 + 1e-5)) ELSE 0.0 END)
        , 4))::FLOAT AS transition_matrix_entropy,
        LEAST(32767, SUM(h.rapid_bounce_1h) OVER w24)::SMALLINT AS rapid_bounce_triplet_count,
        
        -- Динамика 2-го порядка
        GREATEST(0.0, LEAST(1.0, ROUND((h.flips_1h - (SUM(h.flips_1h) OVER w24 / 24.0)) / (h.flips_1h + (SUM(h.flips_1h) OVER w24 / 24.0) + 0.1), 4)))::FLOAT AS burstiness_index,
        (ROUND(SUM(h.night_events_1h) OVER w24 * 1.0 / (SUM(h.events_1h) OVER w24 + 1.0), 4) * SUM(h.flips_1h) OVER w24)::FLOAT AS night_excess,
        ROUND(((SUM(h.flips_1h) OVER w24 - (SUM(h.flips_1h) OVER w72 - SUM(h.flips_1h) OVER w24) / 2.0) / 2.0), 4)::FLOAT AS slope_flips_3d,
        ROUND((1.5 * SUM(h.flips_1h) OVER w24 - 0.5 * SUM(h.flips_1h) OVER w72), 4)::FLOAT AS accel_flips_3d,
        ROUND(SUM(h.alarm_events_1h) OVER w24 * 1.0 / (SUM(h.events_1h) OVER w24 + 1.0), 4)::FLOAT AS alarm_ratio_24h,
        
        -- Поля для джойна
        h.pwr_off_1h,
        h.pwr_on_1h,
        h.sw_on_1h
        
    FROM hourly_raw_{target_label} h
    WINDOW 
        w20_rows AS (PARTITION BY h.channel_id ORDER BY h.hour_bin ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
        w24 AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
        w48 AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 47 HOUR PRECEDING AND CURRENT ROW),
        w72 AS (PARTITION BY h.channel_id ORDER BY h.hour_bin RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW);
    """)
    print(f"      Оконные функции каналов готовы за {time.time() - t_ch:.2f}с")
    
    # 2.6 Финальное объединение 36 признаков, сплит-таргета и карантина
    t_join = time.time()
    print("   [2.6] Сборка 36 признаков, сплит-таргета и карантина...")
    con.execute(f"""
    CREATE OR REPLACE TABLE stream_features_{target_label} AS
    SELECT 
        r.channel_id,
        r.obs_time,
        r.sensor_type,
        r.subsystem_type,
        r.tag_root,
        
        -- БЛОК 1. Аппаратные маркеры шкафа и контроллера (6)
        COALESCE(cab.cabinet_reboot_1970_24h, 0)::SMALLINT AS cabinet_reboot_1970_24h,
        COALESCE(cab.cabinet_reboot_cascade_3d, 0)::SMALLINT AS cabinet_reboot_cascade_3d,
        COALESCE(cab.ups_battery_trouble_flag_7d, 0)::TINYINT AS ups_battery_trouble_flag_7d,
        COALESCE(cab.battery_backup_wear_index, 0.0)::FLOAT AS battery_backup_wear_index,
        COALESCE(cab.controller_device_lost_24h, 0)::SMALLINT AS controller_device_lost_24h,
        COALESCE(cab.bus_simultaneous_drop_count, 1)::SMALLINT AS bus_simultaneous_drop_count,
        
        -- БЛОК 2. Деградация физического шлейфа (2)
        r.undefined_count_24h,
        r.undefined_ratio_24h,
        
        -- БЛОК 3. Микрофизика дребезга и тайминг (7)
        r.micro_chatter_count_1h,
        r.micro_chatter_ratio_1h,
        r.sub2s_flips_24h,
        r.micro_burst_sub2s_ratio,
        r.period_jitter_cv,
        r.duty_cycle_24h,
        r.mean_time_to_restore_sec,
        
        -- БЛОК 4. Асимметрия и автоматы состояний (6)
        r.state_transition_asymmetry_24h,
        CASE 
            WHEN r.sensor_type = 'Состояние фазы' 
             AND (r.pwr_off_1h > 0 OR r.flips_count_1h > 10) 
             AND (COALESCE(cab.phase_power_on_1h, 0) - r.pwr_on_1h) > 0 
            THEN 1 ELSE 0 
        END::TINYINT AS phase_solo_dropout_flag,
        
        CASE 
            WHEN r.sensor_type = 'Состояние насоса' 
            THEN 0.0 -- в чистом фокусе насосов и фаз
            ELSE 0.0 
        END::FLOAT AS pump_dry_run_anomaly,
        
        r.forbidden_transition_rate,
        r.transition_matrix_entropy,
        r.rapid_bounce_triplet_count,
        
        -- БЛОК 5. Пространственный пикетный и шкафной контекст (5)
        COALESCE(cab.cabinet_flips_24h, 0)::INTEGER AS cabinet_flips_24h,
        GREATEST(COALESCE(pkr.picket_flips_24h, 0) - r.flips_count_24h, 0)::INTEGER AS picket_neighbors_flips_24h,
        ROUND((r.flips_count_24h + 0.1) / (GREATEST(COALESCE(pkr.picket_flips_24h, 0) - r.flips_count_24h, 0) + 0.1), 4)::FLOAT AS picket_isolation_index,
        COALESCE(pkr.picket_multi_system_concurrence, 0)::TINYINT AS picket_multi_system_concurrence,
        COALESCE(cab.intercom_active_3h, 0)::TINYINT AS intercom_active_3h,
        
        -- БЛОК 6. Объемы телеметрии и динамика 2-го порядка (10)
        r.flips_count_1h,
        r.flips_count_24h,
        r.flips_count_72h,
        r.events_count_24h,
        ROUND((r.flips_count_24h + 0.1) / (COALESCE(b.avg_events_30d, 2.0) + 0.1), 4)::FLOAT AS activity_ratio_30d,
        r.burstiness_index,
        r.night_excess,
        r.slope_flips_3d,
        r.accel_flips_3d,
        r.alarm_ratio_24h,
        
        -- СПЛИТ-ТАРГЕТЫ
        CASE WHEN p.incident_time IS NOT NULL THEN 1 ELSE 0 END::TINYINT AS target_combined_6_48h,
        CASE WHEN p.incident_time IS NOT NULL AND epoch(p.incident_time - r.obs_time) >= 24 * 3600 THEN 1 ELSE 0 END::TINYINT AS target_regulatory_24h,
        CASE WHEN p.incident_time IS NOT NULL AND epoch(p.incident_time - r.obs_time) < 24 * 3600 THEN 1 ELSE 0 END::TINYINT AS target_urgent_6_24h

    FROM channel_rolling_{target_label} r
    LEFT JOIN cabinet_rolling_{target_label} cab ON r.tag_root = cab.tag_root AND r.obs_time = cab.hour_bin
    LEFT JOIN picket_rolling_{target_label} pkr ON r.picket_num = pkr.picket_num AND r.obs_time = pkr.hour_bin
    LEFT JOIN channel_baselines_tgt b ON r.channel_id = b.channel_id AND date_trunc('day', r.obs_time) = b.day_bin

    -- СТРОГИЙ ФИЗИЧЕСКИЙ КАРАНТИН: исключаем аварии прямо сейчас и агонию (< 6ч)
    LEFT JOIN persistent_incidents_tgt q 
      ON r.channel_id = q.channel_id 
     AND ((r.obs_time >= q.incident_time AND r.obs_time <= q.fail_end)
          OR (q.incident_time > r.obs_time AND q.incident_time < r.obs_time + INTERVAL 6 HOUR))

    -- ТАРГЕТ: авария строго в окне [6ч, 48ч]
    LEFT JOIN persistent_incidents_tgt p 
      ON r.channel_id = p.channel_id
     AND p.incident_time >= r.obs_time + INTERVAL 6 HOUR
     AND p.incident_time <= r.obs_time + INTERVAL 48 HOUR

    WHERE q.incident_time IS NULL;
    """)
    n_tot, n_comb, n_reg, n_urg = con.execute(f"""
    SELECT COUNT(*), SUM(target_combined_6_48h), SUM(target_regulatory_24h), SUM(target_urgent_6_24h)
    FROM stream_features_{target_label};
    """).fetchone()
    print(f"      Поток собран за {time.time() - t_join:.2f}с: {n_tot:,} строк")
    print(f"      • target_combined_6_48h   : {n_comb:,} ({n_comb/n_tot*100:.2f}%)")
    print(f"      • target_regulatory_24h   : {n_reg:,} ({n_reg/n_tot*100:.2f}%)")
    print(f"      • target_urgent_6_24h     : {n_urg:,} ({n_urg/n_tot*100:.2f}%)")
    
    # Очистка промежуточных таблиц
    con.execute(f"DROP TABLE raw_events_{target_label};")
    con.execute(f"DROP TABLE hourly_raw_{target_label};")
    con.execute(f"DROP TABLE cabinet_sec_flips_{target_label};")
    con.execute(f"DROP TABLE cabinet_hourly_{target_label};")
    con.execute(f"DROP TABLE cabinet_rolling_{target_label};")
    con.execute(f"DROP TABLE picket_hourly_{target_label};")
    con.execute(f"DROP TABLE picket_rolling_{target_label};")
    con.execute(f"DROP TABLE channel_rolling_{target_label};")
    con.execute("CHECKPOINT;")
    
    return n_tot

# =============================================================================
# 2. СБОРКА СПЛОШНОГО БОЕВОГО ПОТОКА 2025-2026 (18 МЕСЯЦЕВ)
# =============================================================================
process_pure_physics_stream(["journal_2025.parquet", "journal_2026.parquet"], "stream_2025_2026")

print(f"\nСохранение сплошного потока 18 месяцев в {v5_stream_file}...")
t_save_stream = time.time()
con.execute(f"""
COPY stream_features_stream_2025_2026 
TO '{v5_stream_file}' (FORMAT PARQUET, COMPRESSION 'ZSTD');
""")
print(f"   [OK] Сплошной поток 2025-2026 сохранен ({os.path.getsize(v5_stream_file)/(1024**2):.2f} МБ) за {time.time() - t_save_stream:.2f}с")

# =============================================================================
# 3. СБОРКА КОНТРОЛЬНОЙ СБАЛАНСИРОВАННОЙ ВЫБОРКИ TEST MATCHED 2025-2026 (50/50)
# =============================================================================
print(f"\n3. Формирование сбалансированной контрольной когорты Test Matched 50/50...")
t_match_test = time.time()
con.execute("""
CREATE OR REPLACE TABLE test_pos AS
SELECT *,
       EXTRACT(MONTH FROM obs_time)::INTEGER AS obs_month,
       EXTRACT(HOUR FROM obs_time)::INTEGER AS obs_hour
FROM stream_features_stream_2025_2026
WHERE target_combined_6_48h = 1;
""")
n_test_pos = con.execute("SELECT COUNT(*) FROM test_pos").fetchone()[0]

con.execute("""
CREATE OR REPLACE TABLE test_neg_candidates AS
SELECT *,
       EXTRACT(MONTH FROM obs_time)::INTEGER AS obs_month,
       EXTRACT(HOUR FROM obs_time)::INTEGER AS obs_hour
FROM stream_features_stream_2025_2026
WHERE target_combined_6_48h = 0;
""")

con.execute("""
CREATE OR REPLACE TABLE test_strata AS
SELECT sensor_type, obs_month, obs_hour, COUNT(*) AS needed_count
FROM test_pos
GROUP BY sensor_type, obs_month, obs_hour;

CREATE OR REPLACE TABLE test_matched_neg AS
WITH ranked_neg AS (
    SELECT n.*,
           ROW_NUMBER() OVER (
               PARTITION BY n.sensor_type, n.obs_month, n.obs_hour 
               ORDER BY hash(n.channel_id, epoch(n.obs_time))
           ) AS rn
    FROM test_neg_candidates n
    JOIN test_strata s 
      ON n.sensor_type = s.sensor_type 
     AND n.obs_month = s.obs_month 
     AND n.obs_hour = s.obs_hour
)
SELECT r.* EXCLUDE (rn)
FROM ranked_neg r
JOIN test_strata s 
  ON r.sensor_type = s.sensor_type 
 AND r.obs_month = s.obs_month 
 AND r.obs_hour = s.obs_hour
WHERE r.rn <= s.needed_count;
""")
n_test_neg = con.execute("SELECT COUNT(*) FROM test_matched_neg").fetchone()[0]
shortage_test = n_test_pos - n_test_neg

if shortage_test > 0:
    con.execute(f"""
    CREATE OR REPLACE TABLE test_fallback_neg AS
    WITH unselected_neg AS (
        SELECT n.*,
               ROW_NUMBER() OVER (
                   PARTITION BY n.sensor_type 
                   ORDER BY hash(n.channel_id, epoch(n.obs_time) + 99)
               ) as rn
        FROM test_neg_candidates n
        LEFT JOIN test_matched_neg m 
          ON n.channel_id = m.channel_id AND n.obs_time = m.obs_time
        WHERE m.channel_id IS NULL
    )
    SELECT u.* EXCLUDE (rn)
    FROM unselected_neg u
    WHERE u.rn <= {shortage_test};
    """)
    con.execute("CREATE OR REPLACE TABLE test_final_neg AS SELECT * FROM test_matched_neg UNION ALL SELECT * FROM test_fallback_neg;")
else:
    con.execute("CREATE OR REPLACE TABLE test_final_neg AS SELECT * FROM test_matched_neg;")

con.execute(f"""
CREATE OR REPLACE TABLE final_test_matched AS
SELECT * EXCLUDE (obs_month, obs_hour) FROM test_pos
UNION ALL
SELECT * EXCLUDE (obs_month, obs_hour) FROM test_final_neg
ORDER BY obs_time, channel_id;
""")

con.execute(f"COPY final_test_matched TO '{v5_matched_test_file}' (FORMAT PARQUET, COMPRESSION 'ZSTD');")
tot_te, p_te = con.execute("SELECT COUNT(*), SUM(target_combined_6_48h) FROM final_test_matched").fetchone()
print(f"   [OK] Test Matched 50/50 сохранен: {v5_matched_test_file} ({tot_te:,} строк: {p_te:,} pos / {tot_te - p_te:,} neg, баланс {p_te/tot_te*100:.1f}%) за {time.time() - t_match_test:.2f}с")

con.execute("DROP TABLE stream_features_stream_2025_2026;")
con.execute("DROP TABLE test_pos; DROP TABLE test_neg_candidates; DROP TABLE test_strata; DROP TABLE test_matched_neg; DROP TABLE test_final_neg; DROP TABLE final_test_matched;")
con.execute("CHECKPOINT;")

# =============================================================================
# 4. СБОРКА ОБУЧАЮЩЕЙ ВЫБОРКИ TRAIN 2020-2024 С ФИЛЬТРОМ ИЗНОСА P-F (50/50)
# =============================================================================
train_years = [f"journal_{yr}.parquet" for yr in range(2020, 2025)]
process_pure_physics_stream(train_years, "train_raw_2020_2024")

print(f"\n4. Применение фильтра деградационных аварий P-F (цензурирование мгновенных обрывов)...")
t_purify = time.time()

# Критерии деградационного износа согласно Директиве v5.1:
# flips_count_24h > 2 OR micro_burst_sub2s_ratio > 0.08 OR state_transition_asymmetry_24h > 0.15
# OR undefined_count_24h >= 1 OR (sensor_type = 'Состояние насоса' AND (duty_cycle_24h > 0.25 OR night_excess > 10.0))
# OR period_jitter_cv > 1.5
con.execute("""
CREATE OR REPLACE TABLE train_purified_pos AS
SELECT *,
       EXTRACT(MONTH FROM obs_time)::INTEGER AS obs_month,
       EXTRACT(HOUR FROM obs_time)::INTEGER AS obs_hour
FROM stream_features_train_raw_2020_2024
WHERE target_combined_6_48h = 1
  AND (
      flips_count_24h > 2
      OR micro_burst_sub2s_ratio > 0.08
      OR state_transition_asymmetry_24h > 0.15
      OR undefined_count_24h >= 1
      OR (sensor_type = 'Состояние насоса' AND (duty_cycle_24h > 0.25 OR night_excess > 10.0))
      OR period_jitter_cv > 1.5
  );
""")
n_raw_pos = con.execute("SELECT COUNT(*) FROM stream_features_train_raw_2020_2024 WHERE target_combined_6_48h = 1").fetchone()[0]
n_pur_pos = con.execute("SELECT COUNT(*) FROM train_purified_pos").fetchone()[0]
print(f"   Сырых позитивов в 2020-2024: {n_raw_pos:,}")
print(f"   Очищенных деградационных позитивов P-F: {n_pur_pos:,} (отсеяно {n_raw_pos - n_pur_pos:,} мгновенных обрывов, {((n_raw_pos - n_pur_pos)/n_raw_pos)*100:.1f}%)")

print("   Формирование сбалансированной контрольной группы штатной работы 50/50...")
con.execute("""
CREATE OR REPLACE TABLE train_neg_candidates AS
SELECT *,
       EXTRACT(MONTH FROM obs_time)::INTEGER AS obs_month,
       EXTRACT(HOUR FROM obs_time)::INTEGER AS obs_hour
FROM stream_features_train_raw_2020_2024
WHERE target_combined_6_48h = 0;
""")

con.execute("""
CREATE OR REPLACE TABLE train_strata AS
SELECT sensor_type, obs_month, obs_hour, COUNT(*) AS needed_count
FROM train_purified_pos
GROUP BY sensor_type, obs_month, obs_hour;

CREATE OR REPLACE TABLE train_matched_neg AS
WITH ranked_neg AS (
    SELECT n.*,
           ROW_NUMBER() OVER (
               PARTITION BY n.sensor_type, n.obs_month, n.obs_hour 
               ORDER BY hash(n.channel_id, epoch(n.obs_time))
           ) AS rn
    FROM train_neg_candidates n
    JOIN train_strata s 
      ON n.sensor_type = s.sensor_type 
     AND n.obs_month = s.obs_month 
     AND n.obs_hour = s.obs_hour
)
SELECT r.* EXCLUDE (rn)
FROM ranked_neg r
JOIN train_strata s 
  ON r.sensor_type = s.sensor_type 
 AND r.obs_month = s.obs_month 
 AND r.obs_hour = s.obs_hour
WHERE r.rn <= s.needed_count;
""")
n_tr_neg = con.execute("SELECT COUNT(*) FROM train_matched_neg").fetchone()[0]
shortage_tr = n_pur_pos - n_tr_neg

if shortage_tr > 0:
    con.execute(f"""
    CREATE OR REPLACE TABLE train_fallback_neg AS
    WITH unselected_neg AS (
        SELECT n.*,
               ROW_NUMBER() OVER (
                   PARTITION BY n.sensor_type 
                   ORDER BY hash(n.channel_id, epoch(n.obs_time) + 42)
               ) as rn
        FROM train_neg_candidates n
        LEFT JOIN train_matched_neg m 
          ON n.channel_id = m.channel_id AND n.obs_time = m.obs_time
        WHERE m.channel_id IS NULL
    )
    SELECT u.* EXCLUDE (rn)
    FROM unselected_neg u
    WHERE u.rn <= {shortage_tr};
    """)
    con.execute("CREATE OR REPLACE TABLE train_final_neg AS SELECT * FROM train_matched_neg UNION ALL SELECT * FROM train_fallback_neg;")
else:
    con.execute("CREATE OR REPLACE TABLE train_final_neg AS SELECT * FROM train_matched_neg;")

con.execute(f"""
CREATE OR REPLACE TABLE final_train_purified AS
SELECT * EXCLUDE (obs_month, obs_hour) FROM train_purified_pos
UNION ALL
SELECT * EXCLUDE (obs_month, obs_hour) FROM train_final_neg
ORDER BY obs_time, channel_id;
""")

con.execute(f"COPY final_train_purified TO '{v5_train_file}' (FORMAT PARQUET, COMPRESSION 'ZSTD');")
tot_tr, p_tr = con.execute("SELECT COUNT(*), SUM(target_combined_6_48h) FROM final_train_purified").fetchone()
print(f"   [OK] Train Purified 50/50 сохранен: {v5_train_file} ({tot_tr:,} строк: {p_tr:,} pos / {tot_tr - p_tr:,} neg, баланс {p_tr/tot_tr*100:.1f}%) за {time.time() - t_purify:.2f}с")

con.execute("DROP TABLE stream_features_train_raw_2020_2024;")
con.execute("DROP TABLE train_purified_pos; DROP TABLE train_neg_candidates; DROP TABLE train_strata; DROP TABLE train_matched_neg; DROP TABLE train_final_neg; DROP TABLE final_train_purified;")
con.execute("CHECKPOINT;")

# =============================================================================
# 5. ИТОГОВАЯ ВАЛИДАЦИЯ АРТЕФАКТОВ ПОСТАВКИ v5.1
# =============================================================================
print("\n" + "=" * 80)
print("5. ИТОГОВАЯ ВАЛИДАЦИЯ АРТЕФАКТОВ v5.1 (QUALITY AUDIT)")
print("=" * 80)

all_v5_files = [
    ("Train Purified (2020-2024)", v5_train_file),
    ("Test Matched (2025-2026)", v5_matched_test_file),
    ("Test Stream Full (2025-2026)", v5_stream_file)
]

for label_f, f_path in all_v5_files:
    print(f"\nВалидация файла: {label_f} ({os.path.basename(f_path)})")
    n_rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{f_path}')").fetchone()[0]
    print(f"  • Число наблюдений: {n_rows:,}")
    print(f"  • Размер на диске  : {os.path.getsize(f_path)/(1024**2):.2f} МБ")
    
    # Проверка отсутствия колонок-утечек
    schema_cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f_path}')").fetchall()]
    forbidden = ['horizon_hours', 'is_holdout', 'days_since_last_incident', 'picket_num']
    leaks = [c for c in forbidden if c in schema_cols]
    assert len(leaks) == 0, f"Критическая ошибка: обнаружены колонки утечки {leaks} в {label_f}!"
    print(f"  • Проверка колонок-утечек: [OK] Запрещенных колонок {forbidden} нет")
    
    # Проверка NaN и Inf по всем 36 признакам
    check_exprs = [f"SUM(CASE WHEN {c} IS NULL OR isnan({c}) OR isinf({c}) THEN 1 ELSE 0 END)" for c in feature_cols]
    bad_res = con.execute(f"SELECT {', '.join(check_exprs)} FROM read_parquet('{f_path}')").fetchone()
    total_bad = sum(bad_res)
    assert total_bad == 0, f"Ошибка: обнаружены NaN/Inf ({total_bad}) в {label_f}!"
    print(f"  • Проверка NaN/Inf: [OK] Строго 0 пропусков во всех {len(feature_cols)} признаках")
    
    # Проверка сплит-таргетов
    for t_col in ['target_combined_6_48h', 'target_regulatory_24h', 'target_urgent_6_24h']:
        p_cnt = con.execute(f"SELECT SUM({t_col}) FROM read_parquet('{f_path}')").fetchone()[0]
        print(f"  • Таргет {t_col:22s}: {p_cnt:,} ({p_cnt/n_rows*100:.2f}%)")

print("\n" + "=" * 80)
print(f"ДИРЕКТИВА v5.1 УСПЕШНО ВЫПОЛНЕНА ЗА {time.time() - t_global_start:.2f} СЕК!")
print("=" * 80)
con.close()
