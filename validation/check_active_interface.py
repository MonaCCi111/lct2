"""Проверить формат и ограничения выдачи действующего ML-интерфейса."""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from production_ml.pipeline.active import MODEL_VERSION
from production_ml.pipeline.create_tickets import OUTPUT_COLUMNS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scores",type=Path,required=True)
    parser.add_argument("--tickets",type=Path,required=True)
    args=parser.parse_args();sys.stdout.reconfigure(encoding="utf-8")
    con=duckdb.connect()
    score_columns=[x[0] for x in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{args.scores.as_posix()}')").fetchall()]
    ticket_columns=[x[0] for x in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{args.tickets.as_posix()}')").fetchall()]
    row=con.execute(f"""
      WITH t AS (
        SELECT *,lag(obs_time) OVER(PARTITION BY channel_id ORDER BY obs_time) previous_ticket
        FROM read_parquet('{args.tickets.as_posix()}')
      ), daily AS (
        SELECT date_trunc('day',obs_time) day_bucket,count(*) n
        FROM read_parquet('{args.tickets.as_posix()}') GROUP BY 1
      )
      SELECT (SELECT count(*) FROM read_parquet('{args.scores.as_posix()}')) score_rows,
             count(*) ticket_rows,max(score) max_score,min(score) min_score,
             count(*) FILTER(WHERE model_version!=?) wrong_version,
             count(*) FILTER(WHERE previous_ticket IS NOT NULL AND obs_time<previous_ticket+INTERVAL 48 HOUR) cooldown_violations,
             (SELECT max(n) FROM daily) max_daily
      FROM t
    """,[MODEL_VERSION]).fetchone()
    print(json.dumps({"check":"active_interface","score_columns":score_columns,
                      "ticket_columns":ticket_columns,"expected_ticket_columns":OUTPUT_COLUMNS,
                      "score_rows":row[0],"ticket_rows":row[1],"max_score":row[2],"min_score":row[3],
                      "wrong_version":row[4],"cooldown_violations":row[5],"max_daily":row[6],
                      "schema_match":tuple(ticket_columns)==OUTPUT_COLUMNS},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
