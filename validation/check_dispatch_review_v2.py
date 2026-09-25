"""Проверить полный состав очереди, привязку свидетельств и решения."""

import json
import sys
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from production_ml.pipeline.apply_dispatch_feedback import apply_feedback, read_feedback


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data"
    con = duckdb.connect()
    for period, start, end in (
        ("policy_2024", "2024-07-01", "2025-01-01"),
        ("diagnostic_2025_2026", "2025-01-01", "2026-07-01"),
    ):
        folder = root / "dispatch_review_v2" / period
        for name in ("members", "groups", "observed_mapping", "observed_evidence", "forecast_features",
                     "forecast_evidence"):
            con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM "
                        f"read_parquet('{(folder / (name + '.parquet')).as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW source AS SELECT * FROM read_parquet(" 
                    f"'{(root / 'review_queue' / (period + '.parquet')).as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW situations AS SELECT * FROM read_parquet(" 
                    f"'{(root / 'observed_v1' / 'situations.parquet').as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW evidence AS SELECT * FROM read_parquet(" 
                    f"'{(root / 'observed_v1' / 'evidence.parquet').as_posix()}')")
        result = con.execute(f"""
            SELECT (SELECT count(*) FROM source) source_forecasts,
                   (SELECT count(*) FROM members WHERE basis_kind='forecast') forecasts,
                   (SELECT count(*) FROM source s LEFT JOIN members m USING(draft_id)
                    WHERE m.draft_id IS NULL) lost_forecasts,
                   (SELECT count(*) FROM situations WHERE situation_kind IN
                    ('OBSERVED_PUMP_FLOODED_STATUS','OBSERVED_UPS_BATTERY_LOW_STATUS')
                    AND NOT multi_channel_campaign
                    AND first_seen>='{start}' AND first_seen<'{end}') source_observed,
                   (SELECT count(*) FROM observed_mapping) mapped_observed,
                   (SELECT count(*) FROM observed_mapping WHERE selected_draft)
                    selected_observed,
                   (SELECT count(*) FROM members WHERE basis_kind='observed_status') observed,
                   (SELECT count(*) FROM observed_mapping map LEFT JOIN members m
                    ON m.situation_id=map.draft_situation_id
                    WHERE m.draft_id IS NULL) missing_observed_mapping,
                   (SELECT count(*) FROM members)-
                    (SELECT count(DISTINCT draft_id) FROM members) duplicate_drafts,
                   (SELECT count(*) FROM members m LEFT JOIN groups g USING(group_id)
                    WHERE g.group_id IS NULL OR m.object_id!=g.object_id
                    OR m.obs_time NOT BETWEEN g.first_obs_time AND g.last_obs_time)
                    invalid_groups,
                   (SELECT count(*) FROM (
                       SELECT g.group_id FROM groups g JOIN members m USING(group_id)
                       GROUP BY g.group_id HAVING count(*)!=max(g.draft_count)
                    ))
                    wrong_group_counts,
                   (SELECT count(*) FROM members WHERE object_id IS NULL OR channel_id IS NULL)
                    missing_location,
                   (SELECT count(*) FROM members m WHERE m.basis_kind='forecast'
                    AND NOT EXISTS (SELECT 1 FROM forecast_features f
                                    WHERE f.draft_id=m.draft_id)) missing_features,
                   (SELECT count(*) FROM members m WHERE m.basis_kind='forecast'
                    AND NOT EXISTS (SELECT 1 FROM forecast_evidence e
                                    WHERE e.draft_id=m.draft_id)) missing_raw,
                   (SELECT count(*) FROM forecast_evidence e JOIN members m USING(draft_id)
                    WHERE e.event_time>m.obs_time OR
                    e.event_time<m.obs_time-INTERVAL 1 HOUR) future_forecast,
                   (SELECT count(*) FROM members m WHERE m.basis_kind='observed_status'
                    AND NOT EXISTS (SELECT 1 FROM observed_evidence e
                                    WHERE e.draft_id=m.draft_id AND e.initial_at_draft))
                    missing_initial,
                   (SELECT count(*) FROM observed_evidence e JOIN members m USING(draft_id)
                    WHERE e.initial_at_draft!=(e.event_time<=m.obs_time)) wrong_availability,
                   (SELECT count(*) FROM observed_evidence e JOIN evidence s
                    ON e.source_situation_id=s.situation_id
                     AND e.channel_id=s.channel_id AND e.event_time=s.event_time
                     AND e.event_id IS NOT DISTINCT FROM s.event_id
                     AND e.observed_value IS NOT DISTINCT FROM s.observed_value
                    WHERE s.situation_id IN (SELECT source_situation_id
                                             FROM observed_mapping))
                    matched_observed_evidence,
                   (SELECT count(*) FROM evidence e JOIN observed_mapping map
                    ON e.situation_id=map.source_situation_id)
                    expected_observed_evidence,
                   (SELECT count(*) FROM observed_evidence) observed_evidence_count
        """)
        facts = dict(zip([column[0] for column in result.description], result.fetchone()))
        print(json.dumps({"period": period, **facts}, ensure_ascii=False), flush=True)
        if (facts["source_forecasts"] != facts["forecasts"] or
            facts["source_observed"] != facts["mapped_observed"] or
            facts["selected_observed"] != facts["observed"] or
            facts["matched_observed_evidence"] != facts["observed_evidence_count"] or
            facts["expected_observed_evidence"] != facts["observed_evidence_count"] or
            any(facts[key] for key in (
                "lost_forecasts", "missing_observed_mapping", "duplicate_drafts", "invalid_groups", "wrong_group_counts",
                "missing_location", "missing_features", "missing_raw", "future_forecast",
                "missing_initial", "wrong_availability"))):
            raise AssertionError(facts)
    folder = root / "dispatch_review_v2" / "policy_2024"
    drafts = con.execute(f"SELECT * FROM read_parquet('{(folder / 'members.parquet').as_posix()}')").df()
    sample = drafts.iloc[:2]
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "feedback.jsonl"
        rows = [
            {"feedback_id": "check-1", "draft_id": sample.iloc[0].draft_id,
             "reviewed_at": "2026-09-25T12:00:00+03:00", "decision": "approved",
             "reviewer_id": "check", "reason_code": "verified_by_dispatcher"},
            {"feedback_id": "check-2", "draft_id": sample.iloc[1].draft_id,
             "reviewed_at": "2026-09-25T12:01:00+03:00", "decision": "rejected",
             "reviewer_id": "check", "reason_code": "duplicate_context"},
        ]
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
                        encoding="utf-8")
        feedback = read_feedback(path, require_reason=True)
        reviewed = apply_feedback(drafts, feedback)
        assert len(reviewed) == len(drafts)
        assert set(reviewed.loc[reviewed.draft_id.isin(sample.draft_id), "review_status"]) == {
            "approved", "rejected"}
        assert reviewed.loc[~reviewed.draft_id.isin(sample.draft_id),
                            "review_status"].eq("draft").all()
        rows[0].pop("reason_code")
        path.write_text(json.dumps(rows[0], ensure_ascii=False), encoding="utf-8")
        try:
            read_feedback(path, require_reason=True)
        except ValueError:
            pass
        else:
            raise AssertionError("Одобрение без причины принято")
    print(json.dumps({"feedback_check": "passed", "real_feedback_events": 0},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
