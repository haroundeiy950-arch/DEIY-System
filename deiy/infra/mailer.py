"""Email delivery: DB outbox (default), console, or SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from deiy.config import Settings
from deiy.models import OutboxEmail
from deiy.utils import utcnow

logger = logging.getLogger(__name__)


class BaseMailer:
    backend = "base"

    def send(self, to: str, subject: str, body: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class OutboxMailer(BaseMailer):
    """Stores mail in the database; the default for dev, tests and demos."""

    backend = "outbox"

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def send(self, to: str, subject: str, body: str) -> None:
        session = self.session_factory()
        try:
            session.add(
                OutboxEmail(to=to, subject=subject, body=body, status="sent", sent_at=utcnow())
            )
            session.commit()
        finally:
            session.close()


class ConsoleMailer(BaseMailer):
    backend = "console"

    def send(self, to: str, subject: str, body: str) -> None:
        logger.info("email to=%s subject=%s\n%s", to, subject, body)


class SmtpMailer(BaseMailer):
    backend = "smtp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)


def build_mailer(settings: Settings, session_factory) -> BaseMailer:
    backend = settings.mail_backend.lower()
    if backend == "smtp" and settings.smtp_host:
        return SmtpMailer(settings)
    if backend == "console":
        return ConsoleMailer()
    return OutboxMailer(session_factory)
