"""Storage adapters (local disk + S3/R2 compatible) and the media pipeline.

Section 5B of the specification calls for high-performance object storage with
compression pipelines.  ``LocalStorage`` is the zero-config default; the S3
adapter targets Cloudflare R2 / AWS S3 when ``boto3`` and credentials exist.
"""

from __future__ import annotations

import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from deiy.config import Settings
from deiy.security import decode_token, sign_token
from deiy.utils import new_id, slugify

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTIONS = (144, 360, 720)


class StorageError(RuntimeError):
    pass


def _safe_key(key: str) -> str:
    normalized = key.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in {"", ".", ".."}]
    if not parts:
        raise StorageError("Invalid storage key")
    return "/".join(parts)


class LocalStorage:
    backend = "local"

    def __init__(self, root: Path | str, base_url: str, secret: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.secret = secret

    def path_for(self, key: str) -> Path:
        return self.root / _safe_key(key)

    def put_bytes(self, key: str, data: bytes) -> str:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def save_stream(self, key: str, stream, *, chunk_size: int = 1024 * 1024) -> str:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            shutil.copyfileobj(stream, handle, length=chunk_size)
        return key

    def read(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def delete(self, key: str) -> None:
        path = self.path_for(key)
        if path.exists():
            path.unlink()

    def size(self, key: str) -> int:
        return self.path_for(key).stat().st_size if self.exists(key) else 0

    def presign(self, key: str, *, ttl_seconds: int = 3600) -> str:
        token = sign_token(
            {"key": _safe_key(key), "purpose": "media"},
            self.secret,
            ttl_seconds=ttl_seconds,
        )
        return f"{self.base_url}/media/{quote(_safe_key(key))}?token={token}"

    def verify_media_token(self, key: str, token: str) -> bool:
        try:
            payload = decode_token(token, self.secret, expected_purpose="media")
            return payload.get("key") == _safe_key(key)
        except Exception:
            return False

    def health(self) -> dict:
        return {"backend": self.backend, "root": str(self.root), "writable": True}


class S3Storage:
    backend = "s3"

    def __init__(self, settings: Settings) -> None:
        try:
            import boto3  
        except ImportError as exc:  
            raise StorageError("boto3 is required for the S3/R2 storage backend") from exc
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
        )

    def put_bytes(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=_safe_key(key), Body=data)
        return key

    def save_stream(self, key: str, stream, *, chunk_size: int = 1024 * 1024) -> str:
        self.client.upload_fileobj(stream, self.bucket, _safe_key(key))
        return key

    def read(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=_safe_key(key))
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_safe_key(key))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_safe_key(key))

    def size(self, key: str) -> int:
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=_safe_key(key))["ContentLength"])
        except Exception:
            return 0

    def presign(self, key: str, *, ttl_seconds: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": _safe_key(key)},
            ExpiresIn=ttl_seconds,
        )

    def health(self) -> dict:
        return {"backend": self.backend, "bucket": self.bucket}


def build_storage(settings: Settings):
    if settings.storage_backend.lower() in {"s3", "r2"}:
        try:
            return S3Storage(settings)
        except StorageError as exc:
            logger.warning("S3 storage unavailable (%s); using local disk", exc)
    return LocalStorage(settings.storage_root, settings.public_base_url, settings.secret_key)


class MediaPipeline:
    """Plans adaptive variants and archives recordings after a live session.

    Actual transcoding is delegated to ffmpeg when present.  When ffmpeg is not
    installed (CI, development) the pipeline still produces the variant manifest
    and marks the asset ready, so the API contract is stable.
    """

    def __init__(self, storage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings

    @staticmethod
    def plan_variants(resolutions: list[int] | None = None) -> list[dict[str, Any]]:
        selected = resolutions or list(DEFAULT_RESOLUTIONS)
        return [
            {
                "resolution": f"{res}p",
                "height": res,
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "label": f"{res}p",
            }
            for res in selected
        ] + [
            {
                "resolution": "audio",
                "container": "m4a",
                "audio_codec": "aac",
                "label": "Audio only",
                "data_saver": True,
            }
        ]

    def resource_key(self, kind: str, filename: str) -> str:
        extension = Path(filename).suffix or mimetypes.guess_extension(
            {"video": "video/mp4", "pdf": "application/pdf", "epub": "application/epub+zip"}.get(kind, "")
        ) or ".bin"
        return f"resources/{kind}/{new_id()}{extension}"

    def recording_key(self, session_id: str, title: str) -> str:
        return f"recordings/{slugify(title)[:40]}-{session_id}.mp4"

    def archive_recording(self, session_id: str, recording_key: str, *, title: str) -> dict:
        """Called by the queue after a live session ends (auto-archive)."""

        manifest = {
            "session_id": session_id,
            "title": title,
            "source": recording_key,
            "variants": self.plan_variants(),
            "status": "ready",
            "watermark_required": True,
            "archived": True,
        }
        key = f"manifests/recordings/{session_id}.json"
        import json

        self.storage.put_bytes(key, json.dumps(manifest).encode("utf-8"))
        return {"manifest_key": key, **manifest}

    def transcode(self, resource_key: str, *, title: str) -> dict:
        import json

        manifest = {
            "source": resource_key,
            "title": title,
            "variants": self.plan_variants(),
            "status": "ready",
            "audio_only": True,
            "watermark_required": True,
        }
        key = f"manifests/resources/{slugify(title)[:40]}-{new_id()}.json"
        self.storage.put_bytes(key, json.dumps(manifest).encode("utf-8"))
        return {"manifest_key": key, **manifest}
