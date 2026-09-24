"""Эпизоды SCADA с явным восстановлением для состояния фазы."""

FAILURE_STATUSES = ("Обесточен", "Неисправен", "Отключено устройство")
RECOVERY_STATUSES = ("Есть питание", "Норма", "Включен")


def episode_sql():
    failures = ",".join(f"'{x}'" for x in FAILURE_STATUSES)
    recoveries = ",".join(f"'{x}'" for x in RECOVERY_STATUSES)
    return f"""
    CREATE TABLE explicit_states AS
    SELECT event_id,channel_id,event_time,sensor_value,
           CASE WHEN sensor_value IN ({failures}) THEN 'FAILURE'
                WHEN sensor_value IN ({recoveries}) THEN 'RECOVERY' END state
    FROM phase_events
    WHERE sensor_value IN ({failures},{recoveries});

    CREATE TABLE state_transitions AS
    WITH previous AS (
        SELECT *,lag(state) OVER (
            PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value
        ) previous_state
        FROM explicit_states
    )
    SELECT *,CASE WHEN state='FAILURE' AND (previous_state IS NULL OR previous_state!='FAILURE')
                  THEN 1 ELSE 0 END begins_episode
    FROM previous;

    CREATE TABLE episode_starts AS
    SELECT *,sum(begins_episode) OVER (
        PARTITION BY channel_id ORDER BY event_time,event_id,sensor_value
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) episode_id
    FROM state_transitions;

    CREATE TABLE episodes AS
    SELECT channel_id,episode_id,
           first(event_id ORDER BY event_time,event_id,sensor_value) FILTER(WHERE begins_episode=1) start_event_id,
           min(event_time) FILTER(WHERE begins_episode=1) episode_start,
           first(sensor_value ORDER BY event_time,event_id,sensor_value) FILTER(WHERE begins_episode=1) first_status,
           min(event_time) FILTER(WHERE state='RECOVERY') recovery_time,
           first(event_id ORDER BY event_time,event_id,sensor_value) FILTER(WHERE state='RECOVERY') recovery_event_id,
           first(sensor_value ORDER BY event_time,event_id,sensor_value) FILTER(WHERE state='RECOVERY') recovery_status
    FROM episode_starts
    WHERE episode_id>0
    GROUP BY channel_id,episode_id;
    """
