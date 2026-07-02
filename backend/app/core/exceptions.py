"""Custom application exceptions and FastAPI exception handlers."""
from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class LBROException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(LBROException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", 404)


class PermissionDeniedError(LBROException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(detail, 403)


class ConflictError(LBROException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(detail, 409)


class ValidationError(LBROException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(detail, 422)


async def lbro_exception_handler(request: Request, exc: LBROException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
