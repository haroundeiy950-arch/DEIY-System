"""Micro study rooms and AI summarization (specification section 4).

Implements:

* academic-ID based access, 10-15 student cap, mandatory active cameras;
* fixed maximum duration (45 minutes by default) with an auto-close job;
* an AI meeting summarizer (Whisper transcript -> Gemini summary) driven by the
  background queue, with email + in-app delivery inside the 5-10 minute SLA.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import Conflict, Forbidden, NotFound, ValidationFailed
from deiy.events import EventBus
from deiy.models import RoomParticipant, RoomSummary, StudyRoom, User
from deiy.security import sign_token
from deiy.utils import new_id, utcnow

STUN_SERVERS = [{"urls": "stun:stun.l.google.com:19302"}]


class RoomService:
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

    
    def create_room(self, host: User, data: dict) -> dict:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationFailed("Room title is required.")
        capacity = int(data.get("capacity") or self.settings.room_min_capacity)
        if not (self.settings.room_min_capacity <= capacity <= self.settings.room_max_capacity):
            raise ValidationFailed(
                "Room capacity must be between "
                f"{self.settings.room_min_capacity} and {self.settings.room_max_capacity} students."
            )
        with self.db.session() as session:
            room = StudyRoom(
                id=new_id(),
                title=title,
                course_id=data.get("course_id"),
                host_id=host.id,
                capacity=capacity,
                max_duration_minutes=self.settings.room_max_duration_minutes,
                status="open",
            )
            session.add(room)
            record_audit(
                session,
                action="room.created",
                actor_id=host.id,
                target=room.id,
                meta={"capacity": capacity},
            )
            session.flush()
            return room_public(room)

    def list_rooms(self, *, course_id: str | None = None, status: str | None = None) -> list[dict]:
        with self.db.session() as session:
            query = select(StudyRoom)
            if course_id:
                query = query.where(StudyRoom.course_id == course_id)
            if status:
                query = query.where(StudyRoom.status == status)
            rooms = session.execute(query.order_by(StudyRoom.created_at.desc())).scalars().all()
            return [
                room_public(room, participant_count=self._active_count(session, room.id))
                for room in rooms
            ]

    
    def join(
        self,
        room_id: str,
        user: User,
        *,
        academic_id: str,
        camera_on: bool,
    ) -> dict:
        if not (academic_id or "").strip():
            raise ValidationFailed("Your academic ID is required to join a study room.")
        if academic_id.strip() != (user.academic_id or "").strip():
            raise Forbidden("The academic ID does not match the signed-in account.")
        if not camera_on:
            raise ValidationFailed(
                "An active camera is mandatory in study rooms.", code="camera_required"
            )

        expired = False
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            if room.status != "open":
                raise Conflict("This study room is closed.", code="room_closed")

            now = utcnow()
            if room.started_at and now >= room.started_at + timedelta(
                minutes=room.max_duration_minutes
            ):
                expired = True
            else:
                active = session.execute(
                    select(RoomParticipant).where(
                        RoomParticipant.room_id == room_id,
                        RoomParticipant.left_at.is_(None),
                    )
                ).scalars().all()
                existing = session.execute(
                    select(RoomParticipant).where(
                        RoomParticipant.room_id == room_id,
                        RoomParticipant.user_id == user.id,
                    )
                ).scalar_one_or_none()
                if existing is None and len(active) >= room.capacity:
                    raise Conflict(
                        f"Room is full ({room.capacity}/{room.capacity}).",
                        code="room_full",
                    )

                if room.started_at is None:
                    room.started_at = now
                    first_join = True
                else:
                    first_join = False
                if existing is None:
                    participant = RoomParticipant(
                        id=new_id(),
                        room_id=room_id,
                        user_id=user.id,
                        academic_id=academic_id.strip(),
                        camera_on=True,
                        joined_at=now,
                    )
                    session.add(participant)
                else:
                    existing.left_at = None
                    existing.joined_at = now
                    existing.camera_on = True
                    existing.academic_id = academic_id.strip()

                record_audit(
                    session,
                    action="room.joined",
                    actor_id=user.id,
                    target=room_id,
                    meta={"academic_id": academic_id},
                )
                session.flush()
                participants = self._participants(session, room_id)
                payload = {
                    "room": room_public(room, participant_count=len(participants)),
                    "participants": participants,
                    "webrtc": self._webrtc_config(room, user),
                    "policy": {
                        "camera_required": True,
                        "capacity": room.capacity,
                        "max_duration_minutes": room.max_duration_minutes,
                        "auto_end": True,
                    },
                }
                started = room.started_at
                max_minutes = room.max_duration_minutes

        if expired:
            self.end_room(room_id, actor=None)
            raise Conflict("This room reached its maximum duration and was closed.", code="room_closed")

        
        if first_join:
            delay = max(0.0, (started + timedelta(minutes=max_minutes) - utcnow()).total_seconds())
            self.queue.enqueue("room.autoclose", {"room_id": room_id}, delay_seconds=delay)
        self.events.publish(
            "room.participant.joined",
            {"room_id": room_id, "user_id": user.id, "academic_id": academic_id},
        )
        return payload

    def leave(self, room_id: str, user: User) -> dict:
        with self.db.session() as session:
            participant = session.execute(
                select(RoomParticipant).where(
                    RoomParticipant.room_id == room_id,
                    RoomParticipant.user_id == user.id,
                    RoomParticipant.left_at.is_(None),
                )
            ).scalar_one_or_none()
            if participant is None:
                raise NotFound("You are not an active participant in this room.")
            participant.left_at = utcnow()
            participant.camera_on = False
            session.flush()
        self.events.publish("room.participant.left", {"room_id": room_id, "user_id": user.id})
        return {"message": "Left the room.", "room_id": room_id}

    def delete_room(self, room_id: str, *, actor: User) -> dict:
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            if actor.role != "admin" and actor.id != room.host_id:
                raise Forbidden("Only the host or an admin can delete this room.")
            payload = room_public(room, participant_count=self._active_count(session, room_id))
            session.query(RoomParticipant).filter(RoomParticipant.room_id == room_id).delete(
                synchronize_session=False
            )
            session.query(RoomSummary).filter(RoomSummary.room_id == room_id).delete(
                synchronize_session=False
            )
            record_audit(
                session,
                action="study_room.deleted",
                actor_id=actor.id,
                target=room.id,
                meta={"title": room.title},
            )
            session.delete(room)
            session.flush()
            return payload

    def get_room(self, room_id: str, user: User) -> dict:
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            expired = (
                room.status == "open"
                and room.started_at is not None
                and utcnow() >= room.started_at + timedelta(minutes=room.max_duration_minutes)
            )
        if expired:
            self.end_room(room_id, actor=None)
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            participants = self._participants(session, room_id)
            return {
                "room": room_public(room, participant_count=len(participants)),
                "participants": participants,
                "is_participant": any(p["user_id"] == user.id for p in participants),
            }

    
    def end_room(self, room_id: str, *, actor: User | None = None, transcript_hint: str | None = None) -> dict:
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            if actor is not None and actor.role != "admin" and actor.id != room.host_id:
                raise Forbidden("Only the host or an admin can end this room.")
            if room.status == "ended":
                summary = session.execute(
                    select(RoomSummary).where(RoomSummary.room_id == room_id)
                ).scalar_one_or_none()
                return {
                    "room": room_public(room),
                    "summary": summary_public(summary) if summary else None,
                    "message": "Room already ended.",
                }

            room.status = "ended"
            room.ended_at = utcnow()
            if room.started_at is None:
                room.started_at = room.ended_at
            summary = session.execute(
                select(RoomSummary).where(RoomSummary.room_id == room_id)
            ).scalar_one_or_none()
            if summary is None:
                summary = RoomSummary(
                    id=new_id(),
                    room_id=room_id,
                    status="queued",
                    queued_at=utcnow(),
                )
                session.add(summary)
            participants = session.execute(
                select(RoomParticipant).where(RoomParticipant.room_id == room_id)
            ).scalars().all()
            participant_ids = sorted({p.user_id for p in participants})
            record_audit(
                session,
                action="room.ended",
                actor_id=actor.id if actor else None,
                target=room_id,
                meta={"participants": len(participant_ids)},
            )
            session.flush()
            payload = {
                "room": room_public(room),
                "summary": summary_public(summary),
                "message": "Room ended. AI summary queued for delivery.",
            }

        
        self.queue.enqueue(
            "room.summarize",
            {
                "room_id": room_id,
                "transcript_hint": transcript_hint,
                "participant_ids": participant_ids,
            },
        )
        self.events.publish(
            "room.ended",
            {"room_id": room_id, "participant_ids": participant_ids},
        )
        return payload

    def auto_close(self, payload: dict) -> None:
        self.end_room(payload["room_id"], actor=None)


    def process_summary(self, payload: dict) -> None:
        room_id = payload["room_id"]
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            summary = session.execute(
                select(RoomSummary).where(RoomSummary.room_id == room_id)
            ).scalar_one_or_none()
            if summary is None:
                summary = RoomSummary(id=new_id(), room_id=room_id, status="queued")
                session.add(summary)
            if summary.status == "ready":
                return
            summary.status = "processing"
            participants = session.execute(
                select(RoomParticipant).where(RoomParticipant.room_id == room_id)
            ).scalars().all()
            names = []
            for participant in participants:
                user = session.get(User, participant.user_id)
                if user:
                    names.append(user.full_name)
            title = room.title
            duration = 0
            if room.started_at and room.ended_at:
                duration = max(0, int((room.ended_at - room.started_at).total_seconds()))
            participant_ids = sorted({p.user_id for p in participants})
            session.flush()

        transcript_hint = payload.get("transcript_hint")
        context = {
            "title": title,
            "participants": names or ["Student A", "Student B", "Student C"],
            "duration_seconds": duration or 900,
            "room_id": room_id,
        }
        try:
            if transcript_hint:
                from deiy.ai.base import Transcript

                transcript = Transcript(
                    text=transcript_hint,
                    duration_seconds=float(duration or 0),
                    provider="uploaded",
                )
            else:
                transcript = self.ai.transcribe(
                    f"recordings/rooms/{room_id}.m4a", context=context
                )
            report = self.ai.summarize_room(transcript, context=context)
            with self.db.session() as session:
                summary = session.execute(
                    select(RoomSummary).where(RoomSummary.room_id == room_id)
                ).scalar_one()
                summary.transcript = transcript.text
                summary.summary = report.to_dict()
                summary.provider = f"{transcript.provider}+{report.provider}"
                summary.status = "ready"
                summary.ready_at = utcnow()
                summary.delivered_at = utcnow()
                summary.error = None
                session.flush()
            self.events.publish(
                "room.summary.ready",
                {
                    "room_id": room_id,
                    "participant_ids": participant_ids,
                    "summary": report.to_dict(),
                },
            )
        except Exception as exc:
            with self.db.session() as session:
                summary = session.execute(
                    select(RoomSummary).where(RoomSummary.room_id == room_id)
                ).scalar_one_or_none()
                if summary:
                    summary.status = "failed"
                    summary.error = f"{type(exc).__name__}: {exc}"
            raise

    def get_summary(self, room_id: str, user: User) -> dict:
        with self.db.session() as session:
            room = session.get(StudyRoom, room_id)
            if room is None:
                raise NotFound("Study room not found.")
            allowed = (
                user.role in {"admin", "teacher"}
                or room.host_id == user.id
                or session.execute(
                    select(RoomParticipant).where(
                        RoomParticipant.room_id == room_id,
                        RoomParticipant.user_id == user.id,
                    )
                ).scalar_one_or_none()
                is not None
            )
            if not allowed:
                raise Forbidden("Only room participants can view this summary.")
            summary = session.execute(
                select(RoomSummary).where(RoomSummary.room_id == room_id)
            ).scalar_one_or_none()
        if summary is None:
            raise NotFound("No summary has been requested for this room.")
        return summary_public(summary, include_transcript=True)

  
    @staticmethod
    def _active_count(session, room_id: str) -> int:
        return len(
            session.execute(
                select(RoomParticipant.id).where(
                    RoomParticipant.room_id == room_id,
                    RoomParticipant.left_at.is_(None),
                )
            ).all()
        )

    @staticmethod
    def _participants(session, room_id: str) -> list[dict]:
        rows = session.execute(
            select(RoomParticipant).where(
                RoomParticipant.room_id == room_id,
                RoomParticipant.left_at.is_(None),
            )
        ).scalars().all()
        return [
            {
                "user_id": row.user_id,
                "academic_id": row.academic_id,
                "camera_on": row.camera_on,
                "joined_at": row.joined_at.isoformat() if row.joined_at else None,
            }
            for row in rows
        ]

    def _webrtc_config(self, room: StudyRoom, user: User) -> dict:
        ttl = room.max_duration_minutes * 60
        token = sign_token(
            {
                "sub": user.id,
                "room": room.id,
                "aid": user.academic_id,
                "purpose": "room",
                "role": "host" if user.id == room.host_id else "participant",
            },
            self.settings.secret_key,
            ttl_seconds=ttl,
        )
        ends_at = (
            room.started_at + timedelta(minutes=room.max_duration_minutes)
            if room.started_at
            else None
        )
        return {
            "token": token,
            "ice_servers": STUN_SERVERS,
            "media": {"audio": True, "video": True, "screen_share": False},
            "camera_required": True,
            "expires_in": ttl,
            "ends_at": ends_at.isoformat() + "Z" if ends_at else None,
        }


def room_public(room: StudyRoom, *, participant_count: int | None = None) -> dict:
    ends_at = (
        room.started_at + timedelta(minutes=room.max_duration_minutes)
        if room.started_at
        else None
    )
    remaining = 0
    if ends_at and room.status == "open":
        remaining = max(0, int((ends_at - utcnow()).total_seconds()))
    return {
        "id": room.id,
        "title": room.title,
        "course_id": room.course_id,
        "host_id": room.host_id,
        "capacity": room.capacity,
        "participant_count": participant_count,
        "status": room.status,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
        "remaining_seconds": remaining,
        "max_duration_minutes": room.max_duration_minutes,
        "created_at": room.created_at.isoformat() if room.created_at else None,
    }


def summary_public(summary: RoomSummary, *, include_transcript: bool = False) -> dict:
    payload = {
        "id": summary.id,
        "room_id": summary.room_id,
        "status": summary.status,
        "provider": summary.provider,
        "summary": summary.summary,
        "error": summary.error,
        "queued_at": summary.queued_at.isoformat() if summary.queued_at else None,
        "ready_at": summary.ready_at.isoformat() if summary.ready_at else None,
        "delivered_at": summary.delivered_at.isoformat() if summary.delivered_at else None,
    }
    if include_transcript:
        payload["transcript"] = summary.transcript
    return payload
