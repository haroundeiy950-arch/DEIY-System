"""Typed application errors mapped to HTTP responses by the API layer."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class DependencyUnavailable(AppError):
    status_code = 503
    code = "dependency_unavailable"
