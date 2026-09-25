"""Присоединить решения диспетчера к ML-черновикам для последующего аудита."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


DECISIONS = {"approved", "rejected"}
REQUIRED_FIELDS = {"feedback_id", "draft_id", "reviewed_at", "decision", "reviewer_id"}
FEEDBACK_FIELDS = ("feedback_id", "draft_id", "reviewed_at_utc", "decision",
                   "reviewer_id", "reason_code", "work_order_id")


def read_feedback(path, require_reason=False):
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not REQUIRED_FIELDS <= event.keys():
                raise ValueError(f"Неверные поля события обратной связи, строка {line_number}")
            if any(not isinstance(event[key], str) or not event[key].strip()
                   for key in REQUIRED_FIELDS):
                raise ValueError(f"Пустое обязательное поле, строка {line_number}")
            if event["decision"] not in DECISIONS:
                raise ValueError(f"Неизвестное решение, строка {line_number}")
            if (event["decision"] == "rejected" or require_reason) and not event.get("reason_code"):
                raise ValueError(f"Причина решения обязательна, строка {line_number}")
            reviewed_at = datetime.fromisoformat(event["reviewed_at"].replace("Z", "+00:00"))
            if reviewed_at.utcoffset() is None:
                raise ValueError(f"Время решения должно иметь часовой пояс, строка {line_number}")
            events.append({
                "feedback_id": event["feedback_id"],
                "draft_id": event["draft_id"],
                "reviewed_at_utc": pd.Timestamp(reviewed_at).tz_convert("UTC"),
                "decision": event["decision"],
                "reviewer_id": event["reviewer_id"],
                "reason_code": event.get("reason_code") or None,
                "work_order_id": event.get("work_order_id") or None,
            })
    frame = pd.DataFrame(events, columns=FEEDBACK_FIELDS)
    if not frame.empty and frame.feedback_id.duplicated().any():
        raise ValueError("Повторяющийся feedback_id")
    if not frame.empty and frame.duplicated(["draft_id", "reviewed_at_utc"]).any():
        raise ValueError("У одного черновика два решения с одинаковым временем")
    return frame


def apply_feedback(drafts, feedback):
    if drafts.draft_id.duplicated().any():
        raise ValueError("Повторяющийся draft_id")
    if not drafts.review_status.eq("draft").all():
        raise ValueError("Входная ML-очередь должна содержать черновики")
    unknown = set(feedback.draft_id) - set(drafts.draft_id)
    if unknown:
        raise ValueError(f"Решение для неизвестного draft_id: {sorted(unknown)[:3]}")
    if feedback.empty:
        latest = feedback.copy()
    else:
        latest = (feedback.sort_values(["draft_id", "reviewed_at_utc"])
                  .drop_duplicates("draft_id", keep="last"))
    joined = drafts.merge(latest, on="draft_id", how="left", validate="one_to_one")
    joined["review_status"] = joined["decision"].fillna("draft")
    return joined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--members", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-reason", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    for path in (args.members, args.feedback):
        if not path.exists():
            raise FileNotFoundError(path)
    con = duckdb.connect()
    drafts = con.execute(f"SELECT * FROM read_parquet('{args.members.as_posix()}')").df()
    feedback = read_feedback(args.feedback, require_reason=args.require_reason)
    reviewed = apply_feedback(drafts, feedback)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    con.register("reviewed", reviewed)
    con.execute(f"COPY reviewed TO '{args.output.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    print(json.dumps({"output": str(args.output), "drafts": len(reviewed),
                      "feedback_events": len(feedback),
                      "latest_statuses": reviewed.review_status.value_counts().to_dict()},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
