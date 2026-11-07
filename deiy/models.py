"""Relational model for every subsystem described in the specification.

The schema follows the five document sections:

1. ``User`` / ``VerificationCode`` / ``AuditLog``  - onboarding + RBAC
2. ``Course`` / ``Resource`` / ``LiveSession`` ... - content + digital library
3. ``Exam`` / ``ExamAttempt`` / ``ExamAnswer`` ...  - proctored exams
4. ``StudyRoom`` / ``RoomParticipant`` / ``RoomSummary`` - micro study rooms
5. ``Notification`` / ``SupportTicket`` / ``JobRecord`` ... - utilities + infra
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from deiy.db import Base
from deiy.utils import new_id, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(1000))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    country: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="student", index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_email", index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    academic_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    ai_review: Mapped[dict | None] = mapped_column(JSON)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(40), default="email_verify")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(120), default="General")
    level: Mapped[str] = mapped_column(String(40), default="Undergraduate")
    description: Mapped[str | None] = mapped_column(Text)
    teacher_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    author: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="pdf", index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    resolutions: Mapped[list | None] = mapped_column(JSON, default=list)
    audio_available: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ResourceLink(Base):
    __tablename__ = "resource_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(30), index=True)  # lecture | room | exam
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    teacher_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    recording_key: Mapped[str | None] = mapped_column(String(500))
    viewer_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    instructions: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="mcq")  # mcq | short | essay
    options: Mapped[list | None] = mapped_column(JSON, default=list)
    answer_key: Mapped[dict | None] = mapped_column(JSON)
    rubric: Mapped[str | None] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_exam_student"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deadline_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[float | None] = mapped_column(Float)
    camera_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    camera_device: Mapped[str | None] = mapped_column(String(200))
    integrity: Mapped[dict | None] = mapped_column(JSON)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("exam_attempts.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("exam_questions.id"), index=True)
    answer: Mapped[dict | list | str | int | None] = mapped_column(JSON)
    client_seq: Mapped[int] = mapped_column(Integer, default=0)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("exam_attempts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="low")
    payload: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class StudyRoom(Base):
    __tablename__ = "study_rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    max_duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RoomParticipant(Base):
    __tablename__ = "room_participants"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_user"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("study_rooms.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    academic_id: Mapped[str] = mapped_column(String(40), index=True)
    camera_on: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)


class RoomSummary(Base):
    __tablename__ = "room_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("study_rooms.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict | None] = mapped_column(JSON)
    provider: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="user")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("live_sessions.id"))
    status: Mapped[str] = mapped_column(String(20), default="present")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AIUsageRecord(Base):
    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(60))
    units: Mapped[float] = mapped_column(Float, default=0.0)
    unit_kind: Mapped[str] = mapped_column(String(30), default="tokens")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class OutboxEmail(Base):
    __tablename__ = "outbox_emails"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    to: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(200))
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


Index("ix_resources_course_kind", Resource.course_id, Resource.kind)
Index("ix_exams_course_start", Exam.course_id, Exam.starts_at)
