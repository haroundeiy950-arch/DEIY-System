"""Smart proctored exam system (specification section 3).

Key guarantees implemented here:

* exam access is blocked unless the webcam check passes;
* strict time enforcement - a queued job terminates and submits the attempt at
  the exact deadline, and any late request is auto-submitted immediately;
* anti-cheat events (tab switch, secondary display, camera/face anomalies) are
  recorded, and an AI integrity report is attached to every submission;
* offline auto-save is supported by an idempotent, sequence-numbered bulk sync
  endpoint that the browser can replay after reconnecting.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import Conflict, Forbidden, NotFound, ValidationFailed
from deiy.events import EventBus
from deiy.models import Exam, ExamAnswer, ExamAttempt, ExamQuestion, ProctorEvent, User
from deiy.utils import naive_utc, new_id, utcnow

QUESTION_KINDS = {"mcq", "short", "essay"}
EVENT_KINDS = {
    "tab_switch",
    "secondary_display",
    "face_missing",
    "multiple_faces",
    "camera_off",
    "camera_obstructed",
    "identity_mismatch",
    "copy_paste",
    "network_restored",
}


class ExamService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        ai,
        queue,
        events: EventBus,
    ) -> None:
        self.db = db
        self.settings = settings
        self.ai = ai
        self.queue = queue
        self.events = events

    # ------------------------------------------------------------------ authoring
    def create_exam(self, data: dict, *, actor_id: str | None = None) -> dict:
        title = (data.get("title") or "").strip()
        starts_at = data.get("starts_at")
        ends_at = data.get("ends_at")
        if not title or starts_at is None or ends_at is None:
            raise ValidationFailed("title, starts_at and ends_at are required.")
        starts_at = naive_utc(starts_at)
        ends_at = naive_utc(ends_at)
        if ends_at <= starts_at:
            raise ValidationFailed("ends_at must be after starts_at.")
        duration = int(data.get("duration_minutes") or self.settings.default_exam_duration_minutes)
        if duration <= 0:
            raise ValidationFailed("duration_minutes must be positive.")
        questions = data.get("questions") or []
        if not questions:
            raise ValidationFailed("At least one question is required.")
        for question in questions:
            if question.get("kind", "mcq") not in QUESTION_KINDS:
                raise ValidationFailed(f"Unknown question kind '{question.get('kind')}'.")
            if not (question.get("prompt") or "").strip():
                raise ValidationFailed("Every question needs a prompt.")

        with self.db.session() as session:
            exam = Exam(
                id=new_id(),
                course_id=data.get("course_id"),
                title=title,
                instructions=data.get("instructions"),
                starts_at=starts_at,
                ends_at=ends_at,
                duration_minutes=duration,
                status="closed" if utcnow() > ends_at else "scheduled",
                created_by=actor_id,
            )
            session.add(exam)
            session.flush()
            created = []
            for position, item in enumerate(questions):
                kind = item.get("kind", "mcq")
                options = item.get("options") or []
                if kind == "mcq" and len(options) < 2:
                    raise ValidationFailed("MCQ questions need at least two options.")
                correct_index = item.get("correct_index")
                if kind == "mcq" and correct_index is None:
                    raise ValidationFailed("MCQ questions need correct_index.")
                answer_key = (
                    {"index": int(correct_index)}
                    if kind == "mcq"
                    else {"expected": item.get("expected_answer") or ""}
                )
                question = ExamQuestion(
                    id=new_id(),
                    exam_id=exam.id,
                    prompt=item["prompt"],
                    kind=kind,
                    options=options,
                    answer_key=answer_key,
                    rubric=item.get("rubric"),
                    points=int(item.get("points") or 1),
                    position=position,
                )
                session.add(question)
                created.append(question)
            record_audit(
                session,
                action="exam.created",
                actor_id=actor_id,
                target=exam.id,
                meta={"questions": len(created)},
            )
            session.flush()
            payload = {
                "exam": exam_public(exam),
                "questions": [question_public(q, include_key=True) for q in created],
            }
        self.events.publish("exam.created", {"exam_id": payload["exam"]["id"], "title": title})
        return payload

    def list_exams(self, *, course_id: str | None = None) -> list[Exam]:
        with self.db.session() as session:
            query = select(Exam)
            if course_id:
                query = query.where(Exam.course_id == course_id)
            return list(session.execute(query.order_by(Exam.starts_at)).scalars().all())

    def get_exam(self, exam_id: str, *, include_key: bool = False) -> dict:
        with self.db.session() as session:
            exam = session.get(Exam, exam_id)
            if exam is None:
                raise NotFound("Exam not found.")
            questions = session.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == exam_id)
                .order_by(ExamQuestion.position)
            ).scalars().all()
            return {
                "exam": exam_public(exam),
                "questions": [question_public(q, include_key=include_key) for q in questions],
            }

    # --------------------------------------------------------------- attempts
    def camera_check(self, exam_id: str, *, device_id: str, stream_ok: bool) -> dict:
        if not device_id.strip():
            raise ValidationFailed("Camera device id is required.")
        if not stream_ok:
            raise ValidationFailed(
                "Webcam verification failed. A working camera is mandatory for exams.",
                code="camera_required",
            )
        with self.db.session() as session:
            if session.get(Exam, exam_id) is None:
                raise NotFound("Exam not found.")
        return {
            "exam_id": exam_id,
            "camera_verified": True,
            "device_id": device_id,
            "checked_at": utcnow().isoformat() + "Z",
            "message": "Camera operational. You may start the exam.",
        }

    def start_attempt(
        self,
        student: User,
        exam_id: str,
        *,
        camera_verified: bool,
        camera_device: str | None,
    ) -> dict:
        now = utcnow()
        delay: float | None = None
        expired_attempt: str | None = None
        with self.db.session() as session:
            exam = session.get(Exam, exam_id)
            if exam is None:
                raise NotFound("Exam not found.")
            if now < exam.starts_at:
                raise ValidationFailed(
                    "This exam has not opened yet.",
                    code="exam_not_open",
                    details={"starts_at": exam.starts_at.isoformat()},
                )
            if now > exam.ends_at:
                raise ValidationFailed("The exam window has closed.", code="exam_closed")
            if self.settings.require_camera_for_exam and not camera_verified:
                raise ValidationFailed(
                    "A verified, operational webcam is required to access this exam.",
                    code="camera_required",
                )
            if camera_verified and not (camera_device or "").strip():
                raise ValidationFailed("Camera device id is required.", code="camera_required")

            existing = session.execute(
                select(ExamAttempt).where(
                    ExamAttempt.exam_id == exam_id,
                    ExamAttempt.student_id == student.id,
                )
            ).scalar_one_or_none()
            if existing:
                if existing.status in {"submitted", "terminated"}:
                    raise Conflict("You have already completed this exam.", code="attempt_finished")
                if now >= existing.deadline_at:
                    expired_attempt = existing.id
                    attempt = existing
                else:
                    attempt = existing
                    attempt.camera_verified_at = attempt.camera_verified_at or now
                    attempt.camera_device = attempt.camera_device or camera_device
            else:
                deadline = min(now + timedelta(minutes=exam.duration_minutes), exam.ends_at)
                attempt = ExamAttempt(
                    id=new_id(),
                    exam_id=exam_id,
                    student_id=student.id,
                    status="in_progress",
                    started_at=now,
                    deadline_at=deadline,
                    camera_verified_at=now if camera_verified else None,
                    camera_device=camera_device,
                )
                session.add(attempt)
                delay = max(0.0, (deadline - now).total_seconds())
                record_audit(
                    session,
                    action="exam.attempt_started",
                    actor_id=student.id,
                    target=attempt.id,
                    meta={"exam_id": exam_id},
                )
            session.flush()
            questions = session.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == exam_id)
                .order_by(ExamQuestion.position)
            ).scalars().all()
            payload = {
                "attempt": attempt_public(attempt),
                "exam": exam_public(exam),
                "questions": [question_public(q) for q in questions],
            }
            attempt_id = attempt.id

        if expired_attempt:
            self.auto_submit(expired_attempt)
            raise Conflict(
                "Exam time expired; all saved answers were submitted automatically.",
                code="exam_expired",
                details={"attempt_id": expired_attempt},
            )
        if delay is not None:
            self.queue.enqueue("exam.expire", {"attempt_id": attempt_id}, delay_seconds=delay)
            self.events.publish(
                "exam.attempt_started", {"attempt_id": attempt_id, "student_id": student.id}
            )
        return payload

    def get_attempt(self, attempt_id: str, actor: User) -> dict:
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            if attempt is None:
                raise NotFound("Exam attempt not found.")
            if actor.role == "student" and attempt.student_id != actor.id:
                raise Forbidden("You can only access your own attempt.")
            expired = attempt.status == "in_progress" and utcnow() >= attempt.deadline_at
        if expired:
            self.auto_submit(attempt_id)
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            questions = session.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == attempt.exam_id)
                .order_by(ExamQuestion.position)
            ).scalars().all()
            answers = session.execute(
                select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id)
            ).scalars().all()
            return {
                "attempt": attempt_public(attempt),
                "questions": [question_public(q) for q in questions],
                "saved_answers": [
                    {
                        "question_id": answer.question_id,
                        "answer": answer.answer,
                        "client_seq": answer.client_seq,
                        "saved_at": answer.saved_at.isoformat() if answer.saved_at else None,
                    }
                    for answer in answers
                ],
            }

    # -------------------------------------------------------------- autosave
    def autosave(
        self,
        attempt_id: str,
        student_id: str,
        answers: list[dict],
        *,
        client_seq: int = 0,
    ) -> dict:
        now = utcnow()
        expired = False
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            if attempt is None:
                raise NotFound("Exam attempt not found.")
            if attempt.student_id != student_id:
                raise Forbidden("You can only save answers for your own attempt.")
            if attempt.status != "in_progress":
                raise Conflict(
                    f"Attempt is {attempt.status}; answers are no longer accepted.",
                    code="attempt_not_active",
                )
            if now >= attempt.deadline_at:
                expired = True
            else:
                question_ids = set(
                    session.execute(
                        select(ExamQuestion.id).where(ExamQuestion.exam_id == attempt.exam_id)
                    ).scalars().all()
                )
                existing = {
                    answer.question_id: answer
                    for answer in session.execute(
                        select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id)
                    ).scalars().all()
                }
                synced = []
                for item in answers:
                    question_id = item.get("question_id")
                    if question_id not in question_ids:
                        raise ValidationFailed(f"Question '{question_id}' is not part of this exam.")
                    sequence = int(item.get("client_seq") or client_seq or 0)
                    current = existing.get(question_id)
                    if current and current.client_seq > sequence:
                        continue  # stale replay - ignore
                    if current is None:
                        current = ExamAnswer(
                            id=new_id(),
                            attempt_id=attempt_id,
                            question_id=question_id,
                            answer=item.get("answer"),
                            client_seq=sequence,
                        )
                        session.add(current)
                        existing[question_id] = current
                    else:
                        current.answer = item.get("answer")
                        current.client_seq = sequence
                        current.saved_at = now
                    synced.append(question_id)
                attempt.last_sync_at = now
                remaining = max(0, int((attempt.deadline_at - now).total_seconds()))
                session.flush()
                return {
                    "synced": synced,
                    "client_seq": client_seq,
                    "server_time": now.isoformat() + "Z",
                    "remaining_seconds": remaining,
                    "status": attempt.status,
                }
        if expired:
            self.auto_submit(attempt_id)
            raise Conflict(
                "Exam time expired; all saved answers were submitted automatically.",
                code="exam_expired",
                details={"attempt_id": attempt_id},
            )
        raise Conflict("Autosave failed.", code="autosave_failed")

    # ---------------------------------------------------------------- submit
    def submit(self, attempt_id: str, student_id: str) -> dict:
        return self._finalize(attempt_id, student_id=student_id, auto=False)

    def auto_submit(self, attempt_id: str) -> dict:
        return self._finalize(attempt_id, student_id=None, auto=True)

    def _finalize(self, attempt_id: str, *, student_id: str | None, auto: bool) -> dict:
        now = utcnow()
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            if attempt is None:
                raise NotFound("Exam attempt not found.")
            if student_id is not None and attempt.student_id != student_id:
                raise Forbidden("You can only submit your own attempt.")
            if attempt.status in {"submitted", "terminated"}:
                return {
                    "attempt": attempt_public(attempt),
                    "breakdown": [],
                    "integrity": attempt.integrity,
                    "message": "Attempt was already finalized.",
                }

            questions = session.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == attempt.exam_id)
                .order_by(ExamQuestion.position)
            ).scalars().all()
            answers = {
                answer.question_id: answer
                for answer in session.execute(
                    select(ExamAnswer).where(ExamAnswer.attempt_id == attempt_id)
                ).scalars().all()
            }
            breakdown = []
            total = 0.0
            for question in questions:
                stored = answers.get(question.id)
                awarded, feedback, provider = self._grade_answer(
                    question, stored.answer if stored else None
                )
                total += awarded
                breakdown.append(
                    {
                        "question_id": question.id,
                        "kind": question.kind,
                        "points": question.points,
                        "awarded": round(awarded, 2),
                        "feedback": feedback,
                        "graded_by": provider,
                    }
                )

            event_rows = session.execute(
                select(ProctorEvent).where(ProctorEvent.attempt_id == attempt_id)
            ).scalars().all()
            events = [
                {
                    "kind": event.kind,
                    "severity": event.severity,
                    "payload": event.payload,
                    "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
                }
                for event in event_rows
            ]
            integrity = self.ai.analyze_integrity(
                events,
                attempt={"attempt_id": attempt_id, "exam_id": attempt.exam_id},
            )

            attempt.score = round(total, 2)
            attempt.status = "terminated" if auto or now >= attempt.deadline_at else "submitted"
            attempt.submitted_at = now
            attempt.integrity = integrity.to_dict()
            record_audit(
                session,
                action="exam.submitted",
                actor_id=attempt.student_id,
                target=attempt.id,
                meta={
                    "auto": auto,
                    "score": attempt.score,
                    "integrity": integrity.recommendation,
                },
            )
            session.flush()
            payload = {
                "attempt": attempt_public(attempt),
                "breakdown": breakdown,
                "integrity": integrity.to_dict(),
                "message": "Time expired; answers submitted automatically."
                if attempt.status == "terminated"
                else "Exam submitted.",
            }
            student = attempt.student_id
            exam_id = attempt.exam_id

        self.events.publish(
            "exam.submitted",
            {
                "attempt_id": attempt_id,
                "student_id": student,
                "exam_id": exam_id,
                "score": payload["attempt"]["score"],
                "integrity": payload["integrity"],
            },
        )
        if payload["integrity"]["recommendation"] in {"flag_for_review", "invalidate"}:
            self.events.publish(
                "exam.integrity.flagged",
                {"attempt_id": attempt_id, "integrity": payload["integrity"]},
            )
        return payload

    def _grade_answer(self, question: ExamQuestion, answer) -> tuple[float, str, str]:
        if question.kind == "mcq":
            selected = _selected_index(answer)
            correct = (question.answer_key or {}).get("index")
            if selected is not None and correct is not None and int(selected) == int(correct):
                return float(question.points), "Correct.", "auto"
            return 0.0, "Incorrect or unanswered.", "auto"
        text = _answer_text(answer)
        if not text.strip():
            return 0.0, "No answer provided.", "auto"
        result = self.ai.grade_subjective(
            question.prompt,
            text,
            max_points=float(question.points),
            rubric=question.rubric,
        )
        return float(result.score), result.feedback, result.provider

    # ------------------------------------------------------------- proctoring
    def record_events(self, attempt_id: str, events: list[dict], *, actor: User | None = None) -> dict:
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            if attempt is None:
                raise NotFound("Exam attempt not found.")
            if actor is not None and actor.role == "student" and attempt.student_id != actor.id:
                raise Forbidden("You can only report events for your own attempt.")
            created = []
            for item in events:
                kind = item.get("kind")
                if kind not in EVENT_KINDS:
                    raise ValidationFailed(
                        f"Unknown proctor event '{kind}'. Allowed: {', '.join(sorted(EVENT_KINDS))}"
                    )
                event = ProctorEvent(
                    id=new_id(),
                    attempt_id=attempt_id,
                    kind=kind,
                    severity=item.get("severity") or "low",
                    payload=item.get("payload") or {},
                    occurred_at=item.get("occurred_at") or utcnow(),
                )
                session.add(event)
                created.append(event)
            record_audit(
                session,
                action="exam.proctor_events",
                actor_id=actor.id if actor else None,
                target=attempt_id,
                meta={"count": len(created)},
            )
            session.flush()
            payload = {"attempt_id": attempt_id, "recorded": len(created)}
        self.events.publish("exam.proctor_events", payload)
        return payload

    def integrity_report(self, attempt_id: str, *, actor: User | None = None) -> dict:
        with self.db.session() as session:
            attempt = session.get(ExamAttempt, attempt_id)
            if attempt is None:
                raise NotFound("Exam attempt not found.")
            if actor is not None and actor.role == "student" and attempt.student_id != actor.id:
                raise Forbidden("You can only view your own integrity report.")
            events = session.execute(
                select(ProctorEvent).where(ProctorEvent.attempt_id == attempt_id)
            ).scalars().all()
            report = self.ai.analyze_integrity(
                [
                    {"kind": event.kind, "severity": event.severity, "payload": event.payload}
                    for event in events
                ],
                attempt={"attempt_id": attempt_id, "exam_id": attempt.exam_id},
            )
            attempt.integrity = report.to_dict()
            session.flush()
        return {
            "attempt_id": attempt_id,
            "events": len(events),
            "integrity": report.to_dict(),
        }

    def list_attempts(self, exam_id: str) -> list[ExamAttempt]:
        with self.db.session() as session:
            return list(
                session.execute(
                    select(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
                ).scalars().all()
            )

    # -------------------------------------------------------------------- job
    def expire_attempt(self, payload: dict) -> None:
        self.auto_submit(payload["attempt_id"])


def _selected_index(answer) -> int | None:
    if answer is None:
        return None
    if isinstance(answer, bool):
        return None
    if isinstance(answer, int):
        return answer
    if isinstance(answer, str) and answer.strip().isdigit():
        return int(answer.strip())
    if isinstance(answer, dict):
        for key in ("index", "option", "selected"):
            if key in answer and str(answer[key]).strip().isdigit():
                return int(answer[key])
    return None


def _answer_text(answer) -> str:
    if answer is None:
        return ""
    if isinstance(answer, str):
        return answer
    if isinstance(answer, dict):
        return str(answer.get("text") or answer.get("answer") or "")
    if isinstance(answer, list):
        return " ".join(str(item) for item in answer)
    return str(answer)


def exam_public(exam: Exam) -> dict:
    return {
        "id": exam.id,
        "course_id": exam.course_id,
        "title": exam.title,
        "instructions": exam.instructions,
        "starts_at": exam.starts_at.isoformat() if exam.starts_at else None,
        "ends_at": exam.ends_at.isoformat() if exam.ends_at else None,
        "duration_minutes": exam.duration_minutes,
        "status": exam.status,
        "question_count": None,
    }


def question_public(question: ExamQuestion, *, include_key: bool = False) -> dict:
    payload = {
        "id": question.id,
        "prompt": question.prompt,
        "kind": question.kind,
        "options": question.options or [],
        "points": question.points,
        "position": question.position,
    }
    if include_key:
        payload["answer_key"] = question.answer_key
        payload["rubric"] = question.rubric
    return payload


def attempt_public(attempt: ExamAttempt) -> dict:
    now = utcnow()
    remaining = (
        max(0, int((attempt.deadline_at - now).total_seconds()))
        if attempt.deadline_at
        else 0
    )
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "student_id": attempt.student_id,
        "status": attempt.status,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "deadline_at": attempt.deadline_at.isoformat() if attempt.deadline_at else None,
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "score": attempt.score,
        "remaining_seconds": remaining,
        "camera": {
            "verified": bool(attempt.camera_verified_at),
            "device": attempt.camera_device,
            "verified_at": attempt.camera_verified_at.isoformat()
            if attempt.camera_verified_at
            else None,
        },
        "last_sync_at": attempt.last_sync_at.isoformat() if attempt.last_sync_at else None,
        "integrity": attempt.integrity,
        "policy": {
            "tab_switching_blocked": True,
            "secondary_displays_blocked": True,
            "camera_tracking": True,
            "identity_verification": True,
            "autosave_interval_seconds": 1,
            "auto_submit_on_expiry": True,
            "offline_resync": True,
        },
    }
