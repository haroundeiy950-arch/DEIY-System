"""Platform utilities (specification section 5A).

Academic calendar, student gradebook, notifications, assignments, attendance,
the automated helpdesk chatbot and the ticket system.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import Forbidden, NotFound, ValidationFailed
from deiy.events import EventBus
from deiy.models import (
    AIUsageRecord,
    Assignment,
    AssignmentSubmission,
    AttendanceRecord,
    Exam,
    ExamAttempt,
    JobRecord,
    LiveSession,
    Notification,
    Resource,
    RoomSummary,
    StudyRoom,
    SupportTicket,
    TicketMessage,
    User,
)
from deiy.utils import naive_utc, new_id, utcnow


class UtilitiesService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        ai,
        mailer,
        events: EventBus,
    ) -> None:
        self.db = db
        self.settings = settings
        self.ai = ai
        self.mailer = mailer
        self.events = events

    # ------------------------------------------------------------ notifications
    def notify(
        self,
        user_id: str,
        title: str,
        body: str,
        *,
        channel: str = "in_app",
        meta: dict | None = None,
    ) -> dict | None:
        with self.db.session() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            notification = Notification(
                id=new_id(),
                user_id=user_id,
                title=title[:300],
                body=body,
                channel=channel,
                meta=meta or {},
            )
            session.add(notification)
            session.flush()
            email = user.email
            payload = notification_public(notification)
        if channel in {"email", "both"}:
            try:
                self.mailer.send(email, title, body)
            except Exception:
                pass
        return payload

    def list_notifications(self, user_id: str, *, unread_only: bool = False) -> list[dict]:
        with self.db.session() as session:
            query = select(Notification).where(Notification.user_id == user_id)
            if unread_only:
                query = query.where(Notification.read_at.is_(None))
            rows = session.execute(
                query.order_by(Notification.created_at.desc()).limit(200)
            ).scalars().all()
            return [notification_public(row) for row in rows]

    def mark_read(self, user_id: str, notification_id: str | None = None) -> dict:
        with self.db.session() as session:
            query = select(Notification).where(Notification.user_id == user_id)
            if notification_id:
                query = query.where(Notification.id == notification_id)
            rows = session.execute(query).scalars().all()
            if notification_id and not rows:
                raise NotFound("Notification not found.")
            now = utcnow()
            for row in rows:
                if row.read_at is None:
                    row.read_at = now
            session.flush()
            return {"updated": len(rows)}

    # ---------------------------------------------------------------- calendar
    def calendar(self, user: User) -> list[dict]:
        now = utcnow()
        events: list[dict] = []
        with self.db.session() as session:
            sessions = session.execute(
                select(LiveSession)
                .where(LiveSession.scheduled_at >= now - timedelta(hours=2))
                .order_by(LiveSession.scheduled_at)
            ).scalars().all()
            for row in sessions:
                events.append(
                    {
                        "type": "live_session",
                        "id": row.id,
                        "title": row.title,
                        "course_id": row.course_id,
                        "starts_at": row.scheduled_at.isoformat(),
                        "ends_at": row.ended_at.isoformat() if row.ended_at else None,
                        "status": row.status,
                    }
                )
            exams = session.execute(
                select(Exam).where(Exam.ends_at >= now).order_by(Exam.starts_at)
            ).scalars().all()
            for row in exams:
                events.append(
                    {
                        "type": "exam",
                        "id": row.id,
                        "title": row.title,
                        "course_id": row.course_id,
                        "starts_at": row.starts_at.isoformat(),
                        "ends_at": row.ends_at.isoformat(),
                        "status": row.status,
                    }
                )
            assignments = session.execute(
                select(Assignment).where(Assignment.due_at >= now).order_by(Assignment.due_at)
            ).scalars().all()
            for row in assignments:
                events.append(
                    {
                        "type": "assignment",
                        "id": row.id,
                        "title": row.title,
                        "course_id": row.course_id,
                        "starts_at": None,
                        "ends_at": row.due_at.isoformat(),
                        "status": "due",
                    }
                )
        events.sort(key=lambda item: item["ends_at"] or item["starts_at"] or "")
        return events

    # ---------------------------------------------------------------- gradebook
    def gradebook(self, student_id: str, *, include_insights: bool = False) -> dict:
        with self.db.session() as session:
            attempts = session.execute(
                select(ExamAttempt, Exam.title)
                .join(Exam, ExamAttempt.exam_id == Exam.id)
                .where(ExamAttempt.student_id == student_id)
                .order_by(ExamAttempt.started_at.desc())
            ).all()
            submissions = session.execute(
                select(AssignmentSubmission, Assignment.title)
                .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
                .where(AssignmentSubmission.student_id == student_id)
            ).all()
            attendance = session.execute(
                select(AttendanceRecord).where(AttendanceRecord.student_id == student_id)
            ).scalars().all()

            scores = [float(attempt.score) for attempt, _ in attempts if attempt.score is not None]
            average = round(sum(scores) / len(scores), 2) if scores else 0.0
            present = sum(1 for row in attendance if row.status == "present")
            attendance_rate = round(100 * present / len(attendance), 1) if attendance else 0.0
            payload = {
                "student_id": student_id,
                "average_score": average,
                "exams": [
                    {
                        "attempt_id": attempt.id,
                        "exam_id": attempt.exam_id,
                        "title": title,
                        "score": attempt.score,
                        "status": attempt.status,
                        "submitted_at": attempt.submitted_at.isoformat()
                        if attempt.submitted_at
                        else None,
                        "integrity": attempt.integrity,
                    }
                    for attempt, title in attempts
                ],
                "assignments": [
                    {
                        "assignment_id": submission.assignment_id,
                        "title": title,
                        "grade": submission.grade,
                        "feedback": submission.feedback,
                        "submitted_at": submission.submitted_at.isoformat()
                        if submission.submitted_at
                        else None,
                    }
                    for submission, title in submissions
                ],
                "attendance": {
                    "records": len(attendance),
                    "present": present,
                    "rate": attendance_rate,
                },
                "attendance_rate": attendance_rate,
            }
        if include_insights:
            payload["ai_insights"] = self.ai.student_insights(payload).to_dict()
        return payload

    # -------------------------------------------------------------- assignments
    def create_assignment(self, data: dict, *, actor_id: str | None = None) -> Assignment:
        title = (data.get("title") or "").strip()
        due_at = data.get("due_at")
        if not title or due_at is None:
            raise ValidationFailed("title and due_at are required.")
        with self.db.session() as session:
            assignment = Assignment(
                id=new_id(),
                course_id=data.get("course_id"),
                title=title,
                description=data.get("description"),
                due_at=naive_utc(due_at),
            )
            session.add(assignment)
            record_audit(
                session, action="assignment.created", actor_id=actor_id, target=assignment.id
            )
            session.flush()
            return assignment

    def list_assignments(self, *, course_id: str | None = None) -> list[Assignment]:
        with self.db.session() as session:
            query = select(Assignment)
            if course_id:
                query = query.where(Assignment.course_id == course_id)
            return list(session.execute(query.order_by(Assignment.due_at)).scalars().all())

    def submit_assignment(self, assignment_id: str, student_id: str, content: str) -> AssignmentSubmission:
        with self.db.session() as session:
            assignment = session.get(Assignment, assignment_id)
            if assignment is None:
                raise NotFound("Assignment not found.")
            submission = session.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == assignment_id,
                    AssignmentSubmission.student_id == student_id,
                )
            ).scalar_one_or_none()
            if submission is None:
                submission = AssignmentSubmission(
                    id=new_id(),
                    assignment_id=assignment_id,
                    student_id=student_id,
                    content=content,
                )
                session.add(submission)
            else:
                submission.content = content
                submission.submitted_at = utcnow()
            session.flush()
            return submission

    def grade_submission(
        self,
        assignment_id: str,
        student_id: str,
        grade: float,
        feedback: str | None,
        *,
        actor_id: str | None = None,
    ) -> AssignmentSubmission:
        with self.db.session() as session:
            submission = session.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == assignment_id,
                    AssignmentSubmission.student_id == student_id,
                )
            ).scalar_one_or_none()
            if submission is None:
                raise NotFound("Submission not found.")
            submission.grade = float(grade)
            submission.feedback = feedback
            record_audit(
                session,
                action="assignment.graded",
                actor_id=actor_id,
                target=assignment_id,
                meta={"student_id": student_id, "grade": grade},
            )
            session.flush()
            return submission

    def list_submissions(self, assignment_id: str) -> list[AssignmentSubmission]:
        with self.db.session() as session:
            return list(
                session.execute(
                    select(AssignmentSubmission).where(
                        AssignmentSubmission.assignment_id == assignment_id
                    )
                ).scalars().all()
            )

    # --------------------------------------------------------------- attendance
    def record_attendance(self, data: dict, *, actor_id: str | None = None) -> AttendanceRecord:
        student_id = data.get("student_id")
        if not student_id:
            raise ValidationFailed("student_id is required.")
        with self.db.session() as session:
            if session.get(User, student_id) is None:
                raise NotFound("Student not found.")
            row = AttendanceRecord(
                id=new_id(),
                course_id=data.get("course_id"),
                student_id=student_id,
                session_id=data.get("session_id"),
                status=data.get("status") or "present",
                occurred_at=data.get("occurred_at") or utcnow(),
            )
            session.add(row)
            record_audit(
                session, action="attendance.recorded", actor_id=actor_id, target=student_id
            )
            session.flush()
            return row

    # ----------------------------------------------------------------- helpdesk
    def helpdesk(self, user: User, question: str) -> dict:
        if not (question or "").strip():
            raise ValidationFailed("Question is required.")
        answer = self.ai.helpdesk(
            question, context={"role": user.role, "academic_id": user.academic_id}
        )
        ticket_id = None
        if answer.escalate:
            ticket = self.create_ticket(
                user.id,
                answer.suggested_ticket_subject or question[:120],
                question,
            )
            self.reply_ticket(ticket.id, None, "assistant", answer.answer)
            ticket_id = ticket.id
        return {
            "question": question,
            "answer": answer.answer,
            "confidence": answer.confidence,
            "escalated": answer.escalate,
            "ticket_id": ticket_id,
            "provider": answer.provider,
        }

    # ------------------------------------------------------------------ tickets
    def create_ticket(self, user_id: str, subject: str, body: str) -> SupportTicket:
        if not (subject or "").strip() or not (body or "").strip():
            raise ValidationFailed("Ticket subject and body are required.")
        with self.db.session() as session:
            ticket = SupportTicket(
                id=new_id(),
                user_id=user_id,
                subject=subject[:300],
                body=body,
            )
            session.add(ticket)
            session.flush()
            session.add(
                TicketMessage(
                    id=new_id(),
                    ticket_id=ticket.id,
                    author_id=user_id,
                    role="user",
                    body=body,
                )
            )
            session.flush()
            return ticket

    def reply_ticket(
        self, ticket_id: str, author_id: str | None, role: str, body: str
    ) -> TicketMessage:
        with self.db.session() as session:
            ticket = session.get(SupportTicket, ticket_id)
            if ticket is None:
                raise NotFound("Ticket not found.")
            message = TicketMessage(
                id=new_id(),
                ticket_id=ticket_id,
                author_id=author_id,
                role=role,
                body=body,
            )
            session.add(message)
            ticket.status = "open" if role == "user" else "pending"
            session.flush()
            return message

    def resolve_ticket(self, ticket_id: str, *, actor_id: str | None = None) -> SupportTicket:
        with self.db.session() as session:
            ticket = session.get(SupportTicket, ticket_id)
            if ticket is None:
                raise NotFound("Ticket not found.")
            ticket.status = "resolved"
            record_audit(
                session, action="ticket.resolved", actor_id=actor_id, target=ticket_id
            )
            session.flush()
            return ticket

    def list_tickets(self, *, user_id: str | None = None, status: str | None = None) -> list[dict]:
        with self.db.session() as session:
            query = select(SupportTicket)
            if user_id:
                query = query.where(SupportTicket.user_id == user_id)
            if status:
                query = query.where(SupportTicket.status == status)
            rows = session.execute(
                query.order_by(SupportTicket.created_at.desc())
            ).scalars().all()
            return [ticket_public(row) for row in rows]

    def get_ticket(self, ticket_id: str, actor: User) -> dict:
        with self.db.session() as session:
            ticket = session.get(SupportTicket, ticket_id)
            if ticket is None:
                raise NotFound("Ticket not found.")
            if actor.role not in {"admin", "teacher"} and ticket.user_id != actor.id:
                raise Forbidden("You cannot access this ticket.")
            messages = session.execute(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at)
            ).scalars().all()
            payload = ticket_public(ticket)
            payload["messages"] = [
                {
                    "id": message.id,
                    "author_id": message.author_id,
                    "role": message.role,
                    "body": message.body,
                    "created_at": message.created_at.isoformat()
                    if message.created_at
                    else None,
                }
                for message in messages
            ]
            return payload

    # ------------------------------------------------------------------ metrics
    def metrics(self) -> dict:
        with self.db.session() as session:
            users = session.execute(select(func.count(User.id))).scalar() or 0
            pending = session.execute(
                select(func.count(User.id)).where(User.status == "pending_approval")
            ).scalar() or 0
            resources = session.execute(select(func.count(Resource.id))).scalar() or 0
            exams = session.execute(select(func.count(Exam.id))).scalar() or 0
            rooms = session.execute(select(func.count(StudyRoom.id))).scalar() or 0
            summaries_ready = session.execute(
                select(func.count(RoomSummary.id)).where(RoomSummary.status == "ready")
            ).scalar() or 0
            jobs = dict(
                session.execute(
                    select(JobRecord.status, func.count(JobRecord.id)).group_by(JobRecord.status)
                ).all()
            )
            ai_cost = session.execute(select(func.sum(AIUsageRecord.cost_usd))).scalar() or 0.0
        return {
            "users": users,
            "pending_approvals": pending,
            "resources": resources,
            "exams": exams,
            "study_rooms": rooms,
            "room_summaries_ready": summaries_ready,
            "jobs": jobs,
            "ai_cost_usd": round(float(ai_cost), 6),
            "ai": self.ai.health(),
        }


def notification_public(row: Notification) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "body": row.body,
        "channel": row.channel,
        "read": row.read_at is not None,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "meta": row.meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def ticket_public(ticket: SupportTicket) -> dict:
    return {
        "id": ticket.id,
        "user_id": ticket.user_id,
        "subject": ticket.subject,
        "body": ticket.body,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def assignment_public(assignment: Assignment) -> dict:
    return {
        "id": assignment.id,
        "course_id": assignment.course_id,
        "title": assignment.title,
        "description": assignment.description,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }
