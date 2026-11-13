"""HTTP API for the smart proctored exam system."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.exams.service import attempt_public, exam_public, question_public
from deiy.models import User

router = APIRouter(prefix="/exams", tags=["3. Smart Proctored Exams"])


class QuestionIn(BaseModel):
    prompt: str
    kind: str = Field("mcq", pattern="^(mcq|short|essay)$")
    options: list[str] = []
    correct_index: int | None = None
    expected_answer: str | None = None
    rubric: str | None = None
    points: int = Field(1, ge=1)


class CreateExamRequest(BaseModel):
    title: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int | None = None
    course_id: str | None = None
    instructions: str | None = None
    questions: list[QuestionIn]


class CameraCheckRequest(BaseModel):
    device_id: str
    stream_ok: bool = True


class StartAttemptRequest(BaseModel):
    camera_verified: bool
    camera_device: str | None = None


class AnswerItem(BaseModel):
    question_id: str
    answer: Any = None
    client_seq: int = 0


class AutosaveRequest(BaseModel):
    answers: list[AnswerItem]
    client_seq: int = 0


class ProctorEventIn(BaseModel):
    kind: str
    severity: str = "low"
    payload: dict | None = None
    occurred_at: datetime | None = None


class ProctorEventsRequest(BaseModel):
    events: list[ProctorEventIn]


@router.post("", status_code=201)
def create_exam(
    payload: CreateExamRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    return container.exams.create_exam(payload.model_dump(), actor_id=user.id)


@router.get("")
def list_exams(
    course_id: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    exams = container.exams.list_exams(course_id=course_id)
    return {"count": len(exams), "exams": [exam_public(e) for e in exams]}


@router.post("/{exam_id}/camera-check")
def camera_check(
    exam_id: str,
    payload: CameraCheckRequest,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.exams.camera_check(
        exam_id, device_id=payload.device_id, stream_ok=payload.stream_ok
    )


@router.post("/{exam_id}/attempts", status_code=201)
def start_attempt(
    exam_id: str,
    payload: StartAttemptRequest,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.exams.start_attempt(
        user,
        exam_id,
        camera_verified=payload.camera_verified,
        camera_device=payload.camera_device,
    )


@router.get("/{exam_id}/attempts")
def list_attempts(
    exam_id: str,
    user: User = Depends(require_roles("admin", "teacher", "proctor")),
    container=Depends(get_container),
):
    attempts = container.exams.list_attempts(exam_id)
    return {"count": len(attempts), "attempts": [attempt_public(a) for a in attempts]}


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: str,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    exam = container.exams.delete_exam(exam_id, actor_id=user.id)
    return {"message": "Exam deleted.", "exam": exam}


@router.get("/{exam_id}")
def get_exam(
    exam_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.exams.get_exam(
        exam_id, include_key=user.role in {"admin", "teacher"}
    )


@router.get("/attempts/{attempt_id}")
def get_attempt(
    attempt_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.exams.get_attempt(attempt_id, user)


@router.post("/attempts/{attempt_id}/autosave")
def autosave(
    attempt_id: str,
    payload: AutosaveRequest,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.exams.autosave(
        attempt_id,
        user.id,
        [item.model_dump() for item in payload.answers],
        client_seq=payload.client_seq,
    )


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: str,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.exams.submit(attempt_id, user.id)


@router.post("/attempts/{attempt_id}/proctor-events", status_code=201)
def record_proctor_events(
    attempt_id: str,
    payload: ProctorEventsRequest,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.exams.record_events(
        attempt_id, [item.model_dump() for item in payload.events], actor=user
    )


@router.get("/attempts/{attempt_id}/integrity")
def integrity_report(
    attempt_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.exams.integrity_report(attempt_id, actor=user)
