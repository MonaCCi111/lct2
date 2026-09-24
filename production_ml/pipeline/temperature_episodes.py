"""Эпизоды автоматической тревоги температурных каналов."""


def episode_sql():
    return """
    CREATE TABLE temperature_episode_starts AS
    SELECT channel_id,
           row_number() OVER (
               PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value
           ) episode_id,
           event_id start_event_id,event_time episode_start,sensor_value first_status
    FROM ordered_temperature_events
    WHERE is_alarm AND previous_is_alarm=false AND previous_time<event_time
      AND NOT EXISTS (
          SELECT 1
          FROM temperature_events same_time
          WHERE same_time.channel_id=ordered_temperature_events.channel_id
            AND same_time.event_time=ordered_temperature_events.event_time
            AND NOT same_time.is_alarm
      );

    CREATE TABLE temperature_recoveries AS
    SELECT channel_id,event_id recovery_event_id,event_time recovery_time,
           sensor_value recovery_status
    FROM ordered_temperature_events
    WHERE NOT is_alarm;

    CREATE TABLE temperature_episodes AS
    SELECT s.channel_id,s.episode_id,s.start_event_id,s.episode_start,s.first_status,
           r.recovery_time,r.recovery_event_id,r.recovery_status
    FROM temperature_episode_starts s
    ASOF LEFT JOIN temperature_recoveries r
      ON s.channel_id=r.channel_id AND s.episode_start<r.recovery_time;
    """
