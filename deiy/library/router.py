"""HTTP API for the digital library and live streaming."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.library.service import course_public, live_session_public, resource_public
from deiy.models import User

router = APIRouter(prefix="/library", tags=["2. Content & Digital Library"])


class CreateCourseRequest(BaseModel):
    code: str
    title: str
    department: str = "General"
    level: str = "Undergraduate"
    description: str | None = None
    teacher_id: str | None = None


class CreateResourceRequest(BaseModel):
    title: str
    kind: str = Field(..., description="video | pdf | epub | image | audio")
    course_id: str | None = None
    author: str | None = None
    storage_key: str | None = None
    mime_type: str | None = None
    size_bytes: int = 0
    duration_seconds: int = 0
    transcript: str | None = None
    tags: list[str] | None = None
    resolutions: list[int] | None = None


class LinkRequest(BaseModel):
    target_type: str = Field(..., description="lecture | room | exam")
    target_id: str
    label: str | None = None


class ScheduleSessionRequest(BaseModel):
    title: str
    scheduled_at: datetime
    course_id: str | None = None


@router.post("/courses", status_code=201)
def create_course(
    payload: CreateCourseRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    course = container.library.create_course(payload.model_dump(), actor_id=user.id)
    return {"course": course_public(course)}


@router.get("/courses")
def list_courses(
    department: str | None = None,
    level: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    courses = container.library.list_courses(department=department, level=level)
    return {"count": len(courses), "courses": [course_public(c) for c in courses]}


@router.post("/resources", status_code=201)
def create_resource(
    payload: CreateResourceRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    resource = container.library.create_resource(payload.model_dump(), actor_id=user.id)
    return {"resource": resource_public(resource)}


@router.post("/resources/upload", status_code=201)
def upload_resource(
    title: str = Form(...),
    kind: str = Form(...),
    file: UploadFile = File(...),
    course_id: str | None = Form(None),
    author: str | None = Form(None),
    duration_seconds: int = Form(0),
    transcript: str | None = Form(None),
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    resource = container.library.create_resource(
        {
            "title": title,
            "kind": kind,
            "course_id": course_id,
            "author": author,
            "duration_seconds": duration_seconds,
            "transcript": transcript,
        },
        actor_id=user.id,
        upload=file,
    )
    return {"resource": resource_public(resource)}


@router.get("/resources")
def search_resources(
    q: str = Query("", description="title, author or concept search"),
    course_id: str | None = None,
    kind: str | None = None,
    department: str | None = None,
    level: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.library.search(
        q,
        course_id=course_id,
        kind=kind,
        department=department,
        level=level,
        limit=limit,
    )


@router.get("/resources/{resource_id}")
def get_resource(
    resource_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return {"resource": resource_public(container.library.get_resource(resource_id))}


@router.get("/resources/{resource_id}/access")
def resource_access(
    resource_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.library.access(user, resource_id)


@router.get("/resources/{resource_id}/download")
def download_resource(
    resource_id: str,
    variant: str = Query("original", description="144p, 360p, 720p, audio or original"),
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.library.download(user, resource_id, variant)


@router.post("/resources/{resource_id}/links", status_code=201)
def link_resource(
    resource_id: str,
    payload: LinkRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    link = container.library.add_link(
        resource_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        label=payload.label,
        actor_id=user.id,
    )
    return {"link_id": link.id, "resource_id": link.resource_id, "target": link.target_type}


@router.get("/links")
def get_links(
    target_type: str,
    target_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    links = container.library.links_for(target_type, target_id)
    return {"count": len(links), "links": links}


@router.post("/live-sessions", status_code=201)
def schedule_session(
    payload: ScheduleSessionRequest,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    row = container.library.schedule_session(payload.model_dump(), actor_id=user.id)
    return {"session": live_session_public(row)}


@router.get("/live-sessions")
def list_sessions(
    course_id: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    rows = container.library.list_sessions(course_id=course_id)
    return {"count": len(rows), "sessions": [live_session_public(r) for r in rows]}


@router.post("/live-sessions/{session_id}/start")
def start_session(
    session_id: str,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    return {"session": live_session_public(container.library.start_session(session_id))}


@router.post("/live-sessions/{session_id}/end")
def end_session(
    session_id: str,
    user: User = Depends(require_roles("admin", "teacher")),
    container=Depends(get_container),
):
    return {
        "message": "Session ended; recording queued for automatic archiving.",
        "session": live_session_public(container.library.end_session(session_id)),
    }
