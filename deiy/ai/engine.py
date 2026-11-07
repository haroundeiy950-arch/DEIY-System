"""The single AI gateway used by every DEIY module.

Cost optimisation mirrors section 5B of the specification: speech-to-text and
summarisation are separate, independently replaceable stages, and every call is
metered (audio minutes or tokens) in ``AIUsageRecord``.
"""

from __future__ import annotations

import logging
from typing import Callable

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
from deiy.ai.mock import build_mock_stack
from deiy.ai.providers import GeminiClient, WhisperTranscriber
from deiy.config import Settings
from deiy.utils import clamp, estimate_tokens

logger = logging.getLogger(__name__)

UsageSink = Callable[[str, str, float, str, float, dict], None]

_JSON_RULES = (
    "Respond with a single strict JSON object only. No markdown, no commentary, "
    "no code fences."
)


class AIEngine:
    """Routes each task to the configured provider, falling back to mocks."""

    def __init__(self, settings: Settings, usage_sink: UsageSink | None = None) -> None:
        self.settings = settings
        self._usage_sink = usage_sink
        self._mock = build_mock_stack()
        self.degraded: set[str] = set()

        self._whisper: WhisperTranscriber | None = None
        if settings.ai_transcriber == "whisper" and settings.openai_api_key:
            try:
                self._whisper = WhisperTranscriber(
                    settings.openai_api_key,
                    model=settings.whisper_model,
                    timeout=max(settings.ai_timeout_seconds, 60),
                )
            except ValueError:
                logger.warning("Whisper adapter could not be initialised")

        self._gemini: GeminiClient | None = None
        if settings.ai_provider == "gemini" and settings.gemini_api_key:
            try:
                self._gemini = GeminiClient(
                    settings.gemini_api_key,
                    model=settings.gemini_model,
                    timeout=settings.ai_timeout_seconds,
                )
            except ValueError:
                logger.warning("Gemini adapter could not be initialised")

    # ------------------------------------------------------------------ health
    def health(self) -> dict:
        return {
            "text_provider": "gemini" if self._gemini else "mock",
            "transcriber": "whisper" if self._whisper else "mock",
            "gemini_model": self.settings.gemini_model if self._gemini else None,
            "whisper_model": self.settings.whisper_model if self._whisper else None,
            "degraded_tasks": sorted(self.degraded),
        }

    def _record(
        self,
        task: str,
        provider: str,
        units: float,
        unit_kind: str,
        cost_usd: float,
        meta: dict | None = None,
    ) -> None:
        if not self._usage_sink:
            return
        try:
            self._usage_sink(task, provider, round(units, 4), unit_kind, round(cost_usd, 6), meta or {})
        except Exception:  # pragma: no cover - metering must never fail a request
            logger.exception("failed to record AI usage")

    def _fallback(self, task: str, exc: Exception) -> None:
        self.degraded.add(task)
        logger.warning("AI task '%s' fell back to mock: %s", task, exc)

    # ------------------------------------------------------------- transcribe
    def transcribe(self, audio_uri: str, *, context: dict | None = None) -> Transcript:
        if self._whisper:
            try:
                transcript = self._whisper.transcribe(audio_uri, context=context)
                minutes = transcript.duration_seconds / 60 or 0.0
                self._record(
                    "transcribe",
                    "whisper",
                    minutes,
                    "audio_minutes",
                    minutes * self.settings.ai_cost_per_audio_minute_usd,
                )
                return transcript
            except Exception as exc:
                self._fallback("transcribe", exc)
        transcript = self._mock["transcriber"].transcribe(audio_uri, context=context)
        self._record("transcribe", "mock", transcript.duration_seconds / 60, "audio_minutes", 0.0)
        return transcript

    # -------------------------------------------------------------- summarize
    def summarize_room(
        self, transcript: Transcript, *, context: dict | None = None
    ) -> SummaryReport:
        context = context or {}
        if self._gemini:
            prompt = (
                "You are the DEIY academic meeting summarizer. Summarize the study-room "
                "transcript into a structured report for students and their instructor.\n"
                f"{_JSON_RULES}\n"
                'Schema: {"title": str, "overview": str, "key_points": [str], '
                '"action_items": [str], "decisions": [str], "topics": [str], '
                '"participants": [str]}\n'
                f"Room context: {context}\n"
                f"Transcript:\n{transcript.text[:16000]}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                report = SummaryReport(
                    title=str(data.get("title") or context.get("title") or "Study room session"),
                    overview=str(data.get("overview") or ""),
                    key_points=[str(x) for x in data.get("key_points", [])],
                    action_items=[str(x) for x in data.get("action_items", [])],
                    decisions=[str(x) for x in data.get("decisions", [])],
                    topics=[str(x) for x in data.get("topics", [])],
                    participants=[str(x) for x in data.get("participants", [])],
                    provider="gemini",
                    model=self.settings.gemini_model,
                )
                if not report.overview:
                    raise ValueError("empty summary")
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "summarize",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return report
            except Exception as exc:
                self._fallback("summarize", exc)
        report = self._mock["summarizer"].summarize(transcript, context=context)
        self._record("summarize", "mock", 0.0, "tokens", 0.0)
        return report

    # --------------------------------------------------------- registration
    def review_registration(self, profile: dict) -> RegistrationReview:
        if self._gemini:
            prompt = (
                "You are an onboarding risk reviewer for an accredited learning platform. "
                "Assess this registration for fraud or policy issues. "
                f"{_JSON_RULES}\n"
                'Schema: {"risk_score": number 0-100, "recommendation": '
                '"approve"|"review"|"reject", "flags": [str], "rationale": str}\n'
                f"Profile: {profile}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                review = RegistrationReview(
                    risk_score=clamp(float(data.get("risk_score", 0)), 0, 100),
                    recommendation=str(data.get("recommendation", "review")),
                    flags=[str(x) for x in data.get("flags", [])],
                    rationale=str(data.get("rationale", "")),
                    provider="gemini",
                )
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "registration_review",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return review
            except Exception as exc:
                self._fallback("registration_review", exc)
        review = self._mock["registration_reviewer"].review(profile)
        self._record("registration_review", "mock", 0.0, "tokens", 0.0)
        return review

    # -------------------------------------------------------------- integrity
    def analyze_integrity(self, events: list[dict], *, attempt: dict | None = None) -> IntegrityReport:
        if self._gemini:
            prompt = (
                "You are an exam integrity analyst. Evaluate the proctoring events for one "
                "attempt and decide whether the attempt is clear, needs review, or should "
                f"be invalidated.\n{_JSON_RULES}\n"
                'Schema: {"risk_score": number 0-100, "recommendation": '
                '"clear"|"flag_for_review"|"invalidate", "flags": [str], "rationale": str}\n'
                f"Attempt: {attempt}\nEvents: {events[:200]}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                report = IntegrityReport(
                    risk_score=clamp(float(data.get("risk_score", 0)), 0, 100),
                    recommendation=str(data.get("recommendation", "flag_for_review")),
                    flags=[str(x) for x in data.get("flags", [])],
                    rationale=str(data.get("rationale", "")),
                    provider="gemini",
                )
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "exam_integrity",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return report
            except Exception as exc:
                self._fallback("exam_integrity", exc)
        report = self._mock["integrity_analyzer"].analyze(events, attempt=attempt)
        self._record("exam_integrity", "mock", 0.0, "tokens", 0.0)
        return report

    # ----------------------------------------------------------------- search
    def rank_resources(self, query: str, documents: list[dict], *, limit: int = 20) -> list[SearchHit]:
        if self._gemini and documents:
            compact = [
                {
                    "id": doc["id"],
                    "title": doc.get("title"),
                    "author": doc.get("author"),
                    "tags": doc.get("tags"),
                    "summary": (doc.get("summary") or "")[:400],
                }
                for doc in documents[:40]
            ]
            prompt = (
                "Rank the library resources by relevance to the student's search query. "
                f"{_JSON_RULES}\n"
                'Schema: {"hits": [{"id": str, "score": number, "reason": str}]}\n'
                f"Query: {query}\nResources: {compact}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                valid = {doc["id"] for doc in documents}
                hits = [
                    SearchHit(
                        id=str(item["id"]),
                        score=float(item.get("score", 0)),
                        reason=str(item.get("reason", "")),
                    )
                    for item in data.get("hits", [])
                    if str(item.get("id")) in valid
                ]
                if hits:
                    tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                    self._record(
                        "library_search",
                        "gemini",
                        tokens / 1000,
                        "tokens",
                        (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                    )
                    return hits[:limit]
            except Exception as exc:
                self._fallback("library_search", exc)
        hits = self._mock["search_ranker"].rank(query, documents, limit=limit)
        self._record("library_search", "mock", 0.0, "tokens", 0.0)
        return hits

    # --------------------------------------------------------------- helpdesk
    def helpdesk(self, question: str, *, context: dict | None = None) -> HelpdeskAnswer:
        if self._gemini:
            prompt = (
                "You are the DEIY helpdesk assistant. Answer the student's technical "
                "question about cameras, connectivity, exams, the library or study rooms. "
                "If you are not confident, escalate to a human ticket. "
                f"{_JSON_RULES}\n"
                'Schema: {"answer": str, "confidence": number 0-1, "escalate": bool, '
                '"suggested_ticket_subject": str}\n'
                f"Context: {context or {}}\nQuestion: {question}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                result = HelpdeskAnswer(
                    answer=str(data.get("answer", "")),
                    confidence=clamp(float(data.get("confidence", 0.5)), 0, 1),
                    escalate=bool(data.get("escalate", False)),
                    suggested_ticket_subject=str(data.get("suggested_ticket_subject", "")),
                    provider="gemini",
                )
                if not result.answer:
                    raise ValueError("empty helpdesk answer")
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "helpdesk",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return result
            except Exception as exc:
                self._fallback("helpdesk", exc)
        result = self._mock["helpdesk"].answer(question, context=context)
        self._record("helpdesk", "mock", 0.0, "tokens", 0.0)
        return result

    # ------------------------------------------------------------------ grade
    def grade_subjective(
        self, question: str, answer: str, *, max_points: float, rubric: str | None = None
    ) -> GradeResult:
        if self._gemini:
            prompt = (
                "Grade this exam answer fairly against the question and rubric. "
                f"{_JSON_RULES}\n"
                'Schema: {"score": number, "feedback": str}\n'
                f"Maximum points: {max_points}\nQuestion: {question}\n"
                f"Rubric: {rubric or 'standard academic accuracy'}\nAnswer: {answer}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                result = GradeResult(
                    score=clamp(float(data.get("score", 0)), 0, max_points),
                    feedback=str(data.get("feedback", "")),
                    provider="gemini",
                )
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "exam_grading",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return result
            except Exception as exc:
                self._fallback("exam_grading", exc)
        result = self._mock["grader"].grade(question, answer, max_points=max_points)
        self._record("exam_grading", "mock", 0.0, "tokens", 0.0)
        return result

    # --------------------------------------------------------------- insights
    def student_insights(self, gradebook: dict) -> StudentInsight:
        if self._gemini:
            prompt = (
                "You are an academic advisor. Analyze this student gradebook and produce "
                f"supportive, actionable insights.\n{_JSON_RULES}\n"
                'Schema: {"summary": str, "strengths": [str], "risks": [str], '
                '"next_steps": [str]}\n'
                f"Gradebook: {gradebook}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                insight = StudentInsight(
                    summary=str(data.get("summary", "")),
                    strengths=[str(x) for x in data.get("strengths", [])],
                    risks=[str(x) for x in data.get("risks", [])],
                    next_steps=[str(x) for x in data.get("next_steps", [])],
                    provider="gemini",
                )
                if not insight.summary:
                    raise ValueError("empty insight")
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "student_insights",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return insight
            except Exception as exc:
                self._fallback("student_insights", exc)
        insight = self._mock["advisor"].advise(gradebook)
        self._record("student_insights", "mock", 0.0, "tokens", 0.0)
        return insight

    # --------------------------------------------------------------- library
    def enrich_resource(self, title: str, body: str, *, kind: str) -> ResourceEnrichment:
        if self._gemini:
            prompt = (
                "Create search tags and a short abstract for this educational resource. "
                f"{_JSON_RULES}\n"
                'Schema: {"tags": [str], "summary": str}\n'
                f"Title: {title}\nKind: {kind}\nContent: {(body or '')[:6000]}"
            )
            try:
                data = self._gemini.generate_json(prompt)
                enrichment = ResourceEnrichment(
                    tags=[str(x) for x in data.get("tags", [])][:10],
                    summary=str(data.get("summary", "")),
                    provider="gemini",
                )
                if not enrichment.summary:
                    raise ValueError("empty enrichment")
                tokens = estimate_tokens(prompt) + estimate_tokens(str(data))
                self._record(
                    "library_enrich",
                    "gemini",
                    tokens / 1000,
                    "tokens",
                    (tokens / 1000) * self.settings.ai_cost_per_1k_tokens_usd,
                )
                return enrichment
            except Exception as exc:
                self._fallback("library_enrich", exc)
        enrichment = self._mock["enricher"].enrich(title, body, kind=kind)
        self._record("library_enrich", "mock", 0.0, "tokens", 0.0)
        return enrichment
