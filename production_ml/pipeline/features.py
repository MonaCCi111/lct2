"""Почасовые признаки POWER_PHASE с буквальным смыслом названий."""

SENSORS = ("Состояние фазы",)
FEATURES = (
    "event_count_1h",
    "event_count_24h",
    "status_changes_1h",
    "status_changes_24h",
    "status_changes_72h",
    "rapid_status_changes_24h",
    "fast_change_fraction_24h",
    "alarm_events_24h",
    "alarm_event_fraction_24h",
    "undefined_events_24h",
    "undefined_event_fraction_24h",
    "observed_hours_72h",
)


def feature_sql(hourly_files):
    sources = ",".join(f"'{path.as_posix()}'" for path in hourly_files)
    sensor_sql = ",".join(f"'{sensor}'" for sensor in SENSORS)
    return f"""
    WITH hourly AS (
        SELECT channel_id, sensor_type, hour_bin, events_1h, flips_1h,
               sub2s_flips_1h, alarm_1h, undef_1h
        FROM read_parquet([{sources}])
        WHERE sensor_type IN ({sensor_sql})
    ), sums AS (
        SELECT channel_id, sensor_type, hour_bin,
               events_1h AS event_count_1h,
               SUM(events_1h) OVER w24 AS event_count_24h,
               flips_1h AS status_changes_1h,
               SUM(flips_1h) OVER w24 AS status_changes_24h,
               SUM(flips_1h) OVER w72 AS status_changes_72h,
               SUM(sub2s_flips_1h) OVER w24 AS rapid_status_changes_24h,
               SUM(alarm_1h) OVER w24 AS alarm_events_24h,
               SUM(undef_1h) OVER w24 AS undefined_events_24h,
               COUNT(*) OVER w72 AS observed_hours_72h
        FROM hourly
        WINDOW w24 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
               w72 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW)
    )
    SELECT channel_id, sensor_type, hour_bin + INTERVAL 1 HOUR AS obs_time,
           event_count_1h, event_count_24h,
           status_changes_1h, status_changes_24h, status_changes_72h,
           rapid_status_changes_24h,
           CASE WHEN status_changes_24h > 0
                THEN rapid_status_changes_24h::DOUBLE / status_changes_24h
                ELSE 0.0 END AS fast_change_fraction_24h,
           alarm_events_24h,
           CASE WHEN event_count_24h > 0
                THEN alarm_events_24h::DOUBLE / event_count_24h
                ELSE 0.0 END AS alarm_event_fraction_24h,
           undefined_events_24h,
           CASE WHEN event_count_24h > 0
                THEN undefined_events_24h::DOUBLE / event_count_24h
                ELSE 0.0 END AS undefined_event_fraction_24h,
           observed_hours_72h
    FROM sums
    """
