"""Фиксированная политика заявок, выбранная по периоду 2024 года."""

import json
from datetime import timedelta
from pathlib import Path


def load_policy(path=None):
    if path is None:
        path = Path(__file__).resolve().parents[1] / "models" / "power_phase_scada_v1" / "policy.json"
    return json.loads(path.read_text(encoding="utf-8"))


def select_alerts(scored_rows, policy):
    """scored_rows: (channel_id, obs_time, score) по времени; внутри часа по баллу."""
    last_ticket = {}
    daily_count = {}
    chosen = []
    limit = policy["daily_ticket_limit"]
    cooldown = timedelta(hours=policy["channel_cooldown_hours"])
    threshold = policy["score_threshold"]
    for channel_id, obs_time, score in scored_rows:
        if score < threshold:
            continue
        day = obs_time.date()
        if daily_count.get(day, 0) >= limit:
            continue
        if channel_id in last_ticket and obs_time < last_ticket[channel_id] + cooldown:
            continue
        chosen.append((len(chosen), channel_id, obs_time, float(score)))
        daily_count[day] = daily_count.get(day, 0) + 1
        last_ticket[channel_id] = obs_time
    return chosen, daily_count
