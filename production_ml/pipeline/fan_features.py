"""Почасовые признаки однозначных состояний вентилятора."""

FEATURES = (
    "event_count_1h", "event_count_24h", "event_count_72h",
    "on_events_24h", "off_events_24h", "normal_events_24h",
    "undefined_events_24h", "on_fraction_24h", "off_fraction_24h",
    "undefined_fraction_24h", "observed_hours_72h",
)


def event_and_feature_sql(journal_files, channels_csv):
    sources = ",".join(f"'{path.as_posix()}'" for path in journal_files)
    return f"""
    CREATE TABLE fan_events AS
    SELECT j.event_id,j.channel_id,j.event_time,j.is_alarm,j.sensor_value
    FROM read_parquet([{sources}]) j
    JOIN read_csv('{channels_csv.as_posix()}',header=true) c
      ON j.channel_id=c."ид_канала_данных"
    WHERE c."тип_датчика"='Состояние вентилятора';

    CREATE TABLE fan_times AS
    SELECT channel_id,event_time,bool_and(is_alarm) all_alarm,
           bool_or(is_alarm) any_alarm
    FROM fan_events GROUP BY 1,2;

    CREATE TABLE fan_clear_times AS
    SELECT channel_id,event_time,all_alarm is_alarm
    FROM fan_times WHERE all_alarm=any_alarm;

    CREATE TABLE fan_clear_events AS
    SELECT e.* FROM fan_events e
    JOIN fan_clear_times t USING(channel_id,event_time);

    CREATE TABLE fan_hourly AS
    SELECT channel_id,date_trunc('hour',event_time) hour_bin,
           count(*)::INTEGER events_1h,
           count(*) FILTER(WHERE sensor_value='Включен')::INTEGER on_1h,
           count(*) FILTER(WHERE sensor_value='Выключен')::INTEGER off_1h,
           count(*) FILTER(WHERE sensor_value='Норма')::INTEGER normal_1h,
           count(*) FILTER(WHERE sensor_value='Неопределен')::INTEGER undefined_1h,
           arg_max(is_alarm,struct_pack(t:=event_time,e:=event_id,v:=sensor_value)) last_is_alarm
    FROM fan_clear_events GROUP BY 1,2;

    CREATE TABLE fan_features AS
    WITH rolling AS (
        SELECT channel_id,hour_bin,events_1h,last_is_alarm,
               sum(events_1h) OVER w24 event_count_24h,
               sum(events_1h) OVER w72 event_count_72h,
               sum(on_1h) OVER w24 on_events_24h,
               sum(off_1h) OVER w24 off_events_24h,
               sum(normal_1h) OVER w24 normal_events_24h,
               sum(undefined_1h) OVER w24 undefined_events_24h,
               count(*) OVER w72 observed_hours_72h
        FROM fan_hourly
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
           events_1h event_count_1h,event_count_24h,event_count_72h,
           on_events_24h,off_events_24h,normal_events_24h,undefined_events_24h,
           on_events_24h::DOUBLE/event_count_24h on_fraction_24h,
           off_events_24h::DOUBLE/event_count_24h off_fraction_24h,
           undefined_events_24h::DOUBLE/event_count_24h undefined_fraction_24h,
           observed_hours_72h
    FROM rolling;
    """
