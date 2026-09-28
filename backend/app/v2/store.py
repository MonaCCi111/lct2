"""Исторический пакет ML (integration/backend_sanya, ml_handoff_v1) для API v2.

Данные неизменяемы (отсечка 30.06.2026), поэтому держим их в памяти как pyarrow-таблицы и фильтруем векторно.
Источник: parquet из пакета (Git LFS). Если parquet нет (не выполнен `git lfs pull`) - таблицы собираются из
fixtures_v1.json, чтобы API и фронт работали на реальных, но немногочисленных записях. meta.data_source это показывает.

Все метки времени приводятся к буквальной строке YYYY-MM-DDTHH:MM:SS без зоны (контракт: не добавлять +03:00/Z).
"""
from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.core.config import settings

log = logging.getLogger("v2.store")

TS_FMT = "%Y-%m-%dT%H:%M:%S"

# ресурс -> путь относительно <ml_handoff>/data
PARQUET = {
    "channel_current": "handoff_v1/channel_current.parquet",
    "observation_snapshots": "handoff_v1/observation_snapshots.parquet",
    "situations": "handoff_v1/situation_cards.parquet",
    "situation_evidence": "handoff_v1/situation_evidence.parquet",
    "drafts": "handoff_v1/draft_cards.parquet",
    "groups": "handoff_v1/group_cards.parquet",
    "chart_examples": "handoff_v1/chart_examples.parquet",
    "overview_object_day": "visualization_v1/object_day.parquet",
    "overview_object_type_day": "visualization_v1/object_type_day.parquet",
}
# доказательства черновиков лежат в двух периодах dispatch_review_v2
DRAFT_EVIDENCE_DIRS = ("dispatch_review_v2/policy_2024", "dispatch_review_v2/diagnostic_2025_2026")


def _is_real_parquet(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"PAR1"  # LFS-указатель начинается с "version https://git-lfs"
    except OSError:
        return False


def _stringify_times(table: pa.Table) -> pa.Table:
    for i, field in enumerate(table.schema):
        if pa.types.is_timestamp(field.type):  # без долей секунды: контракт - ровно YYYY-MM-DDTHH:MM:SS
            col = pc.cast(table.column(i), pa.timestamp("s", tz=field.type.tz), safe=False)
            table = table.set_column(i, field.name, pc.strftime(col, format=TS_FMT))
        elif pa.types.is_date(field.type):
            table = table.set_column(i, field.name, pc.strftime(pc.cast(table.column(i), pa.timestamp("s")), format="%Y-%m-%d"))
    return table


def _clean(v: Any) -> Any:
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, datetime):
        return v.strftime(TS_FMT)
    if isinstance(v, date):
        return v.isoformat()
    return v


def rows(table: pa.Table | None) -> list[dict]:
    if table is None or table.num_rows == 0:
        return []
    return [{k: _clean(v) for k, v in r.items()} for r in table.to_pylist()]


def where_eq(table: pa.Table | None, column: str, value: Any) -> pa.Table | None:
    if table is None or column not in table.column_names:
        return None
    return table.filter(pc.equal(table.column(column), pa.scalar(value, type=table.schema.field(column).type)))


def where_le(table: pa.Table | None, column: str, value: str | None) -> pa.Table | None:
    """column <= value для строковых меток времени (ISO сравнивается лексикографически)."""
    if table is None or value is None or column not in table.column_names:
        return table
    col = table.column(column)
    return table.filter(pc.fill_null(pc.less_equal(col, value), False))


def where_between(table: pa.Table | None, column: str, lo: str | None, hi: str | None) -> pa.Table | None:
    if table is None or column not in table.column_names:
        return table
    col = table.column(column)
    if lo is not None:
        table = table.filter(pc.fill_null(pc.greater_equal(col, lo), False))
        col = table.column(column)
    if hi is not None:
        table = table.filter(pc.fill_null(pc.less_equal(col, hi), False))
    return table


def sort_by(table: pa.Table, *keys: str) -> pa.Table:
    present = [(k, "ascending") for k in keys if k in table.column_names]
    return table.sort_by(present) if present else table


class HistoricalStore:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "data"
        self.tables: dict[str, pa.Table] = {}
        self.draft_evidence: pa.Table | None = None
        self.observed_evidence: pa.Table | None = None
        self.forecast_features: pa.Table | None = None
        self.replay_timelines: dict[str, pa.Table] = {}
        self.data_source = "empty"
        self.json: dict[str, Any] = {}

    # ------------------------------------------------------------------ load
    def _json(self, rel: str, default: Any = None) -> Any:
        p = self.root / rel
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    def _read(self, rel: str) -> pa.Table | None:
        p = self.data_dir / rel
        if not _is_real_parquet(p):
            return None
        return _stringify_times(pq.read_table(p))

    def _concat(self, rels: list[str]) -> pa.Table | None:
        parts = [t for t in (self._read(r) for r in rels) if t is not None]
        if not parts:
            return None
        return pa.concat_tables(parts, promote_options="default")

    def load(self) -> "HistoricalStore":
        self.json = {
            "contract": self._json("api_contract_v1.json", {}),
            "model_types": self._json("model_type_decisions.json", {"types": []}),
            "replays": self._json("replay_scenarios_v1.json", []),
            "runtime_policy": self._json("runtime_policy_v1.json", {}),
            "package_manifest": self._json("data/package_manifest.json", {}),
            "schema_manifest": self._json("data/handoff_v1/schema_manifest.json", {}),
            "fire_history": self._json("data/handoff_v1/fire_history_view.json", {}),
            "feedback": self._json("data/handoff_v1/feedback_availability.json", {}),
            "chart_index": self._json("data/handoff_v1/chart_example_index.json", {"cases": []}),
        }
        for name, rel in PARQUET.items():
            t = self._read(rel)
            if t is not None:
                self.tables[name] = t
        if self.tables:
            self.data_source = "ml_handoff_parquet"
            self.draft_evidence = self._concat([f"{d}/forecast_evidence.parquet" for d in DRAFT_EVIDENCE_DIRS])
            self.observed_evidence = self._concat([f"{d}/observed_evidence.parquet" for d in DRAFT_EVIDENCE_DIRS])
            self.forecast_features = self._concat([f"{d}/forecast_features.parquet" for d in DRAFT_EVIDENCE_DIRS])
            for sc in self.json["replays"]:
                t = self._read(f"replay_v1/{sc['id']}/timeline.parquet")
                if t is not None:
                    self.replay_timelines[sc["id"]] = t
        else:
            self._load_fixtures()
        log.info("v2 store: source=%s tables=%s", self.data_source, {k: v.num_rows for k, v in self.tables.items()})
        return self

    def _load_fixtures(self) -> None:
        fx = self._json("fixtures_v1.json")
        if not fx:
            return
        self.data_source = "fixtures_v1"
        strip = ("review_state", "decision", "history", "drafts")

        def base(d: dict) -> dict:
            return {k: v for k, v in d.items() if k not in strip}

        ch = fx["GET /api/v2/channels/{channel_id}"]
        self.tables["channel_current"] = pa.Table.from_pylist([base(ch)] + fx["GET /api/v2/channels?in_catalog=false"]["items"])
        self.tables["observation_snapshots"] = pa.Table.from_pylist(ch.get("history", []))
        self.tables["situations"] = pa.Table.from_pylist([fx["GET /api/v2/situations/{situation_id}"]])
        self.tables["situation_evidence"] = pa.Table.from_pylist(fx["GET /api/v2/situations/{situation_id}/evidence"]["items"])
        drafts = [base(fx["GET /api/v2/drafts/{draft_id}"])] + [base(d) for d in fx["GET /api/v2/drafts?basis_kind=forecast"]["items"]]
        self.tables["drafts"] = pa.Table.from_pylist(drafts)
        group = fx["GET /api/v2/groups/{group_id}"]
        groups = [base(group)]
        for d in drafts:  # у прогнозного черновика своя группа, в фикстурах её карточки нет
            if d["group_id"] != group["group_id"]:
                groups.append({"group_id": d["group_id"], "object_id": d["object_id"], "available_at": d["available_at"],
                               "draft_count": 1, "forecast_count": int(d["basis_kind"] == "forecast"),
                               "observed_count": int(d["basis_kind"] != "forecast")})
        self.tables["groups"] = pa.Table.from_pylist(groups)
        self.draft_evidence = pa.Table.from_pylist(fx["GET /api/v2/drafts/{forecast_draft_id}/evidence"]["items"])

    # ------------------------------------------------------------------ helpers
    def table(self, name: str) -> pa.Table | None:
        return self.tables.get(name)

    @property
    def data_cutoff(self) -> str:
        raw = (self.json.get("schema_manifest") or {}).get("data_cutoff") or "2026-06-30 23:59:59"
        return raw.replace(" ", "T")

    @property
    def active_models(self) -> set[str]:
        return set(((self.json.get("runtime_policy") or {}).get("forecast_models") or {}).keys())


store: HistoricalStore | None = None


def get_store() -> HistoricalStore:
    global store
    if store is None:
        store = HistoricalStore(settings.ml_handoff_dir).load()
    return store
