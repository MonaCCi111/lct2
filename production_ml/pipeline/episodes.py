"""Автоматические эпизоды SCADA для трёх типов POWER_PHASE."""

from .features import SENSORS


def failure_events_sql(journal_files, channels_csv):
    sources = ",".join(f"'{path.as_posix()}'" for path in journal_files)
    sensor_sql = ",".join(f"'{sensor}'" for sensor in SENSORS)
    return f"""
    WITH source_events AS (
        SELECT j.channel_id, c."тип_датчика" AS sensor_type,
               j.event_id, j.event_time, j.sensor_value
        FROM read_parquet([{sources}]) j
        JOIN read_csv('{channels_csv.as_posix()}', header=true) c
          ON j.channel_id = c."ид_канала_данных"
        WHERE c."тип_датчика" IN ({sensor_sql})
    ), reasons AS (
        SELECT channel_id, sensor_type, event_id, event_time,
               sensor_value AS trigger_value,
               CASE
                   WHEN sensor_value IN ('Неисправен','Обесточен','Затоплен')
                        THEN 'TEXT_FAIL'
                   WHEN sensor_value IN ('-100','255','-3276','-127')
                        THEN 'ERROR_CODE'
                   ELSE NULL
               END AS fail_reason
        FROM source_events
    )
    SELECT channel_id, sensor_type, event_id, event_time, trigger_value, fail_reason
    FROM reasons WHERE fail_reason IS NOT NULL
    """


def episodes_sql():
    return """
    WITH ordered AS (
        SELECT *, LAG(event_time) OVER (
            PARTITION BY channel_id ORDER BY event_time, event_id
        ) AS prev_time
        FROM failure_events
    ), boundaries AS (
        SELECT *, CASE WHEN prev_time IS NULL
                           OR epoch(event_time - prev_time) > 48 * 3600
                       THEN 1 ELSE 0 END AS begins_episode
        FROM ordered
    ), grouped AS (
        SELECT *, SUM(begins_episode) OVER (
            PARTITION BY channel_id ORDER BY event_time, event_id
        ) AS episode_id
        FROM boundaries
    )
    SELECT channel_id, sensor_type, episode_id,
           MIN(event_time) AS episode_start,
           MAX(event_time) AS last_failure_event,
           COUNT(*) AS failure_event_count,
           FIRST(fail_reason ORDER BY event_time,event_id) AS first_reason,
           FIRST(trigger_value ORDER BY event_time,event_id) AS first_status
    FROM grouped
    GROUP BY channel_id,sensor_type,episode_id
    """
