"""HTTP API for platform utilities, helpdesk and reporting."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.models import User
from deiy.utilities.service import assignment_public

router = APIRouter(prefix="/utilities", tags=["5. Utilities & Infrastructure"])


class HelpdeskRequest(BaseModel):
    question: str


class TicketRequest(BaseModel):
    subject: str
    body: str


class TicketReplyRequest(BaseModel):
    body: str


class AssignmentRequest(BaseModel):
    title: str
    due_at: datetime
    course_id: str | None = None
    description: str | None = None


class SubmissionRequest(BaseModel):
    content: str


class GradeRequest(BaseModel):
    student_id: str
    grade: float = Field(..., ge=0)
    feedback: str | None = None


class AttendanceRequest(BaseModel):
    student_id: str
    course_id: str | None = None
    session_id: str | None = None
    status: str = "present"
    occurred_at: datetime | None = None


# ------------------------------------------------------------------- calendar
@router.get("/calendar")
def calendar(
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    events = container.utilities.calendar(user)
    return {"count": len(events), "events": events}


# ------------------------------------------------------------------- gradebook
@router.get("/gradebook")
def gradebook(
    student_id: str | None = None,
    insights: bool = Query(True, description="Include AI academic insights"),
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    if user.role == "student":
        target = user.id
    elif user.role in {"admin", "teacher"}:
        if not student_id:
            from deiy.errors import ValidationFailed

            raise ValidationFailed("student_id is required for staff.")
        target = student_id
    else:
        target = user.id
    return container.utilities.gradebook(target, include_insights=insights)


# --------------------------------------------------------------- notifications
@router.get("/notifications")
def notifications(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    rows = container.utilities.list_notifications(user.id, unread_only=unread_only)
    return {"count": len(rows), "notifications": rows}


@router.post("/notifications/read-all")
def read_all(
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.utilities.mark_read(user.id)


@router.post("/notifications/{notification_id}/read")
def read_one(
    notification_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.utilities.mark_read(user.id, notification_id)


# ------------------------------------------------------------------- helpdesk
@router.post("/helpdesk")
def helpdesk(
    payload: HelpdeskRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.utilities.helpdesk(user, payload.question)


@router.post("/tickets", status_code=201)
def create_ticket(
    payload: TicketRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    ticket = container.utilities.create_ticket(user.id, payload.subject, payload.body)
    return {"ticket": container.utilities.get_ticket(ticket.id, user)}


@router.get("/tickets")
def list_tickets(
    status: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    scope = None if user.role in {"admin", "teacher"} else user.id
    rows = container.utilities.list_tickets(user_id=scope, status=status)
    return {"count": len(rows), "tickets": rows}


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.utilities.get_ticket(ticket_id, user)


@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: str,
    payload: TicketReplyRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    container.utilities.get_ticket(ticket_id, user)  # permission check
    role = "staff" if user.role in {"admin", "teacher"} else "user"
    message = container.utilities.reply_ticket(ticket_id, user.id, role, payload.body)
    return {"message_id": message.id, "status": "pending" if role == "staff" else "open"}


@router.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: str,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    ticket = container.utilities.resolve_ticket(ticket_id, actor_id=user.id)
    return {"ticket": {"id": ticket.id, "status": ticket.status}}


# ----------------------------------------------------------------- assignments
@router.post("/assignments", status_code=201)
def create_assignment(
    payload: AssignmentRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    assignment = container.utilities.create_assignment(payload.model_dump(), actor_id=user.id)
    return {"assignment": assignment_public(assignment)}


@router.get("/assignments")
def list_assignments(
    course_id: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    rows = container.utilities.list_assignments(course_id=course_id)
    return {"count": len(rows), "assignments": [assignment_public(r) for r in rows]}


@router.post("/assignments/{assignment_id}/submit")
def submit_assignment(
    assignment_id: str,
    payload: SubmissionRequest,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    submission = container.utilities.submit_assignment(assignment_id, user.id, payload.content)
    return {
        "submission_id": submission.id,
        "assignment_id": assignment_id,
        "submitted_at": submission.submitted_at.isoformat()
        if submission.submitted_at
        else None,
    }


@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(
    assignment_id: str,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    rows = container.utilities.list_submissions(assignment_id)
    return {
        "count": len(rows),
        "submissions": [
            {
                "id": row.id,
                "student_id": row.student_id,
                "grade": row.grade,
                "feedback": row.feedback,
                "content": row.content,
            }
            for row in rows
        ],
    }


@router.post("/assignments/{assignment_id}/grade")
def grade_submission(
    assignment_id: str,
    payload: GradeRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    submission = container.utilities.grade_submission(
        assignment_id,
        payload.student_id,
        payload.grade,
        payload.feedback,
        actor_id=user.id,
    )
    return {
        "submission_id": submission.id,
        "grade": submission.grade,
        "feedback": submission.feedback,
    }


# ----------------------------------------------------------------- attendance
@router.post("/attendance", status_code=201)
def record_attendance(
    payload: AttendanceRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    row = container.utilities.record_attendance(payload.model_dump(), actor_id=user.id)
    return {"attendance_id": row.id, "student_id": row.student_id, "status": row.status}


@router.get("/attendance/{student_id}")
def student_attendance(
    student_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    if user.role == "student" and user.id != student_id:
        from deiy.errors import Forbidden

        raise Forbidden("You can only view your own attendance.")
    book = container.utilities.gradebook(student_id)
    return {"student_id": student_id, "attendance": book["attendance"]}


# -------------------------------------------------------------------- metrics
@router.get("/metrics")
def metrics(
    user: User = Depends(require_roles("admin")),
    container=Depends(get_container),
):
    return container.utilities.metrics()
