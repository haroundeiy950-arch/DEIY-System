"""HTTP API for onboarding, verification, login and admin review."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.auth.service import user_public
from deiy.errors import AppError
from deiy.models import AIUsageRecord, AuditLog, User
from deiy.utils import jsonable

router = APIRouter(prefix="/auth", tags=["1. Onboarding & Access"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])


# --------------------------------------------------------------------- schemas
class RegisterRequest(BaseModel):
    full_name: str = Field(..., examples=["Amina Yusuf Hassan Ali"])
    email: str = Field(..., examples=["amina@example.com"])
    password: str = Field(..., min_length=8, examples=["StrongPass1"])
    photo: str = Field(..., description="https URL or image data URI")
    date_of_birth: date
    country: str = Field(..., examples=["Somalia"])


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


# ------------------------------------------------------------------ onboarding
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


@router.post("/logout", status_code=200)
def logout(user: User = Depends(get_current_user)):
    # Stateless JWT: the client discards the token. Kept for API symmetry.
    return {"message": "Signed out.", "user_id": user.id}


# ----------------------------------------------------------------- admin review
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
