"""Password hashing, signed tokens (JWT HS256) and RBAC helpers.

Implemented with the standard library only, so the backend has no native
dependencies.  The token format is a regular compact JWT and can be verified by
any standard library (PyJWT, jose, ...).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from deiy.errors import Forbidden, Unauthorized

PBKDF2_ITERATIONS = 260_000

ROLES = ("admin", "teacher", "student", "proctor")

# Capability matrix backing the RBAC section of the specification.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "platform.manage",
        "users.review",
        "users.manage",
        "courses.manage",
        "content.manage",
        "exams.manage",
        "exams.proctor",
        "rooms.manage",
        "reports.view",
    },
    "teacher": {
        "courses.manage",
        "content.manage",
        "exams.manage",
        "rooms.create",
        "grades.manage",
    },
    "student": {
        "content.view",
        "exams.take",
        "rooms.join",
        "rooms.create",
        "grades.view",
    },
    "proctor": {
        "exams.proctor",
        "identity.verify",
        "reports.view",
    },
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        _b64e(salt),
        _b64e(digest),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_secret(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def sign_token(
    payload: dict[str, Any],
    secret: str,
    *,
    ttl_seconds: int | None = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    if ttl_seconds is not None:
        body.setdefault("iat", int(time.time()))
        body["exp"] = int(time.time()) + int(ttl_seconds)
    segments = [
        _b64e(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64e(json.dumps(body, separators=(",", ":"), default=str).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64e(signature))
    return ".".join(segments)


def decode_token(token: str, secret: str, *, expected_purpose: str | None = None) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(signature_b64)):
            raise Unauthorized("Invalid token signature")
        payload = json.loads(_b64d(payload_b64))
        if "exp" in payload and int(payload["exp"]) < int(time.time()):
            raise Unauthorized("Token expired")
        if expected_purpose and payload.get("purpose") != expected_purpose:
            raise Unauthorized("Token purpose mismatch")
        return payload
    except Unauthorized:
        raise
    except Exception as exc:  # malformed tokens
        raise Unauthorized("Malformed token") from exc


def create_access_token(user_id: str, role: str, secret: str, ttl_seconds: int) -> str:
    return sign_token(
        {"sub": user_id, "role": role, "purpose": "access", "typ": "access"},
        secret,
        ttl_seconds=ttl_seconds,
    )


def require_capability(role: str, capability: str) -> None:
    if capability not in ROLE_PERMISSIONS.get(role, set()):
        raise Forbidden(f"Role '{role}' is not allowed to perform '{capability}'")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
