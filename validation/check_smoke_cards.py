"""Проверить покрытие сигналов историческими карточками дыма."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "production_ml" / "data" / "smoke_evidence"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW signals AS SELECT * FROM read_parquet('{(root / 'signals.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW cards AS SELECT * FROM read_parquet('{(root / 'cards.parquet').as_posix()}')")
    result = con.execute("""
        WITH located AS (
            SELECT *,CASE WHEN piket IS NULL OR piket=''
                           THEN concat('channel:',channel_id::VARCHAR)
                           ELSE concat('piket:',piket) END location_key
            FROM signals
        ), membership AS (
            SELECT s.channel_id,s.event_time,count(c.card_id) card_count
            FROM located s LEFT JOIN cards c
              ON s.object_id=c.object_id AND s.location_key=c.location_key
             AND s.event_time BETWEEN c.first_signal_time AND c.last_signal_time
            GROUP BY 1,2
        )
        SELECT (SELECT count(*) FROM signals) signals,
               (SELECT count(*) FROM cards) cards,
               (SELECT sum(signal_records) FROM cards) recorded_signals,
               (SELECT count(*) FROM cards)-(SELECT count(DISTINCT card_id) FROM cards) duplicate_ids,
               (SELECT count(*) FROM membership WHERE card_count!=1) bad_membership,
               (SELECT count(*) FROM cards WHERE smoke_channels>signal_records
                    OR first_signal_time>last_signal_time) invalid_cards
    """)
    facts = dict(zip([d[0] for d in result.description], result.fetchone()))
    print(json.dumps(facts, ensure_ascii=False), flush=True)
    if (facts["signals"] != facts["recorded_signals"] or facts["duplicate_ids"]
            or facts["bad_membership"] or facts["invalid_cards"]):
        raise AssertionError(facts)


if __name__ == "__main__":
    main()
