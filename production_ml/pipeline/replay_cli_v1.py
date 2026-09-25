"""Интерактивное управление историческим ML-потоком в терминале."""

import argparse
import cmd
import json
import sys
import time
from pathlib import Path

import duckdb


class ReplaySession:
    def __init__(self, folder, show_all=False):
        self.folder = Path(folder)
        self.manifest = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))
        self.timeline = (self.folder / "timeline.parquet").as_posix().replace("'", "''")
        self.con = duckdb.connect()
        self.cursor = 0
        self.speed = 60.0
        self.show_all = show_all
        self.last_time = None
        self.simulated_decisions = []

    def _filter(self):
        return "" if self.show_all else "AND event_kind!='coverage_baseline'"

    def next_batch(self, count=1):
        if count < 1:
            raise ValueError("Число событий должно быть положительным")
        query = (f"SELECT seq,event_time,event_kind,channel_id,source_id,payload::VARCHAR "
                 f"FROM read_parquet('{self.timeline}') WHERE seq>? {self._filter()} "
                 "ORDER BY seq LIMIT ?")
        rows = self.con.execute(query,[self.cursor,count]).fetchall()
        return [{"seq":row[0],"event_time":row[1],"event_kind":row[2],
                 "channel_id":row[3],"source_id":row[4],"payload":json.loads(row[5])}
                for row in rows]

    def move(self, event):
        if event["seq"] <= self.cursor:
            raise ValueError("Порядок событий нарушен")
        self.cursor = event["seq"]
        self.last_time = event["event_time"]

    def seek(self, seq):
        if seq < 0:
            raise ValueError("Позиция не может быть отрицательной")
        self.cursor = seq
        row = self.con.execute(
            f"SELECT event_time FROM read_parquet('{self.timeline}') WHERE seq<=? "
            "ORDER BY seq DESC LIMIT 1",[seq]).fetchone()
        self.last_time = row[0] if row else None
        self.simulated_decisions.clear()

    def snapshot(self):
        rows = self.con.execute(
            f"SELECT event_kind,count(*) FROM read_parquet('{self.timeline}') "
            "WHERE seq<=? GROUP BY event_kind",[self.cursor]).fetchall()
        visible = dict(rows)
        coverage = self.con.execute(
            "WITH ranked AS (SELECT channel_id,"
            "json_extract_string(payload,'$.observation_state') state,"
            "row_number() OVER(PARTITION BY channel_id ORDER BY seq DESC) rn "
            f"FROM read_parquet('{self.timeline}') WHERE seq<=? "
            "AND event_kind IN ('coverage_baseline','coverage_lost','coverage_restored')) "
            "SELECT state,count(*) FROM ranked WHERE rn=1 GROUP BY state",
            [self.cursor]).fetchall()
        return {"cursor":self.cursor,"last_time":str(self.last_time),
                "speed":self.speed,"readings":visible.get("reading",0),
                "observed_signals":visible.get("observed_signal",0),
                "situations":visible.get("situation_ready",0),
                "drafts":visible.get("draft_created",0),
                "coverage":dict(coverage),
                "historical_feedback_available":False,
                "simulated_decisions":len(self.simulated_decisions)}

    def decide(self, draft_id, decision, reason):
        if decision not in ("approved","rejected"):
            raise ValueError("Решение: approved или rejected")
        if not reason.strip():
            raise ValueError("Причина обязательна")
        if self.last_time is None:
            raise ValueError("Сначала откройте событие потока")
        row = self.con.execute(
            f"SELECT seq,event_time FROM read_parquet('{self.timeline}') "
            "WHERE event_kind='draft_created' AND source_id=? LIMIT 1",
            [draft_id]).fetchone()
        if row is None or row[0]>self.cursor:
            raise ValueError("Этот черновик ещё не появился в потоке")
        record = {"kind":"SIMULATED_DISPATCHER_DECISION",
                  "draft_id":draft_id,"decision":decision,"reason":reason,
                  "simulation_time":self.last_time.isoformat(sep=" "),
                  "source":"manual_replay_action_not_historical_feedback"}
        self.simulated_decisions.append(record)
        return record


class ReplayShell(cmd.Cmd):
    prompt = "timeline> "
    intro = ("Команды: next [n], play [n], pause через Ctrl+C, speed <x>, "
             "seek <seq>, decide <draft_id> <approved|rejected> <reason>, "
             "status, quit")

    def __init__(self, session, max_wait):
        super().__init__()
        self.session = session
        self.max_wait = max_wait

    def _print_event(self, event):
        payload = event["payload"]
        if event["event_kind"] == "reading":
            brief = f"канал={event['channel_id']} значение={payload['sensor_value']} тревога={payload['is_alarm']}"
        elif event["event_kind"] == "draft_created":
            brief = f"черновик={payload['draft_id']} основание={payload['basis_kind']}"
        elif event["event_kind"] == "situation_ready":
            brief = f"ситуация={payload['situation_id']} свидетельств={payload['evidence_count']}"
        else:
            brief = f"канал={event['channel_id']} {payload.get('observation_state','')}"
        print(f"{event['seq']} {event['event_time']} {event['event_kind']} {brief}")

    def do_next(self, argument):
        """Перейти к следующему событию или нескольким событиям."""
        count = int(argument.strip() or "1")
        events = self.session.next_batch(count)
        for event in events:
            self.session.move(event)
            self._print_event(event)
        if not events:
            print("Конец периода")

    def do_play(self, argument):
        """Запустить поток. Ctrl+C останавливает без потери позиции."""
        count = int(argument.strip() or "100")
        events = self.session.next_batch(count)
        previous = self.session.last_time
        try:
            for event in events:
                if previous is not None:
                    delay = max(0.0,(event["event_time"]-previous).total_seconds()
                                / self.session.speed)
                    time.sleep(min(delay,self.max_wait))
                self.session.move(event)
                self._print_event(event)
                previous = event["event_time"]
        except KeyboardInterrupt:
            print("Пауза")
        if not events:
            print("Конец периода")

    def do_speed(self, argument):
        """Установить ускорение: 60 означает 60 секунд истории за секунду."""
        value = float(argument)
        if value <= 0:
            raise ValueError("Ускорение должно быть положительным")
        self.session.speed = value
        print(f"Ускорение {value:g}x")

    def do_seek(self, argument):
        """Перейти к номеру события; имитационные решения сбрасываются."""
        self.session.seek(int(argument))
        print(f"Позиция {self.session.cursor}")

    def do_decide(self, argument):
        """Добавить ручное имитационное решение для уже появившегося черновика."""
        parts = argument.split(maxsplit=2)
        if len(parts) != 3:
            raise ValueError("Нужны draft_id, решение и причина")
        print(json.dumps(self.session.decide(*parts),ensure_ascii=False))

    def do_status(self, _argument):
        """Показать позицию, скорость и ограничения исторического потока."""
        print(json.dumps({"object_id":self.session.manifest["object_id"],
                          **self.session.snapshot()},ensure_ascii=False))

    def do_quit(self, _argument):
        """Закончить просмотр."""
        return True

    def do_EOF(self, _argument):
        print()
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline",type=Path,required=True,
                        help="Папка с timeline.parquet и manifest.json")
    parser.add_argument("--all-events",action="store_true",
                        help="Показывать также стартовые состояния каждого канала")
    parser.add_argument("--max-wait",type=float,default=0.2)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.max_wait < 0:
        raise ValueError("max-wait не может быть отрицательным")
    shell = ReplayShell(ReplaySession(args.timeline,args.all_events),args.max_wait)
    shell.cmdloop()


if __name__ == "__main__":
    main()
