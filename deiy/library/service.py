"""Content management and digital library (specification section 2).

Covers media types, categorization, AI-ranked smart search, the in-browser
viewer configuration, interactive resource links, adaptive download variants,
audio-only mode, dynamic watermarking and live-stream auto-archiving.
"""

from __future__ import annotations

from sqlalchemy import select

from deiy.audit import record_audit
from deiy.config import Settings
from deiy.db import Database
from deiy.errors import Conflict, NotFound, ValidationFailed
from deiy.events import EventBus
from deiy.infra.storage import MediaPipeline
from deiy.infra.watermark import WatermarkService
from deiy.models import Course, LiveSession, Resource, ResourceLink
from deiy.utils import new_id, utcnow

KINDS = {"video", "pdf", "epub", "image", "audio"}
DEFAULT_VIDEO_RESOLUTIONS = [144, 360, 720]


class LibraryService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        ai,
        storage,
        watermark: WatermarkService,
        pipeline: MediaPipeline,
        queue,
        events: EventBus,
    ) -> None:
        self.db = db
        self.settings = settings
        self.ai = ai
        self.storage = storage
        self.watermark = watermark
        self.pipeline = pipeline
        self.queue = queue
        self.events = events

    # ------------------------------------------------------------------ courses
    def create_course(self, data: dict, *, actor_id: str | None = None) -> Course:
        code = (data.get("code") or "").strip().upper()
        title = (data.get("title") or "").strip()
        if not code or not title:
            raise ValidationFailed("Course code and title are required.")
        with self.db.session() as session:
            if session.execute(select(Course).where(Course.code == code)).scalar_one_or_none():
                raise Conflict(f"Course '{code}' already exists.")
            course = Course(
                id=new_id(),
                code=code,
                title=title,
                department=(data.get("department") or "General").strip(),
                level=(data.get("level") or "Undergraduate").strip(),
                description=data.get("description"),
                teacher_id=data.get("teacher_id") or actor_id,
            )
            session.add(course)
            record_audit(
                session, action="course.created", actor_id=actor_id, target=course.id
            )
            session.flush()
            return course

    def list_courses(self, *, department: str | None = None, level: str | None = None) -> list[Course]:
        with self.db.session() as session:
            query = select(Course)
            if department:
                query = query.where(Course.department == department)
            if level:
                query = query.where(Course.level == level)
            return list(session.execute(query.order_by(Course.code)).scalars().all())

    # ---------------------------------------------------------------- resources
    def create_resource(self, data: dict, *, actor_id: str | None = None, upload=None) -> Resource:
        kind = (data.get("kind") or "").strip().lower()
        if kind not in KINDS:
            raise ValidationFailed(f"kind must be one of: {', '.join(sorted(KINDS))}.")
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationFailed("Resource title is required.")

        storage_key = (data.get("storage_key") or "").strip()
        mime_type = data.get("mime_type")
        size_bytes = int(data.get("size_bytes") or 0)

        if upload is not None:
            storage_key = self.pipeline.resource_key(kind, upload.filename or title)
            self.storage.save_stream(storage_key, upload.file)
            size_bytes = self.storage.size(storage_key)
            mime_type = mime_type or upload.content_type
        if not storage_key:
            raise ValidationFailed("Provide an uploaded file or a storage_key.")

        transcript = data.get("transcript")
        enrichment = self.ai.enrich_resource(title, transcript or title, kind=kind)
        tags = [str(tag) for tag in (data.get("tags") or enrichment.tags)][:12]

        resolutions = data.get("resolutions")
        if kind == "video" and not resolutions:
            resolutions = list(DEFAULT_VIDEO_RESOLUTIONS)

        with self.db.session() as session:
            if data.get("course_id") and session.get(Course, data["course_id"]) is None:
                raise NotFound("Course not found.")
            resource = Resource(
                id=new_id(),
                course_id=data.get("course_id"),
                title=title,
                author=data.get("author"),
                kind=kind,
                storage_key=storage_key,
                mime_type=mime_type,
                size_bytes=size_bytes,
                duration_seconds=int(data.get("duration_seconds") or 0),
                resolutions=resolutions or [],
                audio_available=kind in {"video", "audio"},
                transcript=transcript,
                tags=tags,
                ai_summary=enrichment.summary,
                created_by=actor_id,
            )
            session.add(resource)
            record_audit(
                session,
                action="resource.created",
                actor_id=actor_id,
                target=resource.id,
                meta={"kind": kind, "ai_provider": enrichment.provider},
            )
            session.flush()

        if kind == "video":
            self.queue.enqueue(
                "media.transcode",
                {"resource_id": resource.id, "storage_key": storage_key, "title": title},
            )
        self.events.publish(
            "library.resource.created",
            {"resource_id": resource.id, "title": title, "kind": kind, "course_id": resource.course_id},
        )
        return resource

    def get_resource(self, resource_id: str) -> Resource:
        with self.db.session() as session:
            resource = session.get(Resource, resource_id)
            if resource is None:
                raise NotFound("Resource not found.")
            return resource

    def search(
        self,
        query: str = "",
        *,
        course_id: str | None = None,
        kind: str | None = None,
        department: str | None = None,
        level: str | None = None,
        limit: int = 20,
    ) -> dict:
        with self.db.session() as session:
            stmt = select(Resource).outerjoin(Course, Resource.course_id == Course.id)
            if course_id:
                stmt = stmt.where(Resource.course_id == course_id)
            if kind:
                stmt = stmt.where(Resource.kind == kind)
            if department:
                stmt = stmt.where(Course.department == department)
            if level:
                stmt = stmt.where(Course.level == level)
            stmt = stmt.order_by(Resource.created_at.desc()).limit(200)
            resources = list(session.execute(stmt).scalars().all())

        documents = [
            {
                "id": resource.id,
                "title": resource.title,
                "author": resource.author,
                "tags": resource.tags or [],
                "summary": resource.ai_summary,
                "transcript": resource.transcript,
            }
            for resource in resources
        ]
        hits = self.ai.rank_resources(query, documents, limit=limit)
        by_id = {resource.id: resource for resource in resources}
        results = []
        for hit in hits:
            resource = by_id.get(hit.id)
            if resource is None:
                continue
            results.append(
                {
                    **resource_public(resource),
                    "match": {"score": hit.score, "reason": hit.reason},
                }
            )
        return {"query": query, "count": len(results), "results": results}

    # ------------------------------------------------------------------- access
    def access(self, user, resource_id: str, *, kind: str = "view") -> dict:
        resource = self.get_resource(resource_id)
        user_dict = {
            "id": user.id,
            "full_name": user.full_name,
            "academic_id": user.academic_id,
        }
        resource_dict = {"id": resource.id, "title": resource.title}
        watermark = self.watermark.issue(user=user_dict, resource=resource_dict, kind=kind)
        key = resource.storage_key
        variants = [
            {
                **variant,
                "url": self.storage.presign(key, ttl_seconds=self.settings.media_url_ttl_seconds),
                "available": self.storage.exists(key),
            }
            for variant in self.pipeline.plan_variants(resource.resolutions or None)
        ]
        return {
            "resource": resource_public(resource),
            "watermark": watermark,
            "viewer": {
                "mode": "in_browser",
                "full_text_search": True,
                "zoom": {"min": 0.5, "max": 3.0, "step": 0.1},
                "navigation": True,
                "remember_position": True,
                "supports_epub": resource.kind == "epub",
            },
            "variants": variants,
            "audio_only": {
                "available": bool(resource.audio_available),
                "label": "Audio only (data saver)",
            },
            "offline": {
                "download_allowed": True,
                "drm": "watermark",
                "resume": True,
            },
        }

    def download(self, user, resource_id: str, variant: str = "original") -> dict:
        resource = self.get_resource(resource_id)
        allowed = {item["resolution"] for item in self.pipeline.plan_variants(resource.resolutions or None)}
        allowed.add("original")
        if variant not in allowed:
            raise ValidationFailed(f"Unknown variant '{variant}'. Available: {sorted(allowed)}")
        manifest = self.watermark.issue_download(
            user={"id": user.id, "full_name": user.full_name, "academic_id": user.academic_id},
            resource={"id": resource.id, "title": resource.title},
            variant=variant,
        )
        return {
            "resource_id": resource.id,
            "variant": variant,
            "download_url": self.storage.presign(
                resource.storage_key, ttl_seconds=self.settings.media_url_ttl_seconds
            ),
            "expires_in": self.settings.media_url_ttl_seconds,
            "watermark": manifest,
            "checksum_required": True,
        }

    # -------------------------------------------------------------- resource links
    def add_link(
        self, resource_id: str, *, target_type: str, target_id: str, label: str | None, actor_id: str | None
    ) -> ResourceLink:
        if target_type not in {"lecture", "room", "exam"}:
            raise ValidationFailed("target_type must be lecture, room or exam.")
        with self.db.session() as session:
            if session.get(Resource, resource_id) is None:
                raise NotFound("Resource not found.")
            link = ResourceLink(
                id=new_id(),
                resource_id=resource_id,
                target_type=target_type,
                target_id=target_id,
                label=label,
                created_by=actor_id,
            )
            session.add(link)
            record_audit(
                session,
                action="resource.linked",
                actor_id=actor_id,
                target=resource_id,
                meta={"target_type": target_type, "target_id": target_id},
            )
            session.flush()
            return link

    def links_for(self, target_type: str, target_id: str) -> list[dict]:
        with self.db.session() as session:
            links = session.execute(
                select(ResourceLink).where(
                    ResourceLink.target_type == target_type,
                    ResourceLink.target_id == target_id,
                )
            ).scalars().all()
            resources = {
                resource.id: resource
                for resource in session.execute(
                    select(Resource).where(
                        Resource.id.in_([link.resource_id for link in links] or [""])
                    )
                ).scalars().all()
            }
        return [
            {
                "link_id": link.id,
                "label": link.label,
                "resource": resource_public(resources[link.resource_id])
                if link.resource_id in resources
                else None,
            }
            for link in links
        ]

    # ------------------------------------------------------------- live sessions
    def schedule_session(self, data: dict, *, actor_id: str | None = None) -> LiveSession:
        title = (data.get("title") or "").strip()
        scheduled_at = data.get("scheduled_at")
        if not title or scheduled_at is None:
            raise ValidationFailed("title and scheduled_at are required.")
        with self.db.session() as session:
            session_row = LiveSession(
                id=new_id(),
                course_id=data.get("course_id"),
                teacher_id=actor_id,
                title=title,
                scheduled_at=scheduled_at,
                status="scheduled",
            )
            session.add(session_row)
            record_audit(
                session, action="live_session.scheduled", actor_id=actor_id, target=session_row.id
            )
            session.flush()
            return session_row

    def start_session(self, session_id: str) -> LiveSession:
        with self.db.session() as session:
            row = session.get(LiveSession, session_id)
            if row is None:
                raise NotFound("Live session not found.")
            if row.status == "ended":
                raise Conflict("Session already ended.")
            row.status = "live"
            row.started_at = row.started_at or utcnow()
            session.flush()
            return row

    def end_session(self, session_id: str) -> LiveSession:
        with self.db.session() as session:
            row = session.get(LiveSession, session_id)
            if row is None:
                raise NotFound("Live session not found.")
            if row.status == "ended":
                return row
            row.status = "ended"
            row.ended_at = utcnow()
            row.recording_key = self.pipeline.recording_key(row.id, row.title)
            session.flush()
            payload = {"session_id": row.id, "recording_key": row.recording_key, "title": row.title}

        # Automatic recording archive: queued immediately when the stream ends.
        self.queue.enqueue("media.archive_recording", payload)
        self.events.publish(
            "library.live_session.ended",
            {"session_id": session_id, "recording_key": payload["recording_key"]},
        )
        return row

    def list_sessions(self, *, course_id: str | None = None) -> list[LiveSession]:
        with self.db.session() as session:
            query = select(LiveSession)
            if course_id:
                query = query.where(LiveSession.course_id == course_id)
            return list(session.execute(query.order_by(LiveSession.scheduled_at)).scalars().all())

    # ------------------------------------------------------------------- jobs
    def transcode_resource(self, payload: dict) -> None:
        resource = self.get_resource(payload["resource_id"])
        manifest = self.pipeline.transcode(resource.storage_key, title=resource.title)
        self.events.publish(
            "library.resource.transcoded",
            {"resource_id": resource.id, "manifest": manifest},
        )

    def archive_recording(self, payload: dict) -> None:
        result = self.pipeline.archive_recording(
            payload["session_id"], payload["recording_key"], title=payload.get("title", "")
        )
        self.events.publish(
            "library.recording.archived",
            {"session_id": payload["session_id"], "manifest": result},
        )


def resource_public(resource: Resource) -> dict:
    return {
        "id": resource.id,
        "course_id": resource.course_id,
        "title": resource.title,
        "author": resource.author,
        "kind": resource.kind,
        "mime_type": resource.mime_type,
        "size_bytes": resource.size_bytes,
        "duration_seconds": resource.duration_seconds,
        "resolutions": resource.resolutions or [],
        "audio_available": resource.audio_available,
        "tags": resource.tags or [],
        "ai_summary": resource.ai_summary,
        "has_transcript": bool(resource.transcript),
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
    }


def course_public(course: Course) -> dict:
    return {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "department": course.department,
        "level": course.level,
        "description": course.description,
        "teacher_id": course.teacher_id,
    }


def live_session_public(row: LiveSession) -> dict:
    return {
        "id": row.id,
        "course_id": row.course_id,
        "teacher_id": row.teacher_id,
        "title": row.title,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "status": row.status,
        "recording_key": row.recording_key,
        "viewer_count": row.viewer_count,
    }
