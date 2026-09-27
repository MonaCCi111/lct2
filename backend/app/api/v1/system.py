from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.timeutil import iso_msk, now_msk

router = APIRouter(tags=["system"])


@router.get("/system")
async def system_status(db: DbSession) -> dict:
    status = "operational"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        status = "degraded"
    return {"status": status, "updated_at": iso_msk(now_msk())}


@router.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"ok": True}
