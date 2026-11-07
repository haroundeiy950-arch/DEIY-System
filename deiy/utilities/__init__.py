"""Platform utilities package (calendar, gradebook, helpdesk, tickets)."""

from deiy.utilities.service import (
    UtilitiesService,
    assignment_public,
    notification_public,
    ticket_public,
)

__all__ = [
    "UtilitiesService",
    "notification_public",
    "ticket_public",
    "assignment_public",
]
