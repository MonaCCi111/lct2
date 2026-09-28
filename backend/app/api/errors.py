"""Единый формат ошибок.

v1 (INTEGRATION_SPEC §3.4 + фронт читает top-level `message`):
  {"error_code": "...", "code": "...", "message": "...", "details": null, "timestamp": "...+03:00"}
v2 (api_contract_v1.json): {"code": "...", "message": "...", "details": null}
Оба формата совместимы: v1-тело содержит все ключи v2.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.timeutil import iso_msk, now_msk


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details


def not_found(message: str, details: Any = None) -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", message, details)


def bad_request(message: str, details: Any = None) -> ApiError:
    return ApiError(400, "BAD_REQUEST", message, details)


def conflict(message: str, code: str = "CONFLICT", details: Any = None) -> ApiError:
    return ApiError(409, code, message, details)


def forbidden(message: str) -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def unprocessable(message: str, details: Any = None) -> ApiError:
    return ApiError(422, "UNPROCESSABLE", message, details)


def error_body(code: str, message: str, details: Any = None) -> dict:
    return {
        "error_code": code,
        "code": code,
        "message": message,
        "details": details,
        "timestamp": iso_msk(now_msk()),
    }


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    code = {404: "RESOURCE_NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    # Ошибки тела (POST/PATCH) - 400 по контракту фронта; ошибки query/path - тоже 400
    first = errors[0] if errors else {}
    loc = ".".join(str(p) for p in first.get("loc", []))
    msg = f"Некорректный запрос: {loc}: {first.get('msg', 'validation error')}" if first else "Некорректный запрос"
    safe = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in errors]
    return JSONResponse(status_code=400, content=error_body("VALIDATION_ERROR", msg, safe))
