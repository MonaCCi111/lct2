"""Однозначные эпизоды неисправности дымового датчика."""


def episode_sql():
    return """
    CREATE TABLE smoke_fault_ordered_states AS
    SELECT *,lag(state) OVER(PARTITION BY channel_id ORDER BY event_time) previous_state
    FROM smoke_fault_states;

    CREATE TABLE smoke_fault_starts AS
    SELECT channel_id,row_number() OVER(PARTITION BY channel_id ORDER BY event_time) episode_id,
           event_time episode_start
    FROM smoke_fault_ordered_states
    WHERE state=1 AND previous_state=0;

    CREATE TABLE smoke_fault_recoveries AS
    SELECT channel_id,event_time recovery_time
    FROM smoke_fault_states WHERE state=0;

    CREATE TABLE smoke_fault_episodes AS
    SELECT s.channel_id,s.episode_id,s.episode_start,r.recovery_time
    FROM smoke_fault_starts s
    ASOF LEFT JOIN smoke_fault_recoveries r
      ON s.channel_id=r.channel_id AND s.episode_start<r.recovery_time;
    """
