"""Application composition root.

``build_container`` is the only place where concrete adapters are chosen and
where the modules are connected to each other:

* AI gateway (Gemini/Whisper or offline mocks) is shared by auth, library,
  exams, rooms and utilities;
* the job queue receives every background handler (transcode, archive, exam
  expiry, room auto-close, AI summarisation);
* the event bus is wired to notifications/email so domain events reach users.

Keeping this in one module makes the dependency graph explicit and testable -
and it is what the package ``__init__`` exposes as the public entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text

from deiy.ai import AIEngine
from deiy.auth import AuthService
from deiy.config import Settings
from deiy.config_service import ConfigService
from deiy.db import Database
from deiy.errors import AppError
from deiy.events import EventBus
from deiy.exams import ExamService
from deiy.infra import (
    BaseMailer,
    JobQueue,
    MediaPipeline,
    WatermarkService,
    build_mailer,
    build_storage,
)
from deiy.library import LibraryService
from deiy.models import AIUsageRecord, User
from deiy.rooms import RoomService
from deiy.utilities import UtilitiesService

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    """Fully wired object graph for one application instance."""

    settings: Settings
    db: Database
    config: ConfigService
    events: EventBus
    ai: AIEngine
    storage: Any
    mailer: BaseMailer
    watermark: WatermarkService
    pipeline: MediaPipeline
    queue: JobQueue
    auth: AuthService
    library: LibraryService
    exams: ExamService
    rooms: RoomService
    utilities: UtilitiesService

    def start(self) -> None:
        if self.settings.job_worker_enabled:
            self.queue.start()
            logger.info("background job worker started")

    def stop(self) -> None:
        self.queue.stop()
        logger.info("background job worker stopped")

    def health(self) -> dict:
        database_ok = True
        try:
            with self.db.session() as session:
                session.execute(text("SELECT 1"))
        except Exception:  # pragma: no cover - reported instead of raised
            database_ok = False
        return {
            "status": "ok" if database_ok else "degraded",
            "database": database_ok,
            "ai": self.ai.health(),
            "storage": self.storage.health(),
            "mail": self.mailer.backend,
            "jobs_pending": self.queue.pending(),
            "job_handlers": self.queue.handlers(),
            "config_overrides": sorted(self.config.overrides),
        }


def build_container(settings: Settings | None = None, db: Database | None = None) -> AppContainer:
    settings = settings or Settings.from_env()
    settings.validate_security()
    database = db or Database(settings.database_url)
    database.create_all()

    config = ConfigService(database, settings)
    config.load()

    events = EventBus()

    def usage_sink(
        task: str, provider: str, units: float, unit_kind: str, cost_usd: float, meta: dict
    ) -> None:
        with database.session() as session:
            session.add(
                AIUsageRecord(
                    task=task,
                    provider=provider,
                    units=units,
                    unit_kind=unit_kind,
                    cost_usd=cost_usd,
                    meta=meta,
                )
            )

    ai = AIEngine(settings, usage_sink=usage_sink)
    storage = build_storage(settings)
    mailer = build_mailer(settings, database.session_factory)
    watermark = WatermarkService(settings.secret_key, settings.watermark_ttl_seconds)
    pipeline = MediaPipeline(storage, settings)
    queue = JobQueue(
        database.session_factory,
        max_attempts=settings.job_max_attempts,
        poll_interval=settings.job_poll_interval_seconds,
    )

    auth = AuthService(database, settings, mailer, ai, events, storage)
    library = LibraryService(
        database, settings, ai, storage, watermark, pipeline, queue, events
    )
    exams = ExamService(database, settings, ai, queue, events)
    rooms = RoomService(database, settings, ai, queue, events)
    utilities = UtilitiesService(database, settings, ai, mailer, events)

    container = AppContainer(
        settings=settings,
        db=database,
        config=config,
        events=events,
        ai=ai,
        storage=storage,
        mailer=mailer,
        watermark=watermark,
        pipeline=pipeline,
        queue=queue,
        auth=auth,
        library=library,
        exams=exams,
        rooms=rooms,
        utilities=utilities,
    )

    _register_jobs(container)
    _wire_events(container)
    return container


# --------------------------------------------------------------------- jobs
def _register_jobs(container: AppContainer) -> None:
    container.queue.register("media.transcode", container.library.transcode_resource)
    container.queue.register("media.archive_recording", container.library.archive_recording)
    container.queue.register("exam.expire", container.exams.expire_attempt)
    container.queue.register("room.summarize", container.rooms.process_summary)
    container.queue.register("room.autoclose", container.rooms.auto_close)


# ------------------------------------------------------------------- events
def _wire_events(container: AppContainer) -> None:
    events = container.events
    utilities = container.utilities

    def notify_admins(title: str, body: str, meta: dict | None = None) -> None:
        with container.db.session() as session:
            admins = session.execute(
                select(User).where(User.role == "admin", User.status == "active")
            ).scalars().all()
            admin_ids = [admin.id for admin in admins]
        for admin_id in admin_ids:
            utilities.notify(admin_id, title, body, channel="in_app", meta=meta)

    def notify_proctors(title: str, body: str, meta: dict | None = None) -> None:
        with container.db.session() as session:
            staff = session.execute(
                select(User).where(
                    User.role.in_(["proctor", "admin"]), User.status == "active"
                )
            ).scalars().all()
            staff_ids = [user.id for user in staff]
        for staff_id in staff_ids:
            utilities.notify(staff_id, title, body, channel="in_app", meta=meta)

    def on_user_registered(event: str, payload: dict) -> None:
        review = payload.get("ai_review") or {}
        title = "New student application"
        body = (
            f"A new application from {payload.get('email')} is pending email verification. "
            f"AI recommendation: {review.get('recommendation', 'n/a')} "
            f"(risk {review.get('risk_score', 0)})."
        )
        notify_admins(title, body, {"user_id": payload.get("user_id"), "ai_review": review})

    def on_email_verified(event: str, payload: dict) -> None:
        notify_admins(
            "Application ready for review",
            f"{payload.get('email')} verified their email and is awaiting admin approval.",
            {"user_id": payload.get("user_id")},
        )

    def on_user_approved(event: str, payload: dict) -> None:
        utilities.notify(
            payload["user_id"],
            "Your DEIY account is active",
            f"Your academic ID is {payload.get('academic_id')}. You can now sign in, join "
            "study rooms, access the library and take exams.",
            channel="in_app",
            meta={"academic_id": payload.get("academic_id")},
        )

    def on_exam_submitted(event: str, payload: dict) -> None:
        utilities.notify(
            payload["student_id"],
            "Exam submitted",
            f"Your exam attempt was submitted. Current score: {payload.get('score')}.",
            channel="in_app",
            meta={"attempt_id": payload.get("attempt_id"), "exam_id": payload.get("exam_id")},
        )

    def on_integrity_flagged(event: str, payload: dict) -> None:
        integrity = payload.get("integrity") or {}
        notify_proctors(
            "Exam integrity review required",
            "An attempt was flagged: "
            f"{integrity.get('recommendation')} (risk {integrity.get('risk_score')}). "
            f"Flags: {', '.join(integrity.get('flags') or []) or 'none'}.",
            {"attempt_id": payload.get("attempt_id"), "integrity": integrity},
        )

    def on_summary_ready(event: str, payload: dict) -> None:
        summary = payload.get("summary") or {}
        title = f"Study room summary: {summary.get('title', payload.get('room_id'))}"
        body = summary.get("overview") or "Your AI study-room summary is ready."
        for participant_id in payload.get("participant_ids", []):
            utilities.notify(
                participant_id,
                title,
                body,
                channel="both",
                meta={"room_id": payload.get("room_id"), "summary": summary},
            )

    events.subscribe("user.registered", on_user_registered)
    events.subscribe("user.email_verified", on_email_verified)
    events.subscribe("user.approved", on_user_approved)
    events.subscribe("exam.submitted", on_exam_submitted)
    events.subscribe("exam.integrity.flagged", on_integrity_flagged)
    events.subscribe("room.summary.ready", on_summary_ready)


__all__ = ["AppContainer", "build_container", "AppError"]
