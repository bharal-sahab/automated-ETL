"""Typed application errors and FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base error for this application."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class IngestionError(AppError):
    """Outbound HTTP fetch of posts failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=502, details=details)


class DatabaseError(AppError):
    """SQLite read/write failed."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=503, details=details)


class PayloadValidationError(AppError):
    """External payload failed Pydantic validation."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=422, details=details)


class PipelineBusyError(AppError):
    """A pipeline run is already in progress."""

    def __init__(self, message: str = "Pipeline run already in progress") -> None:
        super().__init__(message, status_code=409)


class ConfigurationError(AppError):
    """Invalid source/processor name or plugin settings."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=400, details=details)


def _error_body(message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": message}
    if details:
        body["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach centralized JSON error handlers to the FastAPI app."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError %s: %s", type(exc).__name__, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message, exc.details),
        )

    @app.exception_handler(ValidationError)
    async def handle_pydantic_error(_request: Request, exc: ValidationError) -> JSONResponse:
        logger.warning("Pydantic validation failed: %s", exc)
        return JSONResponse(
            status_code=422,
            content=_error_body("Validation failed", {"errors": exc.errors()}),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body("Internal server error"),
        )
