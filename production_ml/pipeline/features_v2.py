"""Признаки фазы напрямую из упорядоченных событий всех лет."""

FEATURES = (
    "event_count_1h", "event_count_24h", "status_changes_1h",
    "status_changes_24h", "status_changes_72h", "rapid_status_changes_24h",
    "fast_change_fraction_24h", "alarm_events_24h", "alarm_event_fraction_24h",
    "undefined_events_24h", "undefined_event_fraction_24h", "observed_hours_72h",
)


def event_and_feature_sql(journal_files, channels_csv):
    sources = ",".join(f"'{path.as_posix()}'" for path in journal_files)
    return f"""
    CREATE TABLE phase_events AS
    SELECT j.event_id,j.channel_id,j.event_time,j.is_alarm,j.sensor_value
    FROM read_parquet([{sources}]) j
    JOIN read_csv('{channels_csv.as_posix()}',header=true) c
      ON j.channel_id=c."ид_канала_данных"
    WHERE c."тип_датчика"='Состояние фазы';

    CREATE TABLE ordered_events AS
    SELECT *,
           lag(sensor_value) OVER (
               PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value,is_alarm
           ) previous_value,
           lag(event_time) OVER (
               PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value,is_alarm
           ) previous_time
    FROM phase_events;

    CREATE TABLE hourly AS
    SELECT channel_id,date_trunc('hour',event_time) hour_bin,
           count(*)::INTEGER events_1h,
           count(*) FILTER (WHERE previous_value IS NOT NULL
                              AND sensor_value IS DISTINCT FROM previous_value)::INTEGER flips_1h,
           count(*) FILTER (WHERE previous_value IS NOT NULL
                              AND sensor_value IS DISTINCT FROM previous_value
                              AND epoch(event_time-previous_time)<=2)::INTEGER sub2s_flips_1h,
           count(*) FILTER (WHERE is_alarm)::INTEGER alarm_1h,
           count(*) FILTER (WHERE sensor_value IN ('Неопределен','Не определено'))::INTEGER undef_1h
    FROM ordered_events GROUP BY 1,2;

    CREATE TABLE features AS
    WITH rolling AS (
        SELECT channel_id,hour_bin,events_1h,
               sum(events_1h) OVER w24 event_count_24h,
               flips_1h,
               sum(flips_1h) OVER w24 status_changes_24h,
               sum(flips_1h) OVER w72 status_changes_72h,
               sum(sub2s_flips_1h) OVER w24 rapid_status_changes_24h,
               sum(alarm_1h) OVER w24 alarm_events_24h,
               sum(undef_1h) OVER w24 undefined_events_24h,
               count(*) OVER w72 observed_hours_72h
        FROM hourly
        WINDOW w24 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
               w72 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW)
    )
    SELECT channel_id,'Состояние фазы' sensor_type,hour_bin+INTERVAL 1 HOUR obs_time,
           events_1h event_count_1h,event_count_24h,flips_1h status_changes_1h,
           status_changes_24h,status_changes_72h,rapid_status_changes_24h,
           CASE WHEN status_changes_24h>0 THEN rapid_status_changes_24h::DOUBLE/status_changes_24h ELSE 0 END fast_change_fraction_24h,
           alarm_events_24h,
           CASE WHEN event_count_24h>0 THEN alarm_events_24h::DOUBLE/event_count_24h ELSE 0 END alarm_event_fraction_24h,
           undefined_events_24h,
           CASE WHEN event_count_24h>0 THEN undefined_events_24h::DOUBLE/event_count_24h ELSE 0 END undefined_event_fraction_24h,
           observed_hours_72h
    FROM rolling;
    """
