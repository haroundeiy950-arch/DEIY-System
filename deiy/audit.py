"""Append-only audit trail helper (used by every privileged action)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from deiy.models import AuditLog
from deiy.utils import new_id


def record_audit(
    session: Session,
    *,
    action: str,
    actor_id: str | None = None,
    target: str | None = None,
    meta: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        id=new_id(),
        actor_id=actor_id,
        action=action,
        target=target,
        meta=meta or {},
    )
    session.add(entry)
    return entry
