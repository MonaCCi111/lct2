"""Финальная сквозная проверка выпущенного ML/data-контракта."""

import json
import sys
from pathlib import Path

import duckdb


BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "production_ml" / "data"
HANDOFF = DATA / "handoff_v1"
SCENARIOS = BASE / "production_ml" / "pipeline" / "replay_scenarios_v1.json"
DECISIONS = BASE / "production_ml" / "pipeline" / "model_type_decisions.json"


def source(name):
    return f"read_parquet('{(HANDOFF / (name + '.parquet')).as_posix()}')"


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect()
    channels, drafts, groups, situations = map(
        source, ("channel_current", "draft_cards", "group_cards", "situation_cards")
    )
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))["types"]
    assert len(decisions) == 19
    assert len({item["sensor_type"] for item in decisions}) == 19
    by_type = con.execute(f"""
        SELECT sensor_type, forecast_capability, count(*)
        FROM {channels} WHERE in_catalog GROUP BY 1,2 ORDER BY 1
    """).fetchall()
    assert {row[0] for row in by_type} == {item["sensor_type"] for item in decisions}
    actual = {(name, capability): count for name, capability, count in by_type}
    for item in decisions:
        assert (item["sensor_type"], item["forecast_capability"]) in actual
        assert item["forecast_reason_text"]
    assert one(con, f"SELECT count(*) FROM {channels} WHERE NOT in_catalog AND forecast_capability!='not_assessed'") == 0
    assert one(con, f"SELECT count(*) FROM {channels} WHERE forecast_capability!='active' AND forecast_reason_text IS NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} WHERE basis_kind='forecast' AND model_version NOT IN ('power_phase_scada_v2','pump_scada_v1')") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} WHERE basis_kind='observed_status' AND situation_id IS NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} WHERE its_value IS NOT NULL") == 0
    assert one(con, f"SELECT count(*) FROM {channels} WHERE its_value IS NOT NULL") == 0
    assert one(con, f"SELECT count(*) FROM {situations} WHERE confirmed_physical_incident IS NOT NULL") == 0
    assert one(con, f"SELECT count(*) FROM {situations} WHERE multi_channel_campaign AND draft_id IS NOT NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} d LEFT JOIN {channels} c USING(channel_id) WHERE c.channel_id IS NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} d LEFT JOIN {groups} g USING(group_id) WHERE g.group_id IS NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} d WHERE basis_kind='observed_status' AND NOT EXISTS (SELECT 1 FROM {situations} s WHERE s.situation_id=d.situation_id)") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} WHERE basis_kind='forecast' AND source_ref IS NULL") == 0
    assert one(con, f"SELECT count(*) FROM {drafts} WHERE basis_kind='observed_status' AND source_ref IS NULL") == 0
    by_basis = con.execute(f"SELECT basis_kind, count(*) FROM {drafts} GROUP BY 1 ORDER BY 1").fetchall()
    peak = con.execute(f"""
        SELECT CAST(available_at AS DATE) AS calendar_day, count(*) AS group_count,
               sum(draft_count) AS draft_count, count(DISTINCT object_id) AS object_count
        FROM {groups} GROUP BY 1 ORDER BY group_count DESC, draft_count DESC, calendar_day LIMIT 5
    """).fetchall()
    largest = con.execute(f"""
        SELECT group_id, object_id, draft_count, source_first_obs_time,
               source_last_obs_time FROM {groups}
        ORDER BY draft_count DESC, group_id LIMIT 3
    """).fetchall()
    peak_objects = con.execute(f"""
        SELECT object_id, count(*) AS group_count, sum(draft_count) AS draft_count
        FROM {groups} WHERE CAST(available_at AS DATE)=DATE '2026-03-13'
        GROUP BY 1 ORDER BY group_count DESC, draft_count DESC, object_id
    """).fetchall()
    assert peak[0][:4] == (peak[0][0], 13, 15, 9)
    assert peak_objects[0] == (5675, 2, 4)
    assert one(con, f"SELECT count(*) FROM {groups} WHERE draft_count>1") > 0
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    scenario_rows = []
    for item in scenarios:
        folder = DATA / "replay_v1" / item["id"]
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        timeline = f"read_parquet('{(folder / 'timeline.parquet').as_posix()}')"
        rows = con.execute(f"SELECT event_kind,count(*) FROM {timeline} GROUP BY 1 ORDER BY 1").fetchall()
        kinds = dict(rows)
        assert kinds.get("reading", 0) > 0
        assert item["object_id"] == manifest["object_id"]
        assert one(con, f"SELECT count(*) FROM {timeline} WHERE object_id!={item['object_id']}") == 0
        if item["id"] == "peak_queue_object":
            assert kinds.get("draft_created") == 4
        scenario_rows.append({"id": item["id"], "object_id": item["object_id"], "kinds": kinds})
    fire = json.loads((HANDOFF / "fire_history_view.json").read_text(encoding="utf-8"))
    feedback = json.loads((HANDOFF / "feedback_availability.json").read_text(encoding="utf-8"))
    assert fire["real_fire_count"] is None
    assert feedback["decision_counts"] is None
    report = {
        "type_channels": [{"type": n, "capability": c, "channels": k} for n, c, k in by_type],
        "uncatalogued_channels": one(con, f"SELECT count(*) FROM {channels} WHERE NOT in_catalog"),
        "drafts_by_basis": dict(by_basis),
        "groups": one(con, f"SELECT count(*) FROM {groups}"),
        "peak_days": [{"day": str(d), "groups": g, "drafts": n, "objects": o} for d, g, n, o in peak],
        "largest_groups": [{"group_id": g, "object_id": o, "drafts": n, "first": str(a), "last": str(b)} for g, o, n, a, b in largest],
        "peak_2026_03_13_objects": [{"object_id": o, "groups": g, "drafts": n} for o, g, n in peak_objects],
        "scenarios": scenario_rows,
        "confirmed_fires": fire["real_fire_count"],
        "real_dispatcher_decisions": feedback["decision_counts"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    con.close()


if __name__ == "__main__":
    main()
