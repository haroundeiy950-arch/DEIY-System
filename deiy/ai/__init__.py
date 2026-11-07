"""AI subsystem: one gateway, interchangeable providers, offline fallbacks."""

from deiy.ai.base import (
    GradeResult,
    HelpdeskAnswer,
    IntegrityReport,
    RegistrationReview,
    ResourceEnrichment,
    SearchHit,
    StudentInsight,
    SummaryReport,
    Transcript,
)
from deiy.ai.engine import AIEngine
from deiy.ai.mock import (
    MockGrader,
    MockHelpdesk,
    MockIntegrityAnalyzer,
    MockRegistrationReviewer,
    MockResourceEnricher,
    MockSearchRanker,
    MockStudentAdvisor,
    MockSummarizer,
    MockTranscriber,
    build_mock_stack,
)
from deiy.ai.providers import GeminiClient, WhisperTranscriber

__all__ = [
    "AIEngine",
    "Transcript",
    "SummaryReport",
    "RegistrationReview",
    "IntegrityReport",
    "SearchHit",
    "HelpdeskAnswer",
    "GradeResult",
    "StudentInsight",
    "ResourceEnrichment",
    "WhisperTranscriber",
    "GeminiClient",
    "build_mock_stack",
    "MockTranscriber",
    "MockSummarizer",
    "MockRegistrationReviewer",
    "MockIntegrityAnalyzer",
    "MockSearchRanker",
    "MockHelpdesk",
    "MockGrader",
    "MockStudentAdvisor",
    "MockResourceEnricher",
]
