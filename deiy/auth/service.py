"""Onboarding, email verification, admin approval, academic IDs and login.

Implements specification section 1 end to end:

* four-part name, email/password, photo, date of birth, country;
* ``Pending Approval`` status + automated welcome email;
* 6-digit OTP **or** activation link;
* admin approve/reject from the dashboard;
* automatic unique academic/student ID generation + activation email;
* RBAC-aware login for admin / teacher / student / proctor.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import date, timedelta

from sqlalchemy import select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from deiy.events import EventBus
from deiy.models import User, VerificationCode
from deiy.security import (
    create_access_token,
    generate_otp,
    hash_password,
    hash_secret,
    sign_token,
    verify_password,
)
from deiy.utils import is_email, new_id, split_name, utcnow

logger = logging.getLogger(__name__)

_NAME_PART_RE = re.compile(r"^[^\W\d_][\w'’\-.]*$", re.UNICODE)
_DATA_URI_RE = re.compile(r"^data:image/(png|jpe?g|webp|gif);base64,(.+)$", re.IGNORECASE | re.S)
MAX_PHOTO_BYTES = 5 * 1024 * 1024


class AuthService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        mailer,
        ai,
        events: EventBus,
        storage,
    ) -> None:
        self.db = db
        self.settings = settings
        self.mailer = mailer
        self.ai = ai
        self.events = events
        self.storage = storage

    # ------------------------------------------------------------- validation
    def _validate_registration(self, data: dict) -> tuple[list[str], date]:
        parts = split_name(data.get("full_name", ""))
        if len(parts) < 4:
            raise ValidationFailed(
                "A four-part full name is required (first, second, third, family).",
                details={"received_parts": len(parts)},
            )
        for part in parts:
            if not _NAME_PART_RE.match(part):
                raise ValidationFailed(f"Invalid name part: '{part}'")
        email = (data.get("email") or "").strip().lower()
        if not is_email(email):
            raise ValidationFailed("A valid email address is required.")
        password = data.get("password") or ""
        if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(
            r"[a-z]", password
        ) or not re.search(r"\d", password):
            raise ValidationFailed(
                "Password must be at least 8 characters and include upper case, "
                "lower case and a digit."
            )
        photo = (data.get("photo") or "").strip()
        if not photo:
            raise ValidationFailed("A personal photograph is required.")
        if not photo.startswith(("http://", "https://", "data:image/")):
            raise ValidationFailed("Photo must be an https URL or an image data URI.")
        dob = data.get("date_of_birth")
        if not isinstance(dob, date):
            raise ValidationFailed("Date of birth is required (YYYY-MM-DD).")
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if dob >= today:
            raise ValidationFailed("Date of birth must be in the past.")
        if age < self.settings.minimum_age:
            raise ValidationFailed(
                f"Students must be at least {self.settings.minimum_age} years old."
            )
        country = (data.get("country") or "").strip()
        if not country:
            raise ValidationFailed("Country / residence is required.")
        data["email"] = email
        data["country"] = country
        return parts, dob

    def _store_photo(self, user_id: str, photo: str) -> str:
        match = _DATA_URI_RE.match(photo)
        if not match:
            return photo
        extension = match.group(1).lower().replace("jpeg", "jpg")
        try:
            payload = base64.b64decode(match.group(2), validate=True)
        except Exception as exc:
            raise ValidationFailed("Photo data URI is not valid base64.") from exc
        if len(payload) > MAX_PHOTO_BYTES:
            raise ValidationFailed("Photo must be 5 MB or smaller.")
        key = f"users/{user_id}/photo.{extension}"
        self.storage.put_bytes(key, payload)
        if hasattr(self.storage, "presign"):
            return self.storage.presign(key, ttl_seconds=7 * 24 * 3600)
        return key

    # ------------------------------------------------------------- registration
    def register(self, data: dict) -> dict:
        parts, dob = self._validate_registration(data)
        email = data["email"]
        with self.db.session() as session:
            existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                raise Conflict("An account with this email already exists.")

            user_id = new_id()
            photo_url = self._store_photo(user_id, data["photo"])
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            review = self.ai.review_registration(
                {
                    "email": email,
                    "country": data["country"],
                    "photo_url": photo_url,
                    "age": age,
                    "minimum_age": self.settings.minimum_age,
                    "name_parts": len(parts),
                }
            )
            user = User(
                id=user_id,
                full_name=" ".join(parts),
                email=email,
                password_hash=hash_password(data["password"]),
                photo_url=photo_url,
                date_of_birth=dob,
                country=data["country"],
                role="student",
                status="pending_email",
                email_verified=False,
                ai_review=review.to_dict(),
            )
            session.add(user)
            session.flush()
            code, link = self._issue_verification(session, user)
            record_audit(
                session,
                action="user.registered",
                actor_id=user.id,
                target=user.id,
                meta={"ai_recommendation": review.recommendation, "risk": review.risk_score},
            )

        self._send_welcome(user)
        self._send_verification(user, code, link)
        self.events.publish(
            "user.registered",
            {"user_id": user.id, "email": user.email, "ai_review": review.to_dict()},
        )
        return {
            "user": user_public(user, include_review=True),
            "verification": {
                "channel": "email",
                "otp_expires_in": self.settings.otp_ttl_seconds,
                "link_expires_in": self.settings.activation_token_ttl_seconds,
            },
            "dev_code": code if self.settings.expose_dev_codes and not self.settings.is_production else None,
            "dev_link": link if self.settings.expose_dev_codes and not self.settings.is_production else None,
        }

    def _issue_verification(self, session, user: User) -> tuple[str, str]:
        code = generate_otp()
        token = sign_token(
            {"sub": user.id, "purpose": "email_verify", "jti": new_id()},
            self.settings.secret_key,
            ttl_seconds=self.settings.activation_token_ttl_seconds,
        )
        row = VerificationCode(
            user_id=user.id,
            code_hash=hash_secret(code, self.settings.secret_key),
            token_hash=hash_secret(token, self.settings.secret_key),
            purpose="email_verify",
            expires_at=utcnow() + timedelta(seconds=self.settings.activation_token_ttl_seconds),
        )
        session.add(row)
        link = f"{self.settings.public_base_url}/ui/#/verify?token={token}"
        return code, link

    def _send_welcome(self, user: User) -> None:
        self.mailer.send(
            user.email,
            "Welcome to DEIY - your account is pending approval",
            (
                f"Hello {user.full_name},\n\n"
                "Thank you for registering on DEIY. Your account status is now "
                "'Pending Approval'. Please verify your email address using the code "
                "in the next message. An administrator will then review your application.\n\n"
                "The DEIY Team"
            ),
        )

    def _send_verification(self, user: User, code: str, link: str) -> None:
        self.mailer.send(
            user.email,
            "DEIY - verify your email address",
            (
                f"Hello {user.full_name},\n\n"
                f"Your verification code is: {code}\n\n"
                f"Or activate with this link (valid {self.settings.activation_token_ttl_seconds // 3600}h):\n"
                f"{link}\n\n"
                "If you did not create this account, ignore this message.\n\n"
                "The DEIY Team"
            ),
        )

    # ------------------------------------------------------------- verification
    def verify_email(
        self,
        *,
        email: str | None = None,
        code: str | None = None,
        token: str | None = None,
    ) -> User:
        if not code and not token:
            raise ValidationFailed("Provide either the 6-digit code or the activation link token.")
        with self.db.session() as session:
            user = None
            if email:
                user = session.execute(
                    select(User).where(User.email == email.strip().lower())
                ).scalar_one_or_none()
            elif token:
                # Activation links must work even when the visitor does not type
                # their email address again.
                try:
                    from deiy.security import decode_token

                    decoded = decode_token(
                        token, self.settings.secret_key, expected_purpose="email_verify"
                    )
                except Exception as exc:
                    raise ValidationFailed(
                        "Activation link is invalid or expired."
                    ) from exc
                user = session.get(User, decoded.get("sub"))
            if user is None:
                raise NotFound("Account not found.")
            if user.email_verified and user.status != "pending_email":
                return user

            rows = session.execute(
                select(VerificationCode)
                .where(
                    VerificationCode.user_id == user.id,
                    VerificationCode.purpose == "email_verify",
                    VerificationCode.consumed_at.is_(None),
                )
                .order_by(VerificationCode.created_at.desc())
            ).scalars().all()
            if not rows:
                raise ValidationFailed("No active verification code. Request a new one.")
            row = rows[0]
            if row.expires_at < utcnow():
                raise ValidationFailed("Verification code expired. Request a new one.")

            verified = False
            if code:
                if row.attempts >= self.settings.otp_max_attempts:
                    raise ValidationFailed("Too many attempts. Request a new code.")
                if utcnow() > row.created_at + timedelta(seconds=self.settings.otp_ttl_seconds):
                    raise ValidationFailed("The 6-digit code has expired; use the link or resend.")
                if hash_secret(code.strip(), self.settings.secret_key) == row.code_hash:
                    verified = True
                else:
                    row.attempts += 1
            if token and not verified:
                try:
                    from deiy.security import decode_token

                    decoded = decode_token(
                        token, self.settings.secret_key, expected_purpose="email_verify"
                    )
                except Exception as exc:
                    raise ValidationFailed("Activation link is invalid or expired.") from exc
                if decoded.get("sub") != user.id:
                    raise ValidationFailed("Activation link does not belong to this account.")
                if hash_secret(token, self.settings.secret_key) == row.token_hash:
                    verified = True
            if not verified:
                raise ValidationFailed("Invalid verification code or link.")

            row.consumed_at = utcnow()
            user.email_verified = True
            user.status = "pending_approval"
            record_audit(session, action="user.email_verified", actor_id=user.id, target=user.id)
            session.flush()

        self.mailer.send(
            user.email,
            "DEIY - email verified, awaiting admin approval",
            (
                f"Hello {user.full_name},\n\nYour email is verified. Your application is now "
                "in the admin review queue. You will receive your academic ID once approved.\n\n"
                "The DEIY Team"
            ),
        )
        self.events.publish("user.email_verified", {"user_id": user.id, "email": user.email})
        return user

    def resend_verification(self, email: str) -> dict:
        with self.db.session() as session:
            user = session.execute(
                select(User).where(User.email == (email or "").strip().lower())
            ).scalar_one_or_none()
            if user is None:
                raise NotFound("Account not found.")
            if user.email_verified:
                raise Conflict("Email is already verified.")
            code, link = self._issue_verification(session, user)
            record_audit(session, action="user.verification_resent", actor_id=user.id)
        self._send_verification(user, code, link)
        return {
            "message": "Verification email sent.",
            "dev_code": code if self.settings.expose_dev_codes and not self.settings.is_production else None,
        }

    # ---------------------------------------------------------------- approval
    def approve(self, user_id: str, *, actor_id: str | None = None) -> User:
        with self.db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise NotFound("Student application not found.")
            if user.status == "active":
                return user
            if not user.email_verified:
                raise ValidationFailed("The applicant has not verified their email yet.")
            if user.status not in {"pending_approval", "pending_email"}:
                raise Conflict(f"Cannot approve an account with status '{user.status}'.")
            user.academic_id = self._next_academic_id(session, user.role)
            user.status = "active"
            user.rejection_reason = None
            record_audit(
                session,
                action="user.approved",
                actor_id=actor_id,
                target=user.id,
                meta={"academic_id": user.academic_id},
            )
            session.flush()
            academic_id = user.academic_id

        self.mailer.send(
            user.email,
            "DEIY - your account is activated",
            (
                f"Hello {user.full_name},\n\n"
                "Your application has been approved.\n\n"
                f"Academic / Student ID: {academic_id}\n"
                f"Sign in: {self.settings.public_base_url}/auth/login\n\n"
                "Use this academic ID for study rooms, exams and support.\n\n"
                "The DEIY Team"
            ),
        )
        self.events.publish(
            "user.approved",
            {"user_id": user.id, "email": user.email, "academic_id": academic_id},
        )
        return user

    def reject(self, user_id: str, reason: str, *, actor_id: str | None = None) -> User:
        with self.db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise NotFound("Student application not found.")
            if user.status == "active":
                raise Conflict("Active accounts cannot be rejected; suspend instead.")
            user.status = "rejected"
            user.rejection_reason = reason[:500]
            record_audit(
                session,
                action="user.rejected",
                actor_id=actor_id,
                target=user.id,
                meta={"reason": reason},
            )
            session.flush()
        self.mailer.send(
            user.email,
            "DEIY - application update",
            (
                f"Hello {user.full_name},\n\nYour application was not approved.\n"
                f"Reason: {reason}\n\nYou may contact support for clarification.\n\n"
                "The DEIY Team"
            ),
        )
        self.events.publish("user.rejected", {"user_id": user.id, "reason": reason})
        return user

    def _next_academic_id(self, session, role: str) -> str:
        year = date.today().year
        if role in {"admin", "teacher", "proctor"}:
            prefix = role.upper()[:5]
            count = session.execute(
                select(User).where(User.academic_id.like(f"DEIY-{prefix}-%"))
            ).scalars().all()
            return f"DEIY-{prefix}-{len(count) + 1:04d}"
        for sequence in range(1, 10_000_000):
            candidate = f"DEIY-{year}-{sequence:06d}"
            exists = session.execute(
                select(User.id).where(User.academic_id == candidate)
            ).first()
            if not exists:
                return candidate
        raise Conflict("Academic ID space exhausted.")

    # --------------------------------------------------------------- staff/admin
    def create_staff(self, data: dict, *, role: str, actor_id: str | None = None) -> User:
        if role not in {"admin", "teacher", "proctor"}:
            raise ValidationFailed("Staff role must be admin, teacher or proctor.")
        parts = split_name(data.get("full_name", ""))
        if len(parts) < 4:
            raise ValidationFailed("A four-part full name is required.")
        email = (data.get("email") or "").strip().lower()
        if not is_email(email):
            raise ValidationFailed("A valid email address is required.")
        password = data.get("password") or ""
        if len(password) < 8:
            raise ValidationFailed("Password must be at least 8 characters.")
        with self.db.session() as session:
            if session.execute(select(User).where(User.email == email)).scalar_one_or_none():
                raise Conflict("An account with this email already exists.")
            user = User(
                id=new_id(),
                full_name=" ".join(parts),
                email=email,
                password_hash=hash_password(password),
                country=data.get("country") or "N/A",
                role=role,
                status="active",
                email_verified=True,
                academic_id=self._next_academic_id(session, role),
            )
            session.add(user)
            record_audit(
                session,
                action="staff.created",
                actor_id=actor_id,
                target=user.id,
                meta={"role": role},
            )
            session.flush()
        self.mailer.send(
            user.email,
            "DEIY - staff account created",
            (
                f"Hello {user.full_name},\n\nA {role} account was created for you.\n"
                f"Academic / Staff ID: {user.academic_id}\n"
                f"Sign in: {self.settings.public_base_url}/auth/login\n"
            ),
        )
        return user

    def ensure_admin(self, email: str, password: str, full_name: str = "System Administrator Account") -> User:
        """Idempotent bootstrap used by seed scripts and tests."""

        with self.db.session() as session:
            existing = session.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
            if existing:
                return existing
            user = User(
                id=new_id(),
                full_name=full_name,
                email=email.lower(),
                password_hash=hash_password(password),
                country="N/A",
                role="admin",
                status="active",
                email_verified=True,
                academic_id=self._next_academic_id(session, "admin"),
            )
            session.add(user)
            record_audit(session, action="admin.bootstrap", actor_id=user.id, target=user.id)
            session.flush()
            return user

    # ------------------------------------------------------------------- login
    def login(self, email: str, password: str) -> tuple[str, User]:
        with self.db.session() as session:
            user = session.execute(
                select(User).where(User.email == (email or "").strip().lower())
            ).scalar_one_or_none()
            if user is None or not verify_password(password, user.password_hash):
                raise Unauthorized("Invalid email or password.")
            if user.status == "pending_email":
                raise Forbidden(
                    "Email not verified. Verify with the 6-digit code or activation link.",
                    code="email_not_verified",
                )
            if user.status == "pending_approval":
                raise Forbidden(
                    "Your account is pending admin approval.", code="pending_approval"
                )
            if user.status == "rejected":
                raise Forbidden("Your application was rejected.", code="application_rejected")
            if user.status != "active":
                raise Forbidden(f"Account is not active (status: {user.status}).")
            user.last_login_at = utcnow()
            token = create_access_token(
                user.id, user.role, self.settings.secret_key, self.settings.access_token_ttl_seconds
            )
            record_audit(session, action="user.login", actor_id=user.id)
            session.flush()
            return token, user

    def dev_admin_session(self) -> tuple[str, User]:
        """Issue a local-development session for the existing admin account."""
        if not self.settings.auto_admin or self.settings.is_production:
            raise Forbidden("Development auto-admin is disabled.")

        email = "haroundeiy950@gmail.com"

        with self.db.session() as session:
            user = session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

            if user is None:
                raise NotFound("Development admin account was not found.")

            if user.role != "admin" or user.status != "active" or not user.email_verified:
                raise Forbidden("The development admin account is not eligible.")

            user.last_login_at = utcnow()
            token = create_access_token(
                user.id,
                user.role,
                self.settings.secret_key,
                self.settings.access_token_ttl_seconds,
            )
            record_audit(session, action="user.dev_auto_login", actor_id=user.id)
            session.flush()
            return token, user
    def get_user(self, user_id: str) -> User:
        with self.db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise NotFound("User not found.")
            return user

    def list_users(self, *, status: str | None = None, role: str | None = None) -> list[User]:
        with self.db.session() as session:
            query = select(User)
            if status:
                query = query.where(User.status == status)
            if role:
                query = query.where(User.role == role)
            query = query.order_by(User.created_at.desc())
            return list(session.execute(query).scalars().all())

    def set_role(self, user_id: str, role: str, *, actor_id: str | None = None) -> User:
        if role not in {"admin", "teacher", "student", "proctor"}:
            raise ValidationFailed("Unknown role.")
        with self.db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise NotFound("User not found.")
            user.role = role
            record_audit(
                session,
                action="user.role_changed",
                actor_id=actor_id,
                target=user.id,
                meta={"role": role},
            )
            session.flush()
            return user


def user_public(user: User, *, include_review: bool = False) -> dict:
    payload = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "email_verified": user.email_verified,
        "academic_id": user.academic_id,
        "photo_url": user.photo_url,
        "country": user.country,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    if include_review:
        payload["ai_review"] = user.ai_review
        payload["rejection_reason"] = user.rejection_reason
    return payload
