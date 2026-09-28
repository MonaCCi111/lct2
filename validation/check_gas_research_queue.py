"""Проверить исследовательскую газовую очередь и будущие статусы SCADA."""

import json
import sys
from pathlib import Path

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base = Path(__file__).resolve().parents[1] / "production_ml" / "data" / "gas_v1"
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW targets AS
        SELECT e.channel_id,e.event_time,e.card_id,c.alarm_channels
        FROM read_parquet('{(base / 'alarm_evidence.parquet').as_posix()}') e
        JOIN read_parquet('{(base / 'alarm_cards.parquet').as_posix()}') c USING(card_id);
    """)
    for year in (2024, 2025):
        folder = base / f"research_{year}_delta01"
        con.execute(f"CREATE OR REPLACE VIEW signals AS SELECT * FROM read_parquet('{(folder / 'signals.parquet').as_posix()}')")
        con.execute(f"CREATE OR REPLACE VIEW cards AS SELECT * FROM read_parquet('{(folder / 'cards.parquet').as_posix()}')")
        result = con.execute("""
            WITH ordered AS (
                SELECT *,lag(obs_time) OVER(
                    PARTITION BY channel_id ORDER BY obs_time) previous_time
                FROM signals
            ), membership AS (
                SELECT s.channel_id,s.obs_time,count(c.card_id) n
                FROM signals s LEFT JOIN cards c
                  ON s.card_id=c.card_id AND s.object_id=c.object_id
                 AND s.obs_time BETWEEN c.first_signal_time AND c.last_signal_time
                GROUP BY 1,2
            )
            SELECT (SELECT count(*) FROM signals) signals,
                   (SELECT count(*) FROM cards) cards,
                   (SELECT sum(signal_count) FROM cards) card_signals,
                   (SELECT count(*) FROM ordered WHERE previous_time IS NOT NULL
                      AND obs_time<previous_time+INTERVAL 48 HOUR) cooldown_violations,
                   (SELECT count(*) FROM membership WHERE n!=1) bad_membership,
                   (SELECT count(*) FROM cards WHERE review_status!='research'
                      OR candidate_kind!='UNVERIFIED_NUMERIC_RISE') wrong_status,
                   (SELECT count(*) FROM signals WHERE recent_observed_hours<3
                      OR baseline_observed_hours<12 OR median_delta<0.1) wrong_eligibility,
                   (SELECT count(*) FROM cards)-(SELECT count(DISTINCT card_id) FROM cards) duplicate_cards
        """)
        facts = dict(zip([d[0] for d in result.description], result.fetchone()))
        print(json.dumps({"year": year, "check": "structure", **facts}, ensure_ascii=False), flush=True)
        if facts["signals"] != facts["card_signals"] or any(
                facts[key] for key in ("cooldown_violations", "bad_membership",
                                       "wrong_status", "wrong_eligibility", "duplicate_cards")):
            raise AssertionError(facts)
        result = con.execute("""
            WITH future AS (
                SELECT s.*,t.event_time next_alarm_time,t.card_id next_alarm_card,
                       t.alarm_channels next_alarm_channels
                FROM signals s ASOF LEFT JOIN targets t
                  ON s.channel_id=t.channel_id AND s.obs_time<t.event_time
            ), matched AS (
                SELECT * FROM future
                WHERE next_alarm_time BETWEEN obs_time+INTERVAL 1 HOUR
                                          AND obs_time+INTERVAL 48 HOUR
            ), daily AS (
                SELECT cast(first_signal_time AS DATE) d,count(*) n FROM cards GROUP BY 1
            )
            SELECT (SELECT count(*) FROM matched) matched_signals,
                   (SELECT count(DISTINCT card_id) FROM matched) matched_candidate_cards,
                   (SELECT count(DISTINCT next_alarm_card) FROM matched) matched_status_cards,
                   (SELECT count(DISTINCT card_id) FROM matched
                      WHERE next_alarm_channels<10) matched_local_candidate_cards,
                   (SELECT count(DISTINCT next_alarm_card) FROM matched
                      WHERE next_alarm_channels<10) matched_local_status_cards,
                   (SELECT max(n) FROM daily) max_daily_cards,
                   (SELECT count(*) FROM daily WHERE n>10) days_over_ten_cards
        """)
        facts = dict(zip([d[0] for d in result.description], result.fetchone()))
        print(json.dumps({"year": year, "check": "retrospective_status", **facts},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
