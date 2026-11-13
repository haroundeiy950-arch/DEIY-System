"""HTTP API for onboarding, verification, login and admin review."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select, text

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.auth.constants import AUTH_PROVIDERS, LANGUAGES, PROGRAMS
from deiy.auth.service import user_public
from deiy.errors import AppError, Conflict, ValidationFailed
from deiy.models import AIUsageRecord, AuditLog, User
from deiy.utils import jsonable

router = APIRouter(prefix="/auth", tags=["1. Onboarding & Access"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])



class RegisterRequest(BaseModel):
    full_name: str = Field(..., examples=["Amina Yusuf Hassan Ali"])
    email: str = Field(..., examples=["amina@example.com"])
    password: str = Field(..., min_length=8, examples=["StrongPass1"])
    photo: str = Field(..., description="https URL or image data URI")
    date_of_birth: date
    program: str = Field(..., examples=["Computer Science"])
    phone_number: str = Field(..., examples=["+252 61 234 5678"])
    father_phone_number: str = Field(..., examples=["+252 61 876 5432"])
    nationality: str = Field(..., examples=["Somali"])
    country: str | None = Field(None, examples=["Somalia"])
    auth_provider: str = Field(
        "email",
        description="email | google | facebook | other",
        examples=["email"],
    )
    language: str = Field("en", description="en | so | ar", examples=["en"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    program: str | None = None
    phone_number: str | None = None
    father_phone_number: str | None = None
    nationality: str | None = None
    country: str | None = None
    photo: str | None = None
    language: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    program: str | None = None
    phone_number: str | None = None
    father_phone_number: str | None = None
    nationality: str | None = None
    country: str | None = None
    role: str | None = None
    status: str | None = None
    language: str | None = None


class VerifyRequest(BaseModel):
    email: str | None = Field(None, description="Required when verifying with a code.")
    code: str | None = Field(None, min_length=6, max_length=6)
    token: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ResendRequest(BaseModel):
    email: str


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class RoleRequest(BaseModel):
    role: str


class StaffCreateRequest(BaseModel):
    full_name: str
    email: str
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(admin|teacher|proctor)$")
    country: str | None = None


class ConfigUpdateRequest(BaseModel):
    values: dict[str, Any] = Field(
        ...,
        description="Editable policy keys and their new values.",
        examples=[{"default_exam_duration_minutes": 90}],
    )



@router.get("/options")
def admission_options(container=Depends(get_container)):
    """Programs, languages and sign-in providers offered by the platform."""

    return {
        "programs": PROGRAMS,
        "languages": LANGUAGES,
        "auth_providers": AUTH_PROVIDERS,
        "minimum_age": max(15, int(container.settings.minimum_age)),
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, container=Depends(get_container)):
    return container.auth.register(payload.model_dump())


@router.post("/verify-email")
def verify_email(payload: VerifyRequest, container=Depends(get_container)):
    user = container.auth.verify_email(
        email=payload.email, code=payload.code, token=payload.token
    )
    return {
        "message": "Email verified. Your application is pending admin approval.",
        "user": user_public(user),
    }


@router.get("/verify-email", include_in_schema=False)
def verify_email_link(token: str, container=Depends(get_container)):
    """Handle an activation link from an email by forwarding into the web app."""

    try:
        container.auth.verify_email(token=token)
    except AppError as exc:
        target = (
            "/ui/#/verify?token="
            f"{quote(token, safe='')}&error={quote(exc.message, safe='')}"
        )
        return RedirectResponse(target, status_code=303)
    return RedirectResponse("/ui/#/login?verified=1", status_code=303)


@router.post("/resend-verification")
def resend_verification(payload: ResendRequest, container=Depends(get_container)):
    return container.auth.resend_verification(payload.email)


@router.post("/login")
def login(payload: LoginRequest, container=Depends(get_container)):
    token, user = container.auth.login(payload.email, payload.password)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": container.settings.access_token_ttl_seconds,
        "user": user_public(user),
    }


@router.post("/dev-session")
def dev_admin_session(request: Request, container=Depends(get_container)):
    if not container.settings.auto_admin or container.settings.is_production:
        raise HTTPException(status_code=404, detail="Not found.")

    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Local access only.")

    token, user = container.auth.dev_admin_session()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": container.settings.access_token_ttl_seconds,
        "user": user_public(user),
    }

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_public(user)}


@router.patch("/me")
def update_me(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    updated = container.auth.update_profile(
        user.id, payload.model_dump(exclude_unset=True)
    )
    return {"message": "Profile updated.", "user": user_public(updated)}


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    container.auth.change_password(
        user.id, payload.current_password, payload.new_password
    )
    return {"message": "Password updated."}


@router.post("/logout", status_code=200)
def logout(user: User = Depends(get_current_user)):
   
    return {"message": "Signed out.", "user_id": user.id}



@admin_router.get("/users")
def list_users(
    status: str | None = Query(None, description="pending_approval, active, rejected..."),
    role: str | None = None,
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    users = container.auth.list_users(status=status, role=role)
    return {"count": len(users), "users": [user_public(u, include_review=True) for u in users]}


@admin_router.get("/applications")
def pending_applications(
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    users = container.auth.list_users(status="pending_approval", role="student")
    return {
        "count": len(users),
        "applications": [user_public(u, include_review=True) for u in users],
    }


@admin_router.get("/users/{user_id}")
def get_user(
    user_id: str,
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    return {"user": user_public(container.auth.get_user(user_id), include_review=True)}


@admin_router.post("/users/{user_id}/approve")
def approve_user(
    user_id: str,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    user = container.auth.approve(user_id, actor_id=admin.id)
    return {"message": "Application approved.", "user": user_public(user, include_review=True)}


@admin_router.post("/users/{user_id}/reject")
def reject_user(
    user_id: str,
    payload: RejectRequest,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    user = container.auth.reject(user_id, payload.reason, actor_id=admin.id)
    return {"message": "Application rejected.", "user": user_public(user, include_review=True)}


@admin_router.patch("/users/{user_id}/role")
def set_role(
    user_id: str,
    payload: RoleRequest,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    user = container.auth.set_role(user_id, payload.role, actor_id=admin.id)
    return {"message": "Role updated.", "user": user_public(user)}


@admin_router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    changes = payload.model_dump(exclude_unset=True)
    if user_id == admin.id and changes.get("role") not in (None, "admin"):
        raise ValidationFailed("You cannot remove your own administrator role.")
    if user_id == admin.id and changes.get("status") not in (None, "active"):
        raise ValidationFailed("You cannot deactivate your own administrator account.")
    user = container.auth.update_user(user_id, changes, actor_id=admin.id)
    return {"message": "User updated.", "user": user_public(user, include_review=True)}


@admin_router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    if user_id == admin.id:
        raise Conflict("You cannot delete your own account.")
    user = container.auth.delete_user(user_id, actor_id=admin.id)
    return {
        "message": "User deleted. The account can no longer sign in.",
        "user": user_public(user, include_review=True),
    }


@admin_router.get("/database")
def database_overview(
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    """Row counts for every table so admins can see what the database holds."""

    inspector = inspect(container.db.engine)
    tables = []
    total = 0
    with container.db.session() as session:
        for name in sorted(inspector.get_table_names()):
            if name.startswith("sqlite_"):
                continue
            count = session.execute(
                text(f'SELECT COUNT(*) FROM "{name}"')
            ).scalar() or 0
            tables.append({"table": name, "rows": int(count)})
            total += int(count)
    return {
        "dialect": container.db.engine.dialect.name,
        "table_count": len(tables),
        "total_rows": total,
        "tables": tables,
    }


@admin_router.get("/database/download")
def download_database(
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    """Download a consistent SQLite snapshot (safe while WAL files are active)."""

    import os
    import sqlite3
    import tempfile
    from pathlib import Path

    from fastapi.responses import FileResponse
    from sqlalchemy.engine import make_url
    from starlette.background import BackgroundTask

    url = make_url(container.db.url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database in {":memory:", ""}:
        raise ValidationFailed(
            "Database download is only available for file-based SQLite deployments."
        )
    source = Path(url.database).expanduser().resolve()
    if not source.exists():
        raise HTTPException(status_code=404, detail="The database file does not exist yet.")

    fd, snapshot = tempfile.mkstemp(prefix="deiy-backup-", suffix=".db")
    os.close(fd)
    try:
        source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            target_conn = sqlite3.connect(snapshot)
            try:
                source_conn.backup(target_conn)
            finally:
                target_conn.close()
        finally:
            source_conn.close()
    except Exception as error:  # pragma: no cover - filesystem/database failure
        try:
            os.unlink(snapshot)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Could not create the database backup: {error}")

    filename = f"deiy-backup-{date.today().isoformat()}.db"
    return FileResponse(
        snapshot,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(os.unlink, snapshot),
    )


@admin_router.post("/staff", status_code=201)
def create_staff(
    payload: StaffCreateRequest,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    user = container.auth.create_staff(
        payload.model_dump(), role=payload.role, actor_id=admin.id
    )
    return {"message": "Staff account created.", "user": user_public(user)}


@admin_router.get("/config")
def get_config(
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    return {"config": container.config.public()}


@admin_router.patch("/config")
def update_config(
    payload: ConfigUpdateRequest,
    admin: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    updated = container.config.update(payload.values, actor_id=admin.id)
    return {
        "message": "Configuration updated.",
        "updated": updated,
        "config": container.config.public(),
    }


@admin_router.get("/ai-usage")
def ai_usage(
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    with container.db.session() as session:
        rows = session.execute(
            select(
                AIUsageRecord.task,
                AIUsageRecord.provider,
                func.count(AIUsageRecord.id),
                func.sum(AIUsageRecord.units),
                func.sum(AIUsageRecord.cost_usd),
            ).group_by(AIUsageRecord.task, AIUsageRecord.provider)
        ).all()
        total = session.execute(select(func.sum(AIUsageRecord.cost_usd))).scalar() or 0.0
    return {
        "total_cost_usd": round(float(total), 6),
        "breakdown": [
            {
                "task": task,
                "provider": provider,
                "calls": calls,
                "units": round(float(units or 0), 4),
                "cost_usd": round(float(cost or 0), 6),
            }
            for task, provider, calls, units, cost in rows
        ],
        "health": container.ai.health(),
    }


@admin_router.get("/audit-logs")
def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    with container.db.session() as session:
        rows = session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).scalars().all()
    return {
        "count": len(rows),
        "logs": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "action": row.action,
                "target": row.target,
                "meta": jsonable(row.meta),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
