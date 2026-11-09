"""Persisted, audited runtime configuration for platform administrators.

The specification gives admins "system configuration" as part of complete
platform management.  Operational policy values are stored in
``system_settings`` so they survive a restart, validated against explicit
bounds, applied to the shared ``Settings`` instance immediately, and written to
the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import ValidationFailed
from deiy.models import SystemSetting
from deiy.utils import utcnow


@dataclass(frozen=True, slots=True)
class SettingSpec:
    kind: type
    minimum: int | None = None
    maximum: int | None = None
    description: str = ""

    def public(self) -> dict:
        payload: dict[str, Any] = {
            "type": self.kind.__name__,
            "description": self.description,
        }
        if self.minimum is not None:
            payload["minimum"] = self.minimum
        if self.maximum is not None:
            payload["maximum"] = self.maximum
        return payload


EDITABLE_SETTINGS: dict[str, SettingSpec] = {
    "minimum_age": SettingSpec(
        int, 15, 100, "Minimum age for student registration (cannot be below 15)."
    ),
    "expose_dev_codes": SettingSpec(
        bool, None, None, "Return OTPs and activation links in API responses (development only)."
    ),
    "room_max_duration_minutes": SettingSpec(
        int, 5, 240, "Maximum study-room duration before automatic closure."
    ),
    "default_exam_duration_minutes": SettingSpec(
        int, 5, 480, "Default exam duration when authoring an exam."
    ),
    "require_camera_for_exam": SettingSpec(
        bool, None, None, "Block exam access unless the webcam check succeeds."
    ),
    "access_token_ttl_seconds": SettingSpec(
        int, 300, 30 * 24 * 3600, "JWT access-token lifetime in seconds."
    ),
    "watermark_ttl_seconds": SettingSpec(
        int, 60, 24 * 3600, "Validity window for issued watermark tokens."
    ),
    "media_url_ttl_seconds": SettingSpec(
        int, 60, 7 * 24 * 3600, "Validity window for signed media URLs."
    ),
}


class ConfigService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.overrides: set[str] = set()

    # ------------------------------------------------------------------ read
    def values(self) -> dict[str, Any]:
        return {name: getattr(self.settings, name) for name in EDITABLE_SETTINGS}

    def public(self) -> dict:
        return {
            "summary": self.settings.summary(),
            "values": self.values(),
            "allowed": {
                name: spec.public() for name, spec in EDITABLE_SETTINGS.items()
            },
            "overrides": sorted(self.overrides),
        }

    # ------------------------------------------------------------------ load
    def load(self) -> dict[str, Any]:
        """Apply persisted overrides to the shared settings object."""

        applied: dict[str, Any] = {}
        with self.db.session() as session:
            rows = session.execute(select(SystemSetting)).scalars().all()
            for row in rows:
                spec = EDITABLE_SETTINGS.get(row.key)
                if spec is None:
                    continue
                try:
                    value = self._validate(row.key, row.value, spec)
                except ValidationFailed:
                    continue
                setattr(self.settings, row.key, value)
                applied[row.key] = value
        self.overrides = set(applied)
        return applied

    # ---------------------------------------------------------------- update
    def update(self, changes: dict[str, Any], *, actor_id: str | None = None) -> dict:
        if not changes:
            raise ValidationFailed("Provide at least one configuration value.")
        unknown = sorted(set(changes) - set(EDITABLE_SETTINGS))
        if unknown:
            raise ValidationFailed(
                "Unknown configuration key(s): " + ", ".join(unknown),
                details={"allowed": sorted(EDITABLE_SETTINGS)},
            )

        validated: dict[str, Any] = {}
        for key, value in changes.items():
            validated[key] = self._validate(key, value, EDITABLE_SETTINGS[key])

        with self.db.session() as session:
            existing = {
                row.key: row
                for row in session.execute(
                    select(SystemSetting).where(SystemSetting.key.in_(validated))
                ).scalars().all()
            }
            for key, value in validated.items():
                row = existing.get(key)
                if row is None:
                    row = SystemSetting(key=key, value=value, updated_by=actor_id)
                    session.add(row)
                else:
                    row.value = value
                    row.updated_by = actor_id
                    row.updated_at = utcnow()
            record_audit(
                session,
                action="admin.config.updated",
                actor_id=actor_id,
                target="system_settings",
                meta={"changes": validated},
            )

        for key, value in validated.items():
            setattr(self.settings, key, value)
        self.overrides.update(validated)
        return validated

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _validate(key: str, value: Any, spec: SettingSpec) -> Any:
        if spec.kind is bool:
            if not isinstance(value, bool):
                raise ValidationFailed(f"'{key}' must be a boolean.")
            return value
        if spec.kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationFailed(f"'{key}' must be an integer.")
            if spec.minimum is not None and value < spec.minimum:
                raise ValidationFailed(
                    f"'{key}' must be at least {spec.minimum}.",
                    details={"minimum": spec.minimum},
                )
            if spec.maximum is not None and value > spec.maximum:
                raise ValidationFailed(
                    f"'{key}' must be at most {spec.maximum}.",
                    details={"maximum": spec.maximum},
                )
            return value
        raise ValidationFailed(f"'{key}' has an unsupported type.")


__all__ = ["ConfigService", "EDITABLE_SETTINGS", "SettingSpec"]
