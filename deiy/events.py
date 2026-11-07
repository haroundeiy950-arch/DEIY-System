"""Tiny in-process event bus used to decouple the domain modules.

Every subsystem publishes domain events (registration approved, exam submitted,
room summary ready...) and the notification/mail/audit layer subscribes.  This
keeps the feature modules independent while still "connecting everything".
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard: list[Handler] = []

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        self._wildcard.append(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        data = payload or {}
        for handler in list(self._handlers.get(event, ())):
            self._dispatch(handler, event, data)
        for handler in list(self._wildcard):
            self._dispatch(handler, event, data)

    @staticmethod
    def _dispatch(handler: Handler, event: str, payload: dict[str, Any]) -> None:
        try:
            handler(event, payload)
        except Exception:  # pragma: no cover - handlers must never break a request
            logger.exception("event handler failed for %s", event)
