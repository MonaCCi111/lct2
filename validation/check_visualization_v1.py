"""Сверка витрин пункта 6 с исходными расчётами и временной отсечкой."""

import json
import sys
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1] / "production_ml" / "data"
VIEW = ROOT / "visualization_v1"
CON = duckdb.connect()


def p(path):
    return "'" + path.as_posix().replace("'", "''") + "'"


def scalar(query):
    return CON.execute(query).fetchone()[0]


def equal(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"{label}: {actual} != {expected}")
    print(f"OK {label}: {actual}")


def source_union(name):
    files = [ROOT / "dispatch_review_v2" / period / f"{name}.parquet"
             for period in ("policy_2024", "diagnostic_2025_2026")]
    return "read_parquet([" + ",".join(p(file) for file in files) + "])"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    daily = f"read_parquet({p(VIEW / 'object_day.parquet')})"
    typed = f"read_parquet({p(VIEW / 'object_type_day.parquet')})"
    navigation = f"read_parquet({p(VIEW / 'situation_navigation.parquet')})"
    situations = f"read_parquet({p(ROOT / 'observed_v1' / 'situations.parquet')})"
    members = source_union("members")
    groups = source_union("groups")
    equal("черновики по объектам и дням", scalar(f"SELECT sum(draft_count) FROM {daily}"),
          scalar(f"SELECT count(*) FROM {members}"))
    equal("группы по объектам и дням", scalar(f"SELECT sum(review_groups) FROM {daily}"),
          scalar(f"SELECT count(*) FROM {groups}"))
    equal("наблюдаемые ситуации", scalar(f"SELECT sum(observed_situations) FROM {daily}"),
          scalar(f"SELECT count(*) FROM {situations}"))
    equal("дымовые ситуации", scalar(f"SELECT sum(smoke_situations) FROM {daily}"),
          scalar(f"SELECT count(*) FROM {situations} WHERE situation_kind LIKE 'OBSERVED_SMOKE%'"))
    equal("газовые ситуации", scalar(f"SELECT sum(gas_situations) FROM {daily}"),
          scalar(f"SELECT count(*) FROM {situations} WHERE situation_kind LIKE 'OBSERVED_GAS%'"))
    equal("черновики по типам", scalar(f"SELECT sum(draft_count) FROM {typed}"),
          scalar(f"SELECT count(*) FROM {members}"))
    equal("ситуации по типам", scalar(f"SELECT sum(observed_situations) FROM {typed}"),
          scalar(f"SELECT count(*) FROM {situations}"))
    equal("строки навигации", scalar(f"SELECT count(*) FROM {navigation}"),
          scalar(f"SELECT count(*) FROM {situations}"))
    equal("уникальные ссылки ситуаций",
          scalar(f"SELECT count(DISTINCT situation_id) FROM {navigation}"),
          scalar(f"SELECT count(*) FROM {situations}"))
    equal("некорректные ссылки черновиков",
          scalar(f"SELECT count(*) FROM {navigation} n WHERE n.draft_id IS NOT NULL "
                 f"AND NOT EXISTS (SELECT 1 FROM {members} m WHERE m.draft_id=n.draft_id)"), 0)
    equal("разбиение черновиков", scalar(f"SELECT count(*) FROM {members}"),
          scalar(f"SELECT sum(forecast_drafts+observed_drafts) FROM {daily}"))
    quality = f"read_parquet({p(VIEW / 'forecast_quality_daily.parquet')})"
    equal("прогнозы в оценке", scalar(f"SELECT sum(forecast_drafts) FROM {quality}"),
          scalar(f"SELECT count(*) FROM {members} WHERE basis_kind='forecast'"))
    equal("доступные и недоступные для оценки прогнозы",
          scalar(f"SELECT sum(evaluable_drafts+unevaluable_drafts) FROM {quality}"),
          scalar(f"SELECT sum(forecast_drafts) FROM {quality}"))
    if scalar(f"SELECT count(*) FROM {quality} WHERE matched_scada_drafts>evaluable_drafts"):
        raise AssertionError("Совпадений SCADA больше оцениваемых черновиков")
    coverage = f"read_parquet({p(VIEW / 'coverage_monthly.parquet')})"
    source_coverage = f"read_parquet({p(ROOT / 'its_evidence_v1' / 'object_type_history.parquet')})"
    equal("охват каналов по месяцам", scalar(f"SELECT count(*) FROM {coverage}"),
          scalar(f"SELECT count(*) FROM {source_coverage}"))
    equal("придуманные значения ИТС", scalar(f"SELECT count(*) FROM {coverage} "
                                          "WHERE its_value IS NOT NULL"), 0)
    gas = f"read_parquet({p(VIEW / 'gas_daily.parquet')})"
    hourly_files = sorted((ROOT / "gas_v1").glob("hourly_20??.parquet"))
    hourly = "read_parquet([" + ",".join(p(file) for file in hourly_files) + "])"
    equal("газовые часовые записи", scalar(f"SELECT sum(recorded_hours) FROM {gas}"),
          scalar(f"SELECT count(*) FROM {hourly}"))
    equal("газовые измерения", scalar(f"SELECT sum(source_measurements) FROM {gas}"),
          scalar(f"SELECT sum(numeric_count) FROM {hourly}"))
    equal("часы выше заявленного порога",
          scalar(f"SELECT sum(hours_at_or_above_stated_threshold) FROM {gas}"),
          scalar(f"SELECT count(*) FROM {hourly} WHERE numeric_max>=1.0"))
    fire = json.loads((VIEW / "fire_history_view.json").read_text(encoding="utf-8"))
    feedback = json.loads((VIEW / "feedback_availability.json").read_text(encoding="utf-8"))
    equal("реестр подтверждённых пожаров", fire["confirmed_fire_register_available"], False)
    equal("число реальных пожаров", fire["real_fire_count"], None)
    equal("дым не назван пожаром", fire["smoke_signal_statistics_are_fires"], False)
    equal("реальная обратная связь", feedback["real_feedback_available"], False)
    equal("причины отказа неизвестны", feedback["rejection_reasons"], None)
    smoke_base = VIEW / "cases" / "smoke_5113_20251029"
    smoke_cut = VIEW / "cases" / "smoke_5113_at_signal"
    for folder in (smoke_base, smoke_cut, VIEW / "cases" / "gas_5578_20250407",
                   VIEW / "cases" / "gas_5657_20250306",
                   VIEW / "cases" / "phase_draft_20240703"):
        meta = json.loads((folder / "case_meta.json").read_text(encoding="utf-8"))
        points = f"read_parquet({p(folder / 'points.parquet')})"
        equal(f"число точек {folder.name}", scalar(f"SELECT count(*) FROM {points}"),
              meta["records"])
        equal(f"точки после среза {folder.name}",
              scalar(f"SELECT count(*) FROM {points} WHERE event_time>"
                     f"TIMESTAMP '{meta['view_at']}'"), 0)
    base_points = scalar(f"SELECT count(*) FROM read_parquet({p(smoke_base / 'points.parquet')})")
    cut_points = scalar(f"SELECT count(*) FROM read_parquet({p(smoke_cut / 'points.parquet')})")
    if not cut_points < base_points:
        raise AssertionError("Временной срез не убрал позднюю историю")
    print(f"OK отсечка будущего: {cut_points} точек против {base_points} в полном разборе")
    figures = VIEW / "figures"
    for index, stem in enumerate(("overview", "coverage", "shift_workload", "object_5113",
                                  "smoke_temperature_case", "gas_case",
                                  "fire_history_smoke", "forecast_quality"), start=1):
        for extension in ("png", "svg"):
            path = figures / f"{index:02d}_{stem}.{extension}"
            if not path.is_file() or path.stat().st_size < 1000:
                raise AssertionError(f"Нет пригодного графика {path}")
    print("OK 8 графиков в PNG и SVG")


if __name__ == "__main__":
    main()
