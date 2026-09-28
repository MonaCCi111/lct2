"""Зависимости: сессия БД и роль RBAC (INTEGRATION_SPEC §3.5)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import forbidden
from app.core.database import get_session

ROLES = ("dispatcher", "supervisor")


async def get_role(x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None) -> str:
    role = (x_user_role or "dispatcher").strip().lower()
    if role not in ROLES:
        raise forbidden(f"Неизвестная роль '{role}'. Допустимые: dispatcher, supervisor")
    return role


async def get_user_id(x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None, role: str = Depends(get_role)) -> str:
    """Идентификатор автора действий. До появления аутентификации берётся из X-User-Id, иначе - роль."""
    return (x_user_id or role).strip()


def require_role(*allowed: str):
    async def _check(role: str = Depends(get_role)) -> str:
        if role not in allowed:
            raise forbidden(f"Действие доступно только ролям: {', '.join(allowed)}")
        return role

    return _check


DbSession = Annotated[AsyncSession, Depends(get_session)]
Role = Annotated[str, Depends(get_role)]
UserId = Annotated[str, Depends(get_user_id)]
