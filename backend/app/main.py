from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.api.errors import ApiError, api_error_handler, http_error_handler, validation_error_handler
from app.api.v2 import routes as v2_routes
from app.api.v2 import replay_builds as v2_replay_builds
from app.api.v1 import analytics, dashboard, objects, predictions, reports, sensors, system, tickets, weather
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.db import models  # noqa: F401  (регистрация моделей)
from app.db.init_db import seed_all
from app.v2.store import get_store
from app.services.scoring import build_risk_timeline_background, score_all_channels

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_all(session)
        scored = await score_all_channels(session)
    await asyncio.to_thread(get_store)  # исторический пакет ML для API v2
    timeline_task = asyncio.create_task(build_risk_timeline_background()) if scored else None
    log.info("startup complete: %s", settings.database_url.split("@")[-1])
    yield
    if timeline_task and not timeline_task.done():
        timeline_task.cancel()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Сервис прогнозирования инцидентов инженерных коллекторов АО «Москоллектор». Команда Dolos, ЛЦТ 2026.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

for _router in (system, dashboard, objects, predictions, sensors, tickets, analytics, reports, weather):
    app.include_router(_router.router, prefix=settings.api_v1_prefix)
app.include_router(v2_routes.router, prefix=settings.api_v2_prefix)
app.include_router(v2_replay_builds.router, prefix=settings.api_v2_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version, "docs": "/docs"}
