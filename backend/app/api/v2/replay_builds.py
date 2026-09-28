"""Построение произвольного исторического replay из локального полного архива ML.

Переносимый handoff содержит восемь готовых сценариев. Этот маршрут доступен
только при явном подключении исходного архива, который не хранится в Git.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.errors import ApiError
from app.core.config import settings
from app.v2 import store as st

router = APIRouter(tags=["v2 replay"])
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_ID = re.compile(r"^custom_[0-9a-f]{16}$")
_jobs: dict[str, dict] = {}
_running_tasks: set[asyncio.Task] = set()


class ReplayBuildRequest(BaseModel):
    object_id: int
    start: str
    end: str


def _parse_time(value: str) -> datetime:
    if not _TIME.fullmatch(value):
        raise ApiError(422, "INVALID_REPLAY_TIME", "Нужно время источника YYYY-MM-DDTHH:MM:SS без зоны")
    return datetime.fromisoformat(value)


def _paths() -> tuple[Path, Path]:
    root, catalog = settings.replay_source_root, settings.replay_catalog
    if root is None or catalog is None or not root.is_dir() or not catalog.is_file():
        raise ApiError(503, "REPLAY_SOURCE_NOT_MOUNTED", "Полный архив для произвольного replay не подключён")
    return root, catalog


def _cache_path(replay_id: str) -> Path:
    if not _ID.fullmatch(replay_id):
        raise ApiError(404, "REPLAY_NOT_FOUND", "Сценарий не найден")
    return settings.replay_cache_dir / replay_id


def _ready(replay_id: str) -> bool:
    path = _cache_path(replay_id)
    return (path / "timeline.parquet").is_file() and (path / "manifest.json").is_file()


async def _build(replay_id: str, body: ReplayBuildRequest, root: Path, catalog: Path) -> None:
    output = _cache_path(replay_id)
    output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[2] / "v2" / "build_replay.py"
    command = [sys.executable, str(script), "--object-id", str(body.object_id), "--start", body.start,
               "--end", body.end, "--root", str(root), "--catalog", str(catalog), "--output", str(output)]
    try:
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()
        if process.returncode != 0:
            _jobs[replay_id] = {"status": "failed", "message": stderr.decode("utf-8", errors="replace")[-600:]}
        elif _ready(replay_id):
            _jobs[replay_id] = {"status": "ready"}
        else:
            _jobs[replay_id] = {"status": "failed", "message": "Файлы сценария не созданы"}
    except Exception as exc:  # ошибка возвращается статусом задачи, основной API продолжает работу
        _jobs[replay_id] = {"status": "failed", "message": str(exc)}


@router.post("/replay-builds", status_code=202)
async def create_replay(body: ReplayBuildRequest) -> dict:
    start, end = _parse_time(body.start), _parse_time(body.end)
    if end <= start:
        raise ApiError(422, "INVALID_REPLAY_PERIOD", "Конец периода должен быть позже начала")
    root, catalog = _paths()
    key = f"{body.object_id}:{body.start}:{body.end}"
    replay_id = "custom_" + hashlib.sha256(key.encode()).hexdigest()[:16]
    if _ready(replay_id):
        return {"id": replay_id, "status": "ready"}
    if _jobs.get(replay_id, {}).get("status") != "building":
        _jobs[replay_id] = {"status": "building"}
        task = asyncio.create_task(_build(replay_id, body, root, catalog))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
    return {"id": replay_id, "status": "building"}


@router.get("/replay-builds/{replay_id}")
async def get_replay_build(replay_id: str) -> dict:
    path = _cache_path(replay_id)
    if _ready(replay_id):
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        return {"id": replay_id, "status": "ready", "event_count": pq.read_metadata(path / "timeline.parquet").num_rows,
                "object_id": manifest.get("object_id"), "start": manifest.get("start"), "end": manifest.get("end_exclusive"),
                "limitations": manifest.get("source_limits")}
    if replay_id in _jobs:
        return {"id": replay_id, **_jobs[replay_id]}
    raise ApiError(404, "REPLAY_NOT_FOUND", "Сценарий не найден")


def custom_replay_events(replay_id: str, after_seq: int, limit: int) -> dict:
    if not _ready(replay_id):
        raise ApiError(404, "REPLAY_NOT_READY", "Сценарий ещё не построен")
    store = st.get_store()
    if replay_id not in store.replay_timelines:
        store.replay_timelines[replay_id] = st._stringify_times(pq.read_table(_cache_path(replay_id) / "timeline.parquet"))
    table = store.replay_timelines[replay_id]
    part = st.sort_by(table.filter(pc.greater(table.column("seq"), after_seq)), "seq")
    items = st.rows(part.slice(0, limit))
    return {"items": items, "next_cursor": str(items[-1]["seq"]) if part.num_rows > limit else None}
