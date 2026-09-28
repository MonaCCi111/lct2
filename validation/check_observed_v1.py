"""Проверить покрытие источников, ссылки, поля и дневную нагрузку."""

import csv
import json
import sys
from pathlib import Path

import duckdb


def one(con, sql):
    result = con.execute(sql)
    return dict(zip((d[0] for d in result.description), result.fetchone()))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    out = root / "observed_v1"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{(out / 'situations.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{(out / 'evidence.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW original_smoke AS SELECT * FROM read_parquet('{(root / 'smoke_evidence' / 'signals.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW original_gas AS SELECT * FROM read_parquet('{(root / 'gas_v1' / 'alarm_evidence.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW original_hourly AS SELECT * FROM read_parquet('{(root / 'gas_v1' / 'hourly_20??.parquet').as_posix()}')")
    counts = one(con, """
        SELECT (SELECT count(*) FROM s) situations,
               (SELECT count(DISTINCT situation_id) FROM s) unique_situations,
               (SELECT count(*) FROM e) evidence,
               (SELECT count(*) FROM e x LEFT JOIN s y USING(situation_id)
                WHERE y.situation_id IS NULL) orphan_evidence,
               (SELECT count(*) FROM s WHERE first_seen>last_seen) bad_time,
               (SELECT count(*) FROM s WHERE situation_kind='OBSERVED_GAS_NUMERIC_1PCT'
                AND (numeric_max<1 OR stated_threshold!=1 OR numeric_unit!='vol_percent_methane')) bad_gas_unit,
               (SELECT count(*) FROM e WHERE evidence_kind='GAS_TEXT' AND event_id IS NULL) missing_gas_event_id,
               (SELECT count(*) FROM e WHERE evidence_kind='OTHER_TEXT_STATUS' AND event_id IS NULL) missing_other_event_id,
               (SELECT count(*) FROM e WHERE event_time>observation_end
                AND observation_end IS NOT NULL) future_numeric,
               (SELECT count(*) FROM s WHERE affected_channels<1) empty_channel_count,
               (SELECT count(*) FROM e WHERE channel_name IS NULL) missing_channel_name,
               (SELECT count(*) FROM e WHERE evidence_kind='GAS_NUMERIC_HOURLY'
                AND (hour_numeric_count IS NULL OR numeric_value<1)) bad_hourly_measurement,
               (SELECT count(*) FROM e WHERE evidence_kind='SMOKE_TEXT'
                AND channel_id=212285 AND event_time=TIMESTAMP '2025-10-29 00:24:16'
                AND mixed_alarm_flags_at_time) notebook_smoke_evidence,
               (SELECT count(*) FROM s WHERE situation_kind LIKE 'OBSERVED_SMOKE%'
                AND object_id=5113 AND first_seen=TIMESTAMP '2025-10-29 00:24:16'
                AND mixed_status_signal_records>0) notebook_smoke_cards;
    """)
    by_kind = con.execute("""
        WITH evidence_counts AS (
            SELECT situation_id,count(*) evidence_records FROM e GROUP BY 1
        )
        SELECT situation_kind,count(*) situations,sum(signal_records) records,
               sum(coalesce(evidence_records,0)) evidence_records
        FROM s LEFT JOIN evidence_counts USING(situation_id)
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    source_counts = one(con, """
        SELECT (SELECT count(*) FROM original_smoke) smoke_signals,
               (SELECT count(*) FROM original_gas) gas_status_signals,
               (SELECT count(*) FROM original_hourly WHERE numeric_max>=1) gas_threshold_hours,
               (SELECT count(*) FROM original_smoke WHERE mixed_alarm_flags_at_time) smoke_mixed_source,
               (SELECT count(*) FROM e WHERE evidence_kind='SMOKE_TEXT') output_smoke,
               (SELECT count(*) FROM e WHERE evidence_kind='SMOKE_TEXT'
                AND mixed_alarm_flags_at_time) smoke_mixed_output,
               (SELECT sum(mixed_status_signal_records) FROM s
                WHERE situation_kind LIKE 'OBSERVED_SMOKE%') smoke_mixed_cards,
               (SELECT count(*) FROM e WHERE evidence_kind='GAS_TEXT') output_gas_status,
               (SELECT count(*) FROM e WHERE evidence_kind='GAS_NUMERIC_HOURLY') output_gas_threshold;
    """)
    daily = con.execute("""
        WITH counts AS (
            SELECT cast(first_seen AS date) date_value,count(*) cards
            FROM s WHERE first_seen>='2024-01-01' AND first_seen<'2026-01-01'
            GROUP BY 1
        )
        SELECT year(date_value) yr,count(*) active_days,median(cards) median_cards_active_day,
               quantile_cont(cards,0.9) p90_cards_active_day,max(cards) max_cards_day
        FROM counts GROUP BY 1 ORDER BY 1
    """).fetchall()
    peaks = con.execute("""
        SELECT cast(first_seen AS date) date_value,count(*) cards
        FROM s GROUP BY 1 ORDER BY 2 DESC LIMIT 5
    """).fetchall()
    manifest = json.loads((out / "fire_history_manifest.json").read_text(encoding="utf-8"))
    with (out / "confirmed_fires.csv").open(encoding="utf-8", newline="") as file:
        fire_rows = list(csv.reader(file))
    with (out / "smoke_temperature_candidates.csv").open(encoding="utf-8", newline="") as file:
        candidates = list(csv.DictReader(file))
    assert len(fire_rows) == 1 and len(fire_rows[0]) == 8
    assert manifest["confirmed_fire_register_available"] is False
    assert manifest["confirmed_fire_count"] == 0
    assert len(candidates) == manifest["telemetry_candidate_count"]
    assert all(c["evidence_state"] == "UNCONFIRMED_TELEMETRY_COINCIDENCE"
               for c in candidates)
    notebook_cases = [c for c in candidates if c["object_id"] == "5113"
                      and c["piket"] == "108"
                      and c["first_smoke_time"] == "2025-10-29 00:24:16"]
    assert len(notebook_cases) == 1
    assert notebook_cases[0]["any_smoke_mixed_status"] == "true"
    assert notebook_cases[0]["any_temperature_undefined_status"] == "true"
    assert counts["situations"] == counts["unique_situations"]
    assert counts["notebook_smoke_evidence"] == counts["notebook_smoke_cards"] == 1
    assert not any(counts[k] for k in ("orphan_evidence", "bad_time", "bad_gas_unit",
                                         "missing_gas_event_id", "missing_other_event_id",
                                         "future_numeric", "empty_channel_count",
                                         "missing_channel_name", "bad_hourly_measurement"))
    for source, output in (("smoke_signals", "output_smoke"),
                           ("gas_status_signals", "output_gas_status"),
                           ("gas_threshold_hours", "output_gas_threshold")):
        assert source_counts[source] == source_counts[output], (source, source_counts)
    assert (source_counts["smoke_mixed_source"] == source_counts["smoke_mixed_output"]
            == source_counts["smoke_mixed_cards"]), source_counts
    assert sum(r[2] for r in by_kind) == counts["evidence"], (by_kind, counts)
    assert all(r[2] == r[3] for r in by_kind), by_kind
    print(json.dumps({"checks": counts, "source_coverage": source_counts,
                      "by_kind": by_kind, "daily_2024_2025": daily,
                      "peak_days": peaks, "fire_history_state": manifest["display_state"]},
                     ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
