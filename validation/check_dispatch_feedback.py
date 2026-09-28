"""Проверить контракт решений диспетчера на синтетических событиях."""

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

from production_ml.pipeline.apply_dispatch_feedback import apply_feedback, read_feedback


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data" / "dispatch_review"
    source = root / "policy_2024" / "review_members.parquet"
    drafts = duckdb.connect().execute(f"SELECT * FROM read_parquet('{source.as_posix()}')").df()
    first, second = drafts.draft_id.iloc[:2]
    events = [
        {"feedback_id": "synthetic-1", "draft_id": first,
         "reviewed_at": "2026-09-24T09:00:00Z", "decision": "approved",
         "reviewer_id": "test-dispatcher", "work_order_id": "test-order"},
        {"feedback_id": "synthetic-2", "draft_id": first,
         "reviewed_at": "2026-09-24T10:00:00Z", "decision": "rejected",
         "reviewer_id": "test-dispatcher", "reason_code": "test-correction"},
        {"feedback_id": "synthetic-3", "draft_id": second,
         "reviewed_at": "2026-09-24T09:30:00+00:00", "decision": "approved",
         "reviewer_id": "test-dispatcher", "work_order_id": "test-order-2"},
    ]
    fixture = root / "synthetic_feedback.jsonl"
    fixture.write_text("\n".join(json.dumps(row) for row in events) + "\n", encoding="utf-8")
    feedback = read_feedback(fixture)
    reviewed = apply_feedback(drafts, feedback)
    statuses = reviewed.set_index("draft_id").review_status
    facts = {"input_drafts": len(drafts), "feedback_events": len(feedback),
             "output_drafts": len(reviewed), "rejected": int((statuses == "rejected").sum()),
             "approved": int((statuses == "approved").sum()),
             "pending": int((statuses == "draft").sum()),
             "latest_decision_kept": bool(statuses[first] == "rejected")}
    unknown_rejected = False
    try:
        invalid = feedback.copy()
        invalid.loc[0, "draft_id"] = "missing-draft"
        apply_feedback(drafts, invalid)
    except ValueError:
        unknown_rejected = True
    facts["unknown_draft_rejected"] = unknown_rejected
    empty = pd.DataFrame(columns=feedback.columns)
    facts["empty_keeps_all_drafts"] = bool(
        apply_feedback(drafts, empty).review_status.eq("draft").all()
    )
    print(json.dumps(facts, ensure_ascii=False), flush=True)
    if not (facts["input_drafts"] == facts["output_drafts"]
            and facts["rejected"] == 1 and facts["approved"] == 1
            and facts["pending"] == len(drafts) - 2
            and facts["latest_decision_kept"] and facts["unknown_draft_rejected"]
            and facts["empty_keeps_all_drafts"]):
        raise AssertionError(facts)


if __name__ == "__main__":
    main()
