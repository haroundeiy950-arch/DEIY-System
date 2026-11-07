"""Infrastructure adapters: storage, mail, watermarking and background jobs."""

from deiy.infra.mailer import (
    BaseMailer,
    ConsoleMailer,
    OutboxMailer,
    SmtpMailer,
    build_mailer,
)
from deiy.infra.queue import JobHandler, JobQueue
from deiy.infra.storage import (
    DEFAULT_RESOLUTIONS,
    LocalStorage,
    MediaPipeline,
    S3Storage,
    StorageError,
    build_storage,
)
from deiy.infra.watermark import WatermarkService

__all__ = [
    "LocalStorage",
    "S3Storage",
    "StorageError",
    "build_storage",
    "MediaPipeline",
    "DEFAULT_RESOLUTIONS",
    "BaseMailer",
    "OutboxMailer",
    "ConsoleMailer",
    "SmtpMailer",
    "build_mailer",
    "WatermarkService",
    "JobQueue",
    "JobHandler",
]
