"""Public (unauthenticated) assistant for applicants and new users.

Applicants cannot sign in until an administrator approves their account, so the
normal authenticated helpdesk is unavailable to exactly the people who most
need guidance.  This router exposes a rate-limited, read-only assistant plus a
structured application guide.  It reuses the same ``AIEngine`` gateway, so it
works with Gemini when configured and with the deterministic offline mock
otherwise.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from deiy.api.deps import get_container
from deiy.auth.constants import AUTH_PROVIDERS, LANGUAGES, PROGRAMS
from deiy.errors import RateLimited

router = APIRouter(prefix="/support", tags=["Public Support & AI Assistant"])

_WINDOW_SECONDS = 60.0
_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)
_ATTEMPTS_LOCK = Lock()


class AssistantRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        examples=["How do I apply and what do I need?"],
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Optional page or role context supplied by the frontend.",
    )


APPLICATION_STEPS: list[dict[str, str]] = [
    {
        "title": "Create your account",
        "description": (
            "Open Apply and enter your four-part full name (first, second, third, "
            "family name), a valid email address and a password of at least 8 "
            "characters containing upper case, lower case and a number."
        ),
        "action": "Apply now",
        "target": "#/apply",
    },
    {
        "title": "Add your details and photo",
        "description": (
            "Choose your program of study, nationality, date of birth and phone "
            "numbers (yours and your father's), then upload a clear personal photo "
            "(JPG, PNG or WebP, 5 MB or smaller). A photo URL also works."
        ),
        "action": "Open the form",
        "target": "#/apply",
    },
    {
        "title": "Verify your email",
        "description": (
            "Enter the 6-digit code sent to your email, or use the activation link. "
            "Codes expire after 10 minutes; you can request a new one."
        ),
        "action": "Verify email",
        "target": "#/verify",
    },
    {
        "title": "Wait for admin approval",
        "description": (
            "Your status becomes Pending Approval. An administrator reviews the "
            "application, usually within 1-2 working days. You can check your "
            "status by trying to sign in."
        ),
        "action": "Check status",
        "target": "#/login",
    },
    {
        "title": "Receive your academic ID and start learning",
        "description": (
            "Once approved, a unique academic ID is generated and emailed to you. "
            "Sign in with your email and password to open the library, exams and "
            "study rooms."
        ),
        "action": "Sign in",
        "target": "#/login",
    },
]

REQUIREMENTS: list[dict[str, str]] = [
    {
        "label": "Full name in four parts",
        "detail": "Example: Amina Yusuf Hassan Ali (first, second, third, family).",
    },
    {
        "label": "Program of study",
        "detail": "Choose one program from the list shown on the application form.",
    },
    {
        "label": "A valid email address",
        "detail": (
            "Register with your own email, or choose Google, Facebook or another "
            "provider. Verification and approval messages are sent by email."
        ),
    },
    {
        "label": "A strong password",
        "detail": "At least 8 characters with upper case, lower case and a digit.",
    },
    {
        "label": "Phone numbers",
        "detail": "Your own phone number and your father's (or guardian's) phone number.",
    },
    {
        "label": "Nationality and date of birth",
        "detail": "You must be at least 15 years old to apply.",
    },
    {
        "label": "A personal photograph",
        "detail": "JPG, PNG or WebP, 5 MB or smaller, or an https image URL.",
    },
]

FAQ: list[dict[str, str]] = [
    {
        "question": "How do I apply?",
        "answer": (
            "Choose Apply, complete the form in three short steps, then verify your "
            "email. An administrator reviews the application and, once approved, "
            "your academic ID is emailed to you."
        ),
    },
    {
        "question": "What do I need before I start?",
        "answer": (
            "A four-part full name, your program of study, a valid email address, a "
            "strong password, your phone number, your father's phone number, your "
            "nationality, your date of birth and a clear personal photo."
        ),
    },
    {
        "question": "What is the minimum age to apply?",
        "answer": (
            "You must be at least 15 years old on the day you apply. Applications "
            "from younger applicants are not accepted."
        ),
    },
    {
        "question": "Can I register with Google or Facebook?",
        "answer": (
            "Yes. On the application form you can choose email and password, Google, "
            "Facebook or another provider. Every application still verifies its email "
            "address before an administrator reviews it."
        ),
    },
    {
        "question": "Which languages are available?",
        "answer": (
            "The platform is available in English, Somali and Arabic. Use the language "
            "selector at the top of the page to switch at any time."
        ),
    },
    {
        "question": "I did not receive my OTP. What should I do?",
        "answer": (
            "Check your spam folder, make sure the email address is correct, then use "
            "Resend code on the Verify page. A new code is valid for 10 minutes."
        ),
    },
    {
        "question": "How long does approval take?",
        "answer": (
            "Admin review usually takes 1-2 working days. You can check your status "
            "by signing in: Pending Approval means the review is still in progress."
        ),
    },
    {
        "question": "What is an academic ID?",
        "answer": (
            "Your academic ID is the unique student identifier generated after "
            "approval. You need it to join study rooms and it appears in the "
            "watermark on downloaded library resources."
        ),
    },
]


def _check_rate_limit(host: str, limit: int) -> None:
    now = monotonic()
    with _ATTEMPTS_LOCK:
        bucket = _ATTEMPTS[host]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - bucket[0])) + 1)
            raise RateLimited(
                "Too many assistant requests. Please wait a moment and try again.",
                details={"retry_after_seconds": retry_after},
            )
        bucket.append(now)


@router.get("/guide")
def application_guide(container=Depends(get_container)) -> dict:
    """Machine-readable application guide used by the public frontend."""

    return {
        "minimum_age": max(15, int(container.settings.minimum_age)),
        "photo_max_mb": 5,
        "otp_length": 6,
        "otp_ttl_minutes": max(1, container.settings.otp_ttl_seconds // 60),
        "programs": PROGRAMS,
        "languages": LANGUAGES,
        "auth_providers": AUTH_PROVIDERS,
        "steps": APPLICATION_STEPS,
        "requirements": REQUIREMENTS,
        "faq": FAQ,
        "assistant_prompts": [
            "How do I apply step by step?",
            "What documents or details do I need?",
            "I did not receive my OTP",
            "How long does approval take?",
            "What is an academic ID?",
        ],
        "assistant_available_without_login": True,
    }


@router.post("/assistant")
def public_assistant(
    payload: AssistantRequest,
    request: Request,
    container=Depends(get_container),
) -> dict:
    """Answer applicant questions before they have an account.

    The assistant never creates tickets for anonymous visitors.  If it cannot
    answer confidently it points the visitor to registration and the support
    ticket flow available after sign-in.
    """

    host = (request.client.host if request.client else "unknown") or "unknown"
    _check_rate_limit(
        host, max(1, int(container.settings.assistant_rate_limit_per_minute))
    )

    question = payload.question.strip()
    context = {
        "channel": "public_applicant",
        "authenticated": False,
        "page": (payload.context or {}).get("page"),
    }
    answer = container.ai.helpdesk(question, context=context)

    reply = answer.answer
    next_action = "Read the application guide or create an account to continue."
    if answer.escalate:
        next_action = (
            "Create an account first. After signing in you can open a support "
            "ticket so a human agent can help with the camera, connectivity or "
            "exam issue."
        )
    return {
        "question": question,
        "answer": reply,
        "confidence": answer.confidence,
        "escalated": answer.escalate,
        "ticket_id": None,
        "provider": answer.provider,
        "can_open_ticket": False,
        "next_action": next_action,
        "suggested_ticket_subject": answer.suggested_ticket_subject,
        "quick_prompts": [
            item["question"] for item in FAQ
        ],
        "guide_url": "/support/guide",
    }


__all__ = ["router", "APPLICATION_STEPS", "REQUIREMENTS", "FAQ"]
