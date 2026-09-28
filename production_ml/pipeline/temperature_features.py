"""Простые почасовые признаки температурных каналов."""

FEATURES = (
    "event_count_1h",
    "event_count_24h",
    "numeric_count_1h",
    "numeric_count_24h",
    "numeric_mean_1h",
    "numeric_mean_24h",
    "numeric_min_24h",
    "numeric_max_24h",
    "numeric_range_24h",
    "numeric_last_72h",
    "value_changes_24h",
    "status_events_24h",
    "undefined_events_24h",
    "numeric_fraction_24h",
    "observed_hours_72h",
)


def event_and_feature_sql(journal_files, channels_csv):
    sources = ",".join(f"'{path.as_posix()}'" for path in journal_files)
    return f"""
    CREATE TABLE temperature_events AS
    SELECT j.event_id,j.channel_id,j.event_time,j.is_alarm,j.sensor_value,
           try_cast(replace(j.sensor_value,',','.') AS DOUBLE) numeric_value
    FROM read_parquet([{sources}]) j
    JOIN read_csv('{channels_csv.as_posix()}',header=true) c
      ON j.channel_id=c."ид_канала_данных"
    WHERE c."тип_датчика"='Датчик температуры';

    CREATE TABLE ordered_temperature_events AS
    SELECT *,
           lag(sensor_value) OVER (
               PARTITION BY channel_id
               ORDER BY event_time,event_id,sensor_value,is_alarm
           ) previous_value,
           lag(is_alarm) OVER (
               PARTITION BY channel_id
               ORDER BY event_time,event_id,sensor_value,is_alarm
           ) previous_is_alarm,
           lag(event_time) OVER (
               PARTITION BY channel_id
               ORDER BY event_time,event_id,sensor_value,is_alarm
           ) previous_time
    FROM temperature_events;

    CREATE TABLE temperature_hourly AS
    SELECT channel_id,date_trunc('hour',event_time) hour_bin,
           count(*)::INTEGER events_1h,
           count(numeric_value)::INTEGER numeric_1h,
           sum(numeric_value) numeric_sum_1h,
           avg(numeric_value) numeric_mean_1h,
           min(numeric_value) numeric_min_1h,
           max(numeric_value) numeric_max_1h,
           arg_max(numeric_value,struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm))
             FILTER(WHERE numeric_value IS NOT NULL) numeric_last_1h,
           count(*) FILTER(WHERE sensor_value IS DISTINCT FROM previous_value)::INTEGER changes_1h,
           count(*) FILTER(WHERE numeric_value IS NULL)::INTEGER status_1h,
           count(*) FILTER(WHERE sensor_value IN ('Неопределен','Не определено'))::INTEGER undefined_1h,
           arg_max(is_alarm,struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) last_is_alarm
    FROM ordered_temperature_events
    GROUP BY 1,2;

    CREATE TABLE temperature_features AS
    WITH rolling AS (
        SELECT channel_id,hour_bin,events_1h,numeric_1h,numeric_mean_1h,last_is_alarm,
               sum(events_1h) OVER w24 event_count_24h,
               sum(numeric_1h) OVER w24 numeric_count_24h,
               sum(numeric_sum_1h) OVER w24 numeric_sum_24h,
               min(numeric_min_1h) OVER w24 numeric_min_24h,
               max(numeric_max_1h) OVER w24 numeric_max_24h,
               last_value(numeric_last_1h IGNORE NULLS) OVER w72 numeric_last_72h,
               sum(changes_1h) OVER w24 value_changes_24h,
               sum(status_1h) OVER w24 status_events_24h,
               sum(undefined_1h) OVER w24 undefined_events_24h,
               count(*) OVER w72 observed_hours_72h
        FROM temperature_hourly
        WINDOW w24 AS (
                   PARTITION BY channel_id ORDER BY hour_bin
                   RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW
               ),
               w72 AS (
                   PARTITION BY channel_id ORDER BY hour_bin
                   RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW
               )
    )
    SELECT channel_id,hour_bin+INTERVAL 1 HOUR obs_time,last_is_alarm,
           events_1h event_count_1h,event_count_24h,
           numeric_1h numeric_count_1h,numeric_count_24h,numeric_mean_1h,
           CASE WHEN numeric_count_24h>0 THEN numeric_sum_24h/numeric_count_24h END numeric_mean_24h,
           numeric_min_24h,numeric_max_24h,
           numeric_max_24h-numeric_min_24h numeric_range_24h,
           numeric_last_72h,value_changes_24h,status_events_24h,undefined_events_24h,
           CASE WHEN event_count_24h>0 THEN numeric_count_24h::DOUBLE/event_count_24h ELSE 0 END numeric_fraction_24h,
           observed_hours_72h
    FROM rolling;
    """
