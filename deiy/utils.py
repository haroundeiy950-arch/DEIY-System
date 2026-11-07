"""Small, dependency-free helpers shared across the DEIY codebase."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def utcnow() -> datetime:
    """Naive UTC timestamp.

    SQLite does not preserve tzinfo, so the whole project stores and compares
    naive UTC datetimes to avoid aware/naive comparison errors.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(value: datetime) -> datetime:
    """Normalise an incoming datetime to naive UTC."""

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def new_id(prefix: str = "") -> str:
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value


def iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.strip().lower()).strip("-") or "item"


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value or ""))


def split_name(full_name: str) -> list[str]:
    return [part for part in re.split(r"\s+", (full_name or "").strip()) if part]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def estimate_tokens(text: str) -> int:
    """Cheap token estimate used for cost accounting only."""

    return max(1, len(text or "") // 4)


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def jsonable(value: Any) -> Any:
    """Recursively convert datetimes to ISO strings for JSON responses."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value
