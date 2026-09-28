"""Эпизоды тревоги вентилятора после исключения конфликтных временных меток."""


def episode_sql():
    return """
    CREATE TABLE fan_ordered_times AS
    SELECT *,lag(is_alarm) OVER (
                  PARTITION BY channel_id ORDER BY event_time
              ) previous_is_alarm
    FROM fan_clear_times;

    CREATE TABLE fan_episode_starts AS
    SELECT channel_id,
           row_number() OVER (PARTITION BY channel_id ORDER BY event_time) episode_id,
           event_time episode_start
    FROM fan_ordered_times
    WHERE is_alarm AND previous_is_alarm=false;

    CREATE TABLE fan_recoveries AS
    SELECT channel_id,event_time recovery_time
    FROM fan_ordered_times WHERE NOT is_alarm;

    CREATE TABLE fan_episodes AS
    SELECT s.channel_id,s.episode_id,s.episode_start,r.recovery_time
    FROM fan_episode_starts s
    ASOF LEFT JOIN fan_recoveries r
      ON s.channel_id=r.channel_id AND s.episode_start<r.recovery_time;
    """
