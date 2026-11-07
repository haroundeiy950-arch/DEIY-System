"""Shared FastAPI dependencies: container access, bearer auth and RBAC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from deiy.errors import Forbidden, Unauthorized
from deiy.models import User
from deiy.security import decode_token

if TYPE_CHECKING:  # pragma: no cover
    from deiy.container import AppContainer

_bearer = HTTPBearer(auto_error=False, description="DEIY access token")


def get_container(request: Request) -> "AppContainer":
    return request.app.state.container


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: "AppContainer" = Depends(get_container),
) -> User:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Authentication required.", code="missing_token")
    payload = decode_token(
        credentials.credentials, container.settings.secret_key, expected_purpose="access"
    )
    user = container.auth.get_user(payload.get("sub", ""))
    if user.status != "active":
        raise Forbidden("Account is not active.", code="account_inactive")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise Forbidden(
                f"This endpoint requires one of: {', '.join(roles)}.",
                code="insufficient_role",
            )
        return user

    return dependency


def require_capability(capability: str) -> Callable[..., User]:
    from deiy.security import ROLE_PERMISSIONS

    def dependency(user: User = Depends(get_current_user)) -> User:
        if capability not in ROLE_PERMISSIONS.get(user.role, set()):
            raise Forbidden(
                f"Role '{user.role}' lacks capability '{capability}'.",
                code="insufficient_capability",
            )
        return user

    return dependency
