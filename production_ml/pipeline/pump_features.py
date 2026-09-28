"""Простые почасовые признаки каналов состояния насоса."""

PUMP_STATUSES = (
    "Выключен",
    "Включен",
    "Норма",
    "Неопределен",
    "Неисправен",
    "Обесточен",
    "Работают все насосы в АНС",
    "Затоплен",
    "Отключено устройство",
)

FEATURES = (
    "event_count_1h",
    "event_count_24h",
    "status_changes_1h",
    "status_changes_24h",
    "status_changes_72h",
    "rapid_status_changes_24h",
    "fast_change_fraction_24h",
    "on_events_24h",
    "on_event_fraction_24h",
    "off_events_24h",
    "off_event_fraction_24h",
    "undefined_events_24h",
    "undefined_event_fraction_24h",
    "observed_hours_72h",
)


def event_and_feature_sql(journal_files, channels_csv):
    sources = ",".join(f"'{path.as_posix()}'" for path in journal_files)
    return f"""
    CREATE TABLE pump_events AS
    SELECT j.event_id,j.channel_id,j.event_time,j.is_alarm,j.sensor_value
    FROM read_parquet([{sources}]) j
    JOIN read_csv('{channels_csv.as_posix()}',header=true) c
      ON j.channel_id=c."ид_канала_данных"
    WHERE c."тип_датчика"='Состояние насоса';

    CREATE TABLE ordered_pump_events AS
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
    FROM pump_events;

    CREATE TABLE pump_hourly AS
    SELECT channel_id,date_trunc('hour',event_time) hour_bin,
           count(*)::INTEGER events_1h,
           count(*) FILTER(WHERE sensor_value IS DISTINCT FROM previous_value)::INTEGER changes_1h,
           count(*) FILTER(WHERE sensor_value IS DISTINCT FROM previous_value
                             AND epoch(event_time-previous_time)<=2)::INTEGER rapid_changes_1h,
           count(*) FILTER(WHERE sensor_value='Включен')::INTEGER on_1h,
           count(*) FILTER(WHERE sensor_value='Выключен')::INTEGER off_1h,
           count(*) FILTER(WHERE sensor_value='Неопределен')::INTEGER undefined_1h,
           arg_max(sensor_value,struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) current_status,
           arg_max(is_alarm,struct_pack(t:=event_time,e:=event_id,v:=sensor_value,a:=is_alarm)) last_is_alarm
    FROM ordered_pump_events
    GROUP BY 1,2;

    CREATE TABLE pump_features AS
    WITH rolling AS (
        SELECT channel_id,hour_bin,events_1h,changes_1h,current_status,last_is_alarm,
               sum(events_1h) OVER w24 event_count_24h,
               sum(changes_1h) OVER w24 status_changes_24h,
               sum(changes_1h) OVER w72 status_changes_72h,
               sum(rapid_changes_1h) OVER w24 rapid_status_changes_24h,
               sum(on_1h) OVER w24 on_events_24h,
               sum(off_1h) OVER w24 off_events_24h,
               sum(undefined_1h) OVER w24 undefined_events_24h,
               count(*) OVER w72 observed_hours_72h
        FROM pump_hourly
        WINDOW w24 AS (
                   PARTITION BY channel_id ORDER BY hour_bin
                   RANGE BETWEEN INTERVAL 23 HOUR PRECEDING AND CURRENT ROW
               ),
               w72 AS (
                   PARTITION BY channel_id ORDER BY hour_bin
                   RANGE BETWEEN INTERVAL 71 HOUR PRECEDING AND CURRENT ROW
               )
    )
    SELECT channel_id,hour_bin+INTERVAL 1 HOUR obs_time,current_status,last_is_alarm,
           events_1h event_count_1h,event_count_24h,
           changes_1h status_changes_1h,status_changes_24h,status_changes_72h,
           rapid_status_changes_24h,
           CASE WHEN status_changes_24h>0
                THEN rapid_status_changes_24h::DOUBLE/status_changes_24h ELSE 0 END fast_change_fraction_24h,
           on_events_24h,
           CASE WHEN event_count_24h>0
                THEN on_events_24h::DOUBLE/event_count_24h ELSE 0 END on_event_fraction_24h,
           off_events_24h,
           CASE WHEN event_count_24h>0
                THEN off_events_24h::DOUBLE/event_count_24h ELSE 0 END off_event_fraction_24h,
           undefined_events_24h,
           CASE WHEN event_count_24h>0
                THEN undefined_events_24h::DOUBLE/event_count_24h ELSE 0 END undefined_event_fraction_24h,
           observed_hours_72h
    FROM rolling;
    """
