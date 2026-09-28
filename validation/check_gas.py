"""Проверить газовые часовые факты, карточки и расчёт из ограниченной истории."""

import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import duckdb

from production_ml.pipeline.gas_live_cards import build_observed_cards
from production_ml.pipeline.gas_live_features import aggregate_hour, build_hour_features


def rows(result):
    columns = [item[0] for item in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def equal(expected, actual):
    if isinstance(expected, float) and isinstance(actual, float):
        return math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-12)
    return expected == actual


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    data = root / "production_ml" / "data" / "gas_v1"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW hourly AS SELECT * FROM read_parquet('{(data / 'hourly_*.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW features AS SELECT * FROM read_parquet('{(data / 'features.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW cards AS SELECT * FROM read_parquet('{(data / 'alarm_cards.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW evidence AS SELECT * FROM read_parquet('{(data / 'alarm_evidence.parquet').as_posix()}')")
    result = con.execute("""
        SELECT (SELECT count(*) FROM hourly) hourly_rows,
               (SELECT count(*) FROM hourly)-(SELECT count(*) FROM
                   (SELECT channel_id,obs_time FROM hourly GROUP BY 1,2)) duplicate_hours,
               (SELECT count(*) FROM hourly WHERE numeric_count<=0
                   OR numeric_min>numeric_median OR numeric_median>numeric_max) invalid_hours,
               (SELECT count(*) FROM features) feature_rows,
               (SELECT count(*) FROM cards) cards,
               (SELECT count(*) FROM cards)-(SELECT count(DISTINCT card_id) FROM cards) duplicate_cards,
               (SELECT sum(alarm_records) FROM cards) card_records,
               (SELECT count(*) FROM evidence) evidence_records,
               (SELECT count(*) FROM cards WHERE alarm_channels>alarm_records
                   OR first_alarm_time>last_alarm_time) invalid_cards
    """)
    facts = rows(result)[0]
    print(json.dumps({"check": "structure", **facts}, ensure_ascii=False), flush=True)
    if (facts["hourly_rows"] != facts["feature_rows"]
            or facts["card_records"] != facts["evidence_records"]
            or any(facts[key] for key in
                   ("duplicate_hours", "invalid_hours", "duplicate_cards", "invalid_cards"))):
        raise AssertionError(facts)

    actual_cards = build_observed_cards(rows(con.execute("SELECT * FROM evidence")))
    expected_cards = {row["card_id"]: row for row in rows(con.execute("SELECT * FROM cards"))}
    mismatches = []
    for card in actual_cards:
        expected = expected_cards.get(card["card_id"])
        differences = ({key: [expected[key], value] for key, value in card.items()
                        if not equal(expected[key], value)} if expected else {"missing": card["card_id"]})
        if differences:
            mismatches.append({"card_id": card["card_id"], "differences": differences})
    print(json.dumps({"check": "card_parity", "historical": len(expected_cards),
                      "streamed": len(actual_cards), "mismatches": len(mismatches),
                      "examples": mismatches[:3]}, ensure_ascii=False, default=str), flush=True)
    if len(actual_cards) != len(expected_cards) or mismatches:
        raise AssertionError(mismatches[:3])

    cases = ((196723, "2024-06-01 12:00:00"),
             (196723, "2025-01-01 00:00:00"),
             (104026, "2024-04-14 15:00:00"))
    for channel_id, timestamp in cases:
        feature = rows(con.execute("SELECT * FROM features WHERE channel_id=? AND obs_time=?",
                                   [channel_id, timestamp]))
        if len(feature) != 1:
            raise AssertionError((channel_id, timestamp, len(feature)))
        expected = feature[0]
        time = expected["obs_time"]
        prior = rows(con.execute("""
            SELECT * FROM hourly WHERE channel_id=? AND obs_time>=?
              AND obs_time<? ORDER BY obs_time
        """, [channel_id, time - timedelta(hours=72), time]))
        current = rows(con.execute("SELECT * FROM hourly WHERE channel_id=? AND obs_time=?",
                                   [channel_id, timestamp]))[0]
        actual = build_hour_features(current, prior)
        differences = {key: [expected[key], value] for key, value in actual.items()
                       if not equal(expected[key], value)}
        if timestamp == "2024-06-01 12:00:00":
            journal = root / "production_ml" / "data" / "source_v2" / "journal_2024.parquet"
            events = rows(con.execute(f"""
                SELECT event_time,try_cast(replace(sensor_value,',','.') AS DOUBLE) numeric_value
                FROM read_parquet('{journal.as_posix()}')
                WHERE channel_id=? AND event_time>=? AND event_time<?
                  AND try_cast(replace(sensor_value,',','.') AS DOUBLE) IS NOT NULL
                ORDER BY event_time
            """, [channel_id, time - timedelta(hours=1), time]))
            raw_hour = aggregate_hour(channel_id, current["object_id"], time, events)
            differences.update({key: [current[key], value] for key, value in raw_hour.items()
                                if not equal(current[key], value)})
        print(json.dumps({"check": "live_parity", "channel_id": channel_id,
                          "obs_time": timestamp, "previous_hours": len(prior),
                          "differences": differences}, ensure_ascii=False, default=str), flush=True)
        if differences:
            raise AssertionError(differences)


if __name__ == "__main__":
    main()
