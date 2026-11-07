"""DEIY - education platform backend.

This package implements the *DEIY System Architecture Specification Document*:

1. Onboarding, registration, OTP/activation, admin approval, academic IDs, RBAC
2. Content management, digital library, live streaming, watermarking, offline
3. Smart proctored exams with camera checks, strict timing and auto-save
4. Micro study rooms (10-15 students) with queued AI summaries
5. Utilities, notifications, helpdesk, gradebook and cost-aware AI infrastructure

The package root is the composition root: importing ``deiy`` gives you the
application factory (``create_app``), the wired object graph (``build_container``
/ ``AppContainer``), every domain service, and the AI/infra adapters.

Quick start::

    from deiy import create_app
    app = create_app()

Or run the server::

    uvicorn deiy:app --reload
"""

from __future__ import annotations

__title__ = "DEIY"
__version__ = "1.0.0"
__author__ = "DEIY Platform"
__specification__ = "DEIY System Architecture Specification Document"

# --------------------------------------------------------------------- core
from deiy.ai import (
    AIEngine,
    GeminiClient,
    GradeResult,
    HelpdeskAnswer,
    IntegrityReport,
    RegistrationReview,
    ResourceEnrichment,
    SearchHit,
    StudentInsight,
    SummaryReport,
    Transcript,
    WhisperTranscriber,
)
from deiy.api import create_app, get_app, get_container, get_current_user, require_capability, require_roles
from deiy.auth import AuthService, user_public
from deiy.config import Settings
from deiy.config_service import ConfigService
from deiy.container import AppContainer, build_container
from deiy.db import Base, Database
from deiy.errors import (
    AppError,
    Conflict,
    DependencyUnavailable,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthorized,
    ValidationFailed,
)
from deiy.events import EventBus
from deiy.exams import ExamService, attempt_public, exam_public, question_public
from deiy.infra import (
    BaseMailer,
    ConsoleMailer,
    JobQueue,
    LocalStorage,
    MediaPipeline,
    OutboxMailer,
    S3Storage,
    SmtpMailer,
    WatermarkService,
    build_mailer,
    build_storage,
)
from deiy.library import LibraryService, course_public, live_session_public, resource_public
from deiy.rooms import RoomService, room_public, summary_public
from deiy.security import (
    ROLES,
    ROLE_PERMISSIONS,
    create_access_token,
    decode_token,
    hash_password,
    sign_token,
    verify_password,
)
from deiy.utilities import UtilitiesService, notification_public, ticket_public

__all__ = [
    # metadata
    "__title__",
    "__version__",
    "__author__",
    "__specification__",
    # application
    "create_app",
    "get_app",
    "build_container",
    "AppContainer",
    "Settings",
    "ConfigService",
    "Database",
    "Base",
    "EventBus",
    # errors
    "AppError",
    "ValidationFailed",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "Conflict",
    "RateLimited",
    "DependencyUnavailable",
    # security
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "sign_token",
    "ROLES",
    "ROLE_PERMISSIONS",
    # services
    "AuthService",
    "LibraryService",
    "ExamService",
    "RoomService",
    "UtilitiesService",
    # serializers
    "user_public",
    "course_public",
    "resource_public",
    "live_session_public",
    "exam_public",
    "question_public",
    "attempt_public",
    "room_public",
    "summary_public",
    "notification_public",
    "ticket_public",
    # AI
    "AIEngine",
    "Transcript",
    "SummaryReport",
    "RegistrationReview",
    "IntegrityReport",
    "SearchHit",
    "HelpdeskAnswer",
    "GradeResult",
    "StudentInsight",
    "ResourceEnrichment",
    "WhisperTranscriber",
    "GeminiClient",
    # infrastructure
    "LocalStorage",
    "S3Storage",
    "MediaPipeline",
    "WatermarkService",
    "JobQueue",
    "BaseMailer",
    "OutboxMailer",
    "ConsoleMailer",
    "SmtpMailer",
    "build_storage",
    "build_mailer",
    # API helpers
    "get_container",
    "get_current_user",
    "require_roles",
    "require_capability",
]


def __getattr__(name: str):
    """Expose ``deiy:app`` for uvicorn without building it on import."""

    if name == "app":
        return get_app()
    raise AttributeError(f"module 'deiy' has no attribute '{name}'")
