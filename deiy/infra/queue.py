"""DB-backed background job queue.

Implements the "resource optimisation queue" from section 4B: room summaries,
recording archives, exam expiry sweeps and media transcodes run outside the
request cycle, with retries and a persistent audit trail.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import timedelta
from typing import Callable

from sqlalchemy import select

from deiy.models import JobRecord
from deiy.utils import utcnow

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict], None]


class JobQueue:
    def __init__(
        self,
        session_factory,
        *,
        max_attempts: int = 3,
        poll_interval: float = 0.5,
    ) -> None:
        self.session_factory = session_factory
        self.max_attempts = max_attempts
        self.poll_interval = poll_interval
        self._handlers: dict[str, JobHandler] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

   
    def register(self, kind: str, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    def handlers(self) -> list[str]:
        return sorted(self._handlers)

   
    def enqueue(self, kind: str, payload: dict | None = None, *, delay_seconds: float = 0.0) -> str:
        if kind not in self._handlers:
            raise ValueError(f"No handler registered for job kind '{kind}'")
        session = self.session_factory()
        try:
            job = JobRecord(
                kind=kind,
                payload=payload or {},
                status="queued",
                run_after=utcnow() + timedelta(seconds=max(0.0, delay_seconds)),
            )
            session.add(job)
            session.commit()
            return job.id
        finally:
            session.close()

    
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="deiy-jobs", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                processed = self.drain(limit=20)
            except Exception:  # pragma: no cover - defensive
                logger.exception("job worker loop error")
                processed = 0
            if not processed:
                self._stop.wait(self.poll_interval)

    
    def drain(self, *, limit: int = 100) -> int:
        """Process due jobs synchronously (also used by tests)."""

        processed = 0
        for _ in range(limit):
            job = self._claim()
            if job is None:
                break
            self._execute(job)
            processed += 1
        return processed

    def _claim(self) -> JobRecord | None:
        session = self.session_factory()
        try:
            job = session.execute(
                select(JobRecord)
                .where(JobRecord.status == "queued", JobRecord.run_after <= utcnow())
                .order_by(JobRecord.run_after)
                .limit(1)
            ).scalar_one_or_none()
            if job is None:
                return None
            job.status = "running"
            job.attempts = (job.attempts or 0) + 1
            job.started_at = utcnow()
            session.commit()
            return job
        finally:
            session.close()

    def _execute(self, job: JobRecord) -> None:
        handler = self._handlers.get(job.kind)
        payload = job.payload or {}
        error: str | None = None
        if handler is None:
            error = f"unknown job kind '{job.kind}'"
        else:
            try:
                handler(payload)
            except Exception as exc:  # noqa: BLE001 - persisted for retry
                logger.exception("job %s (%s) failed", job.id, job.kind)
                error = f"{type(exc).__name__}: {exc}"

        session = self.session_factory()
        try:
            stored = session.get(JobRecord, job.id)
            if stored is None:
                return
            if error is None:
                stored.status = "done"
                stored.finished_at = utcnow()
                stored.error = None
            elif stored.attempts >= self.max_attempts:
                stored.status = "failed"
                stored.finished_at = utcnow()
                stored.error = error
            else:
                stored.status = "queued"
                stored.error = error
                stored.run_after = utcnow() + timedelta(seconds=15 * stored.attempts)
            session.commit()
        finally:
            session.close()

   
    def pending(self) -> int:
        session = self.session_factory()
        try:
            return len(
                session.execute(select(JobRecord).where(JobRecord.status == "queued")).all()
            )
        finally:
            session.close()

    def wait_idle(self, timeout: float = 10.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.pending() == 0:
                return True
            time.sleep(0.05)
        return False
