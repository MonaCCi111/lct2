"""Малые реальные примеры API для проверки фронтенда без Parquet в браузере."""

import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "integration" / "backend_sanya" / "data" / "handoff_v1"
OUTPUT = ROOT / "integration" / "frontend_roma" / "fixtures_v1.json"


def record(con, table, where, args=()):
    row = con.execute(f"SELECT * FROM read_parquet(?) WHERE {where} LIMIT 1",
                      [str(DATA / (table + ".parquet")), *args]).fetchone()
    if row is None:
        raise ValueError(f"Нет примера {table}: {where}")
    columns = [item[0] for item in con.description]
    return dict(zip(columns, row))


def main():
    con = duckdb.connect()
    draft_id = "observed:OBSERVED_PUMP_FLOODED_STATUS:5333:20250202T030222"
    draft = record(con, "draft_cards", "draft_id=?", [draft_id])
    group = record(con, "group_cards", "group_id=?", [draft["group_id"]])
    channel = record(con, "channel_current", "channel_id=?", [draft["channel_id"]])
    channel_history = record(con, "observation_snapshots", "channel_id=? ORDER BY snapshot_date DESC",
                             [draft["channel_id"]])
    situation = record(con, "situation_cards", "situation_id=?", [draft["situation_id"]])
    evidence = record(con, "situation_evidence", "situation_id=?", [draft["situation_id"]])
    forecast = record(con, "draft_cards",
                      "group_id='review_v2:5003:20251210T090000' AND basis_kind='forecast' ORDER BY draft_id")
    assert forecast["score"] is not None and forecast["model_version"]
    assert forecast["forecast_horizon_hours"] is not None
    forecast_source = ROOT / "integration" / "backend_sanya" / "data" / "dispatch_review_v2" / "diagnostic_2025_2026"
    forecast_evidence = con.execute(
        "SELECT * FROM read_parquet(?) WHERE draft_id=? ORDER BY event_time LIMIT 1",
        [str(forecast_source / "forecast_evidence.parquet"), forecast["draft_id"]]).fetchone()
    assert forecast_evidence is not None
    evidence_columns = [item[0] for item in con.description]
    forecast_evidence = dict(zip(evidence_columns, forecast_evidence))
    feature = con.execute("SELECT feature_snapshot FROM read_parquet(?) WHERE draft_id=?",
                          [str(forecast_source / "forecast_features.parquet"),
                           forecast["draft_id"]]).fetchone()
    assert feature is not None
    forecast["feature_snapshot"] = json.loads(feature[0])
    object_row = con.execute('SELECT "ид_объект","диспетчерское_название_объекта",'
                             '"вид_объекта","родитель" FROM read_csv(?) WHERE "ид_объект"=?',
                             [str(ROOT / "integration" / "backend_sanya" / "data" / "catalog"
                                  / "справочник_объектов_диспетчер.csv"),
                              draft["object_id"]]).fetchone()
    assert object_row is not None
    channel_count = con.execute("SELECT count(*) FROM read_parquet(?) WHERE object_id=?",
                                [str(DATA / "channel_current.parquet"), draft["object_id"]]).fetchone()[0]
    object_sample = {"object_id": object_row[0], "object_name": object_row[1],
                     "kind": object_row[2], "parent_id": object_row[3],
                     "channel_count": channel_count}
    unknown = record(con, "channel_current", "NOT in_catalog")
    fire = json.loads((DATA / "fire_history_view.json").read_text(encoding="utf-8"))
    examples = {
        "contract_version": "dispatcher_api_v1",
        "note": "Реальные исторические поля. review_state=pending – продуктовая проекция исходного draft; решений человека нет.",
        "GET /api/v2/meta": {
            "contract_version": "dispatcher_api_v1", "data_version": "ml_handoff_v1",
            "data_cutoff": "2026-06-30T23:59:59", "source_timezone_known": False,
            "real_feedback_available": False, "live_ingestion_available": False,
        },
        "GET /api/v2/channels/{channel_id}": {**channel, "history": [channel_history]},
        "GET /api/v2/objects/{object_id}": object_sample,
        "GET /api/v2/channels?in_catalog=false": {"items": [unknown], "next_cursor": None},
        "GET /api/v2/situations/{situation_id}": situation,
        "GET /api/v2/situations/{situation_id}/evidence": {"items": [evidence], "next_cursor": None},
        "GET /api/v2/groups/{group_id}": {**group, "drafts": [{**draft, "review_state": "pending", "decision": None}]},
        "GET /api/v2/drafts/{draft_id}": {**draft, "review_state": "pending", "decision": None},
        "GET /api/v2/drafts?basis_kind=forecast": {
            "items": [{**forecast, "review_state": "pending", "decision": None}],
            "next_cursor": None,
        },
        "GET /api/v2/drafts/{forecast_draft_id}/evidence": {
            "items": [forecast_evidence], "next_cursor": None,
        },
        "GET /api/v2/fire-history": {"source_status": fire["display_state"],
                                      "real_fire_count": fire["real_fire_count"],
                                      "smoke_signal_statistics_are_fires": fire["smoke_signal_statistics_are_fires"],
                                      "smoke_signal_statistics": fire["smoke_signal_statistics"]},
    }
    OUTPUT.write_text(json.dumps(examples, ensure_ascii=False, indent=2,
                                 default=lambda value: value.isoformat()) + "\n",
                      encoding="utf-8")
    print(f"fixtures: {OUTPUT}, observed={draft_id}, forecast={forecast['draft_id']}")
    con.close()


if __name__ == "__main__":
    main()
