"""Проверить реестр двух активных моделей и общий поток заявок."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.active import ACTIVE_MODELS, SUPPORTED_SENSOR_TYPES
from production_ml.pipeline.package_power_phase_v2 import verify_bundle as verify_phase
from production_ml.pipeline.package_pump import verify_bundle as verify_pump


EXPECTED_COLUMNS = (
    "ticket_id",
    "channel_id",
    "obs_time",
    "score",
    "model_version",
    "forecast_horizon_hours",
    "target_kind",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "production_ml" / "models" / "active_model.json").read_text(
            encoding="utf-8"
        )
    )
    verify_phase(ACTIVE_MODELS["power_phase_scada_v2"]["bundle"])
    verify_pump(ACTIVE_MODELS["pump_scada_v1"]["bundle"])
    manifest_versions = tuple(
        item["version"] for item in manifest["active_models"]
    )
    code_versions = tuple(ACTIVE_MODELS)
    manifest_sensors = tuple(manifest["supported_sensor_types"])
    if manifest_versions != code_versions:
        raise AssertionError("Версии реестра не совпадают с active.py")
    if manifest_sensors != SUPPORTED_SENSOR_TYPES:
        raise AssertionError("Типы датчиков реестра не совпадают с active.py")
    con = duckdb.connect()
    description = con.execute(f"""
        DESCRIBE SELECT * FROM read_parquet('{args.tickets.as_posix()}')
    """).fetchall()
    columns = tuple(row[0] for row in description)
    facts = con.execute(f"""
        WITH tickets AS (
          SELECT * FROM read_parquet('{args.tickets.as_posix()}')
        ), ordered AS (
          SELECT *,lag(obs_time) OVER (
            PARTITION BY model_version,channel_id ORDER BY obs_time,ticket_id
          ) previous_ticket
          FROM tickets
        ), daily AS (
          SELECT cast(obs_time AS DATE) ticket_day,count(*) ticket_count
          FROM tickets GROUP BY 1
        )
        SELECT
          (SELECT count(*) FROM tickets) tickets,
          (SELECT count(DISTINCT model_version) FROM tickets) models,
          (SELECT count(*) FROM ordered
           WHERE previous_ticket IS NOT NULL
             AND obs_time<previous_ticket+INTERVAL 48 HOUR) cooldown_violations,
          (SELECT coalesce(max(ticket_count),0) FROM daily) max_daily,
          (SELECT count(*) FROM tickets
           WHERE forecast_horizon_hours!=48) wrong_horizon,
          (SELECT count(*) FROM tickets
           WHERE model_version NOT IN ('power_phase_scada_v2','pump_scada_v1')) wrong_model
    """).fetchone()
    by_model = con.execute(f"""
        SELECT model_version,count(*) tickets
        FROM read_parquet('{args.tickets.as_posix()}')
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    result = {
        "check": "active_registry",
        "manifest_versions": manifest_versions,
        "supported_sensor_types": SUPPORTED_SENSOR_TYPES,
        "ticket_columns": columns,
        "schema_match": columns == EXPECTED_COLUMNS,
        "tickets": facts[0],
        "models": facts[1],
        "cooldown_violations": facts[2],
        "max_daily": facts[3],
        "wrong_horizon": facts[4],
        "wrong_model": facts[5],
        "tickets_by_model": dict(by_model),
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not result["schema_match"]:
        raise AssertionError("Схема заявок не совпадает")
    if facts[2] or facts[3] > 10 or facts[4] or facts[5]:
        raise AssertionError("Нарушена общая политика заявок")


if __name__ == "__main__":
    main()
