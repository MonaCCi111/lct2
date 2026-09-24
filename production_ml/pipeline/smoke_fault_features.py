"""Простые признаки неисправности дымового датчика."""

FEATURES = (
    "event_count_1h", "event_count_24h", "event_count_72h",
    "normal_events_24h", "undefined_events_24h", "smoke_alarm_events_24h",
    "normal_fraction_24h", "undefined_fraction_24h", "smoke_alarm_fraction_24h",
    "status_diversity_1h", "observed_hours_72h",
)


def feature_sql(journals, channels):
    sources=",".join(f"'{p.as_posix()}'" for p in journals)
    return f"""
    CREATE TABLE smoke_fault_events AS
    SELECT j.event_id,j.channel_id,j.event_time,j.is_alarm,j.sensor_value
    FROM read_parquet([{sources}]) j
    JOIN read_csv('{channels.as_posix()}',header=true) c
      ON j.channel_id=c."ид_канала_данных"
    WHERE c."тип_датчика"='Датчик дыма';

    CREATE TABLE smoke_fault_times AS
    SELECT channel_id,event_time,
           bool_and(is_alarm) all_alarm,bool_or(is_alarm) any_alarm,
           bool_or(sensor_value='Неисправен' AND is_alarm) fault_alarm,
           bool_or(sensor_value IN ('Норма','Дыма нет') AND NOT is_alarm) explicit_good
    FROM smoke_fault_events GROUP BY 1,2;

    CREATE TABLE smoke_fault_clear_events AS
    SELECT e.* FROM smoke_fault_events e
    JOIN smoke_fault_times t USING(channel_id,event_time)
    WHERE t.all_alarm=t.any_alarm;

    CREATE TABLE smoke_fault_states AS
    SELECT channel_id,event_time,
           CASE WHEN fault_alarm THEN 1 WHEN explicit_good THEN 0 END state
    FROM smoke_fault_times
    WHERE all_alarm=any_alarm AND (fault_alarm OR explicit_good);

    CREATE TABLE smoke_fault_hourly AS
    SELECT channel_id,date_trunc('hour',event_time) hour_bin,
           count(*)::INTEGER events_1h,
           count(*) FILTER(WHERE sensor_value='Норма')::INTEGER normal_1h,
           count(*) FILTER(WHERE sensor_value='Неопределен')::INTEGER undefined_1h,
           count(*) FILTER(WHERE sensor_value='Обнаружен дым' AND is_alarm)::INTEGER smoke_alarm_1h,
           count(DISTINCT sensor_value)::INTEGER diversity_1h
    FROM smoke_fault_clear_events GROUP BY 1,2;

    CREATE TABLE smoke_fault_features AS
    WITH rolling AS (
        SELECT channel_id,hour_bin,events_1h,diversity_1h,
               sum(events_1h) OVER w24 event_count_24h,
               sum(events_1h) OVER w72 event_count_72h,
               sum(normal_1h) OVER w24 normal_events_24h,
               sum(undefined_1h) OVER w24 undefined_events_24h,
               sum(smoke_alarm_1h) OVER w24 smoke_alarm_events_24h,
               count(*) OVER w72 observed_hours_72h
        FROM smoke_fault_hourly
        WINDOW w24 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW),
               w72 AS (PARTITION BY channel_id ORDER BY hour_bin
                       RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW)
    )
    SELECT channel_id,hour_bin+INTERVAL 1 HOUR obs_time,
           events_1h event_count_1h,event_count_24h,event_count_72h,
           normal_events_24h,undefined_events_24h,smoke_alarm_events_24h,
           normal_events_24h::DOUBLE/event_count_24h normal_fraction_24h,
           undefined_events_24h::DOUBLE/event_count_24h undefined_fraction_24h,
           smoke_alarm_events_24h::DOUBLE/event_count_24h smoke_alarm_fraction_24h,
           diversity_1h status_diversity_1h,observed_hours_72h
    FROM rolling;
    """
