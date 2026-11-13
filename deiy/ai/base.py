"""Provider-agnostic AI contracts and value objects.

The rest of the platform depends only on these dataclasses, never on a vendor
SDK.  This is what makes the Whisper/Gemini/mock stack interchangeable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Transcript:
    text: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    language: str = "en"
    duration_seconds: float = 0.0
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SummaryReport:
    title: str
    overview: str
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    provider: str = "mock"
    model: str = "heuristic"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RegistrationReview:
    risk_score: float
    recommendation: str  
    flags: list[str] = field(default_factory=list)
    rationale: str = ""
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class IntegrityReport:
    risk_score: float
    recommendation: str 
    flags: list[str] = field(default_factory=list)
    rationale: str = ""
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SearchHit:
    id: str
    score: float
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class HelpdeskAnswer:
    answer: str
    confidence: float = 0.5
    escalate: bool = False
    suggested_ticket_subject: str = ""
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class GradeResult:
    score: float
    feedback: str = ""
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class StudentInsight:
    summary: str
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ResourceEnrichment:
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    provider: str = "mock"

    def to_dict(self) -> dict:
        return asdict(self)
