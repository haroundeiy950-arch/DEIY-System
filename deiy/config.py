"""Runtime configuration for the DEIY platform.

All values can be overridden with environment variables (see ``.env.example``).
The project intentionally avoids ``pydantic-settings`` so the backend runs with
the same dependency set on any Python 3.10+ machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


_DOTENV_LOADED = False


def load_env_file(path: str | Path | None = None) -> Path | None:
    """Load a simple ``KEY=VALUE`` file without an external dependency.

    The lookup order is: explicit ``path``, ``DEIY_ENV_FILE``, then ``./.env``.
    Existing environment variables always win, and only the first call reads a
    file. Malformed lines are ignored rather than preventing startup.
    """

    global _DOTENV_LOADED
    if _DOTENV_LOADED and path is None:
        return None

    candidate = Path(path or os.environ.get("DEIY_ENV_FILE") or ".env")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not candidate.is_file():
        _DOTENV_LOADED = True
        return None
    try:
        lines = candidate.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        _DOTENV_LOADED = True
        return None

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key[0].isdigit() or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

    _DOTENV_LOADED = True
    return candidate


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(slots=True)
class Settings:
    """Everything the application needs to boot."""

    app_name: str = "DEIY"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    auto_admin: bool = False  # Local development only; never enable in production.
    secret_key: str = "dev-only-change-me-please-32-bytes-minimum"
    public_base_url: str = "http://localhost:8000"

    # Persistence / storage
    database_url: str = "sqlite:///./deiy.db"
    storage_root: Path = Path("./var/storage")
    storage_backend: str = "local"  # local | s3
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Tokens
    access_token_ttl_seconds: int = 12 * 3600
    activation_token_ttl_seconds: int = 3 * 24 * 3600
    otp_ttl_seconds: int = 10 * 60
    otp_max_attempts: int = 5
    watermark_ttl_seconds: int = 15 * 60
    media_url_ttl_seconds: int = 60 * 60

    # Onboarding policy
    minimum_age: int = 15
    expose_dev_codes: bool = True

    # Study rooms (spec section 4)
    room_min_capacity: int = 10
    room_max_capacity: int = 15
    room_max_duration_minutes: int = 45
    summary_sla_minutes: int = 10

    # Exams (spec section 3)
    default_exam_duration_minutes: int = 60
    auto_submit_on_expiry: bool = True
    require_camera_for_exam: bool = True

    # AI stack (spec section 5B: Whisper STT + Gemini summarization)
    ai_provider: str = "mock"  # mock | gemini
    ai_transcriber: str = "mock"  # mock | whisper
    openai_api_key: str = ""
    gemini_api_key: str = ""
    whisper_model: str = "whisper-1"
    gemini_model: str = "gemini-1.5-flash"
    ai_timeout_seconds: float = 30.0
    ai_cost_per_audio_minute_usd: float = 0.006
    ai_cost_per_1k_tokens_usd: float = 0.0005

    # Mail
    mail_backend: str = "outbox"  # outbox | console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    mail_from: str = "no-reply@deiy.example"

    # Background processing
    job_worker_enabled: bool = True
    job_poll_interval_seconds: float = 0.5
    job_max_attempts: int = 3

    # Public AI assistant (available before sign-in)
    assistant_rate_limit_per_minute: int = 30

    # Web / CORS
    cors_origins: tuple[str, ...] = field(default_factory=lambda: ("*",))

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        defaults = cls()
        return cls(
            environment=_env("DEIY_ENV", "development"),
            debug=_env_bool("DEIY_DEBUG", True),
            auto_admin=_env_bool("DEIY_AUTO_ADMIN", False),
            secret_key=_env("DEIY_SECRET_KEY", defaults.secret_key),
            public_base_url=_env("DEIY_PUBLIC_BASE_URL", defaults.public_base_url),
            database_url=_env("DEIY_DATABASE_URL", defaults.database_url),
            storage_root=Path(_env("DEIY_STORAGE_ROOT", str(defaults.storage_root))),
            storage_backend=_env("DEIY_STORAGE_BACKEND", "local"),
            s3_bucket=_env("DEIY_S3_BUCKET", ""),
            s3_endpoint_url=_env("DEIY_S3_ENDPOINT_URL", ""),
            s3_region=_env("DEIY_S3_REGION", "auto"),
            s3_access_key=_env("DEIY_S3_ACCESS_KEY", ""),
            s3_secret_key=_env("DEIY_S3_SECRET_KEY", ""),
            access_token_ttl_seconds=_env_int("DEIY_ACCESS_TOKEN_TTL", defaults.access_token_ttl_seconds),
            activation_token_ttl_seconds=_env_int(
                "DEIY_ACTIVATION_TOKEN_TTL", defaults.activation_token_ttl_seconds
            ),
            otp_ttl_seconds=_env_int("DEIY_OTP_TTL", defaults.otp_ttl_seconds),
            otp_max_attempts=_env_int("DEIY_OTP_MAX_ATTEMPTS", defaults.otp_max_attempts),
            watermark_ttl_seconds=_env_int("DEIY_WATERMARK_TTL", defaults.watermark_ttl_seconds),
            media_url_ttl_seconds=_env_int("DEIY_MEDIA_URL_TTL", defaults.media_url_ttl_seconds),
            minimum_age=_env_int("DEIY_MINIMUM_AGE", defaults.minimum_age),
            expose_dev_codes=_env_bool("DEIY_EXPOSE_DEV_CODES", True),
            room_min_capacity=_env_int("DEIY_ROOM_MIN_CAPACITY", defaults.room_min_capacity),
            room_max_capacity=_env_int("DEIY_ROOM_MAX_CAPACITY", defaults.room_max_capacity),
            room_max_duration_minutes=_env_int(
                "DEIY_ROOM_MAX_DURATION_MINUTES", defaults.room_max_duration_minutes
            ),
            summary_sla_minutes=_env_int("DEIY_SUMMARY_SLA_MINUTES", defaults.summary_sla_minutes),
            default_exam_duration_minutes=_env_int(
                "DEIY_DEFAULT_EXAM_DURATION_MINUTES", defaults.default_exam_duration_minutes
            ),
            auto_submit_on_expiry=_env_bool("DEIY_AUTO_SUBMIT_ON_EXPIRY", True),
            require_camera_for_exam=_env_bool("DEIY_REQUIRE_CAMERA_FOR_EXAM", True),
            ai_provider=_env("DEIY_AI_PROVIDER", "mock"),
            ai_transcriber=_env("DEIY_AI_TRANSCRIBER", "mock"),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            gemini_api_key=_env("GEMINI_API_KEY", _env("GOOGLE_API_KEY", "")),
            whisper_model=_env("DEIY_WHISPER_MODEL", defaults.whisper_model),
            gemini_model=_env("DEIY_GEMINI_MODEL", defaults.gemini_model),
            ai_timeout_seconds=_env_float("DEIY_AI_TIMEOUT", defaults.ai_timeout_seconds),
            ai_cost_per_audio_minute_usd=_env_float(
                "DEIY_AI_AUDIO_COST_PER_MINUTE", defaults.ai_cost_per_audio_minute_usd
            ),
            ai_cost_per_1k_tokens_usd=_env_float(
                "DEIY_AI_TOKEN_COST_PER_1K", defaults.ai_cost_per_1k_tokens_usd
            ),
            mail_backend=_env("DEIY_MAIL_BACKEND", "outbox"),
            smtp_host=_env("DEIY_SMTP_HOST", ""),
            smtp_port=_env_int("DEIY_SMTP_PORT", 587),
            smtp_username=_env("DEIY_SMTP_USERNAME", ""),
            smtp_password=_env("DEIY_SMTP_PASSWORD", ""),
            smtp_use_tls=_env_bool("DEIY_SMTP_TLS", True),
            mail_from=_env("DEIY_MAIL_FROM", "no-reply@deiy.example"),
            job_worker_enabled=_env_bool("DEIY_JOB_WORKER", True),
            job_poll_interval_seconds=_env_float(
                "DEIY_JOB_POLL_INTERVAL", defaults.job_poll_interval_seconds
            ),
            job_max_attempts=_env_int("DEIY_JOB_MAX_ATTEMPTS", defaults.job_max_attempts),
            assistant_rate_limit_per_minute=_env_int(
                "DEIY_ASSISTANT_RATE_LIMIT_PER_MINUTE",
                defaults.assistant_rate_limit_per_minute,
            ),
            cors_origins=_env_list("DEIY_CORS_ORIGINS", ("*",)),
        )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    def summary(self) -> dict:
        """Safe-to-print configuration summary (no secrets)."""

        return {
            "app": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "database_url": self.database_url,
            "storage_backend": self.storage_backend,
            "ai_provider": self.ai_provider,
            "ai_transcriber": self.ai_transcriber,
            "mail_backend": self.mail_backend,
            "job_worker_enabled": self.job_worker_enabled,
        }

    def validate_security(self) -> None:
        """Reject insecure configuration before production startup."""
        if not self.is_production:
            return

        errors = []

        if self.secret_key == "dev-only-change-me-please-32-bytes-minimum":
            errors.append("DEIY_SECRET_KEY must not use the development default.")

        if len(self.secret_key.encode("utf-8")) < 32:
            errors.append("DEIY_SECRET_KEY must contain at least 32 bytes.")

        if self.debug:
            errors.append("DEIY_DEBUG must be false in production.")

        if self.auto_admin:
            errors.append("DEIY_AUTO_ADMIN must be false in production.")

        if self.expose_dev_codes:
            errors.append("DEIY_EXPOSE_DEV_CODES must be false in production.")

        public_url = urlparse(self.public_base_url.strip())
        if public_url.scheme.lower() != "https" or not public_url.netloc:
            errors.append("DEIY_PUBLIC_BASE_URL must use a valid HTTPS URL in production.")

        if not self.cors_origins:
            errors.append("DEIY_CORS_ORIGINS must contain at least one HTTPS origin.")
        else:
            for origin in self.cors_origins:
                parsed_origin = urlparse(origin.strip())
                if (
                    "*" in origin
                    or parsed_origin.scheme.lower() != "https"
                    or not parsed_origin.netloc
                    or parsed_origin.path not in ("", "/")
                    or parsed_origin.query
                    or parsed_origin.fragment
                ):
                    errors.append(
                        "Every DEIY_CORS_ORIGINS entry must be an exact HTTPS origin; wildcards are forbidden."
                    )
                    break

        if errors:
            raise ValueError(
                "Insecure production configuration:\n- " + "\n- ".join(errors)
            )
