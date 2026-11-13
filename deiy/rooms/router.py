"""HTTP API for micro study rooms and AI summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deiy.api.deps import get_container, get_current_user, require_roles
from deiy.models import User

router = APIRouter(prefix="/rooms", tags=["4. Micro Study Rooms & AI"])


class CreateRoomRequest(BaseModel):
    title: str
    capacity: int = Field(10, ge=10, le=15)
    course_id: str | None = None


class JoinRoomRequest(BaseModel):
    academic_id: str
    camera_on: bool = True


class EndRoomRequest(BaseModel):
    transcript: str | None = Field(
        None, description="Optional server-side transcript; otherwise AI transcribes the recording"
    )


@router.post("", status_code=201)
def create_room(
    payload: CreateRoomRequest,
    user: User = Depends(require_roles("student", "teacher", "admin")),
    container=Depends(get_container),
):
    return {"room": container.rooms.create_room(user, payload.model_dump())}


@router.get("")
def list_rooms(
    course_id: str | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    rooms = container.rooms.list_rooms(course_id=course_id, status=status)
    return {"count": len(rooms), "rooms": rooms}


@router.delete("/{room_id}")
def delete_room(
    room_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return {"message": "Study room deleted.", "room": container.rooms.delete_room(room_id, actor=user)}


@router.get("/{room_id}")
def get_room(
    room_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.rooms.get_room(room_id, user)


@router.post("/{room_id}/join")
def join_room(
    room_id: str,
    payload: JoinRoomRequest,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.rooms.join(
        room_id, user, academic_id=payload.academic_id, camera_on=payload.camera_on
    )


@router.post("/{room_id}/leave")
def leave_room(
    room_id: str,
    user: User = Depends(require_roles("student")),
    container=Depends(get_container),
):
    return container.rooms.leave(room_id, user)


@router.post("/{room_id}/end")
def end_room(
    room_id: str,
    payload: EndRoomRequest | None = None,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    transcript = payload.transcript if payload else None
    return container.rooms.end_room(room_id, actor=user, transcript_hint=transcript)


@router.get("/{room_id}/summary")
def room_summary(
    room_id: str,
    user: User = Depends(get_current_user),
    container=Depends(get_container),
):
    return container.rooms.get_summary(room_id, user)
