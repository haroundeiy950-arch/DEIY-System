"""Deterministic, dependency-free AI fallbacks.

The mock stack is not a stub: it produces useful, stable output so the whole
platform (registration review, search, proctoring analysis, room summaries,
helpdesk, grading and student insights) works offline and in CI.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

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
from deiy.utils import clamp

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "to", "of", "in",
    "on", "for", "with", "at", "by", "from", "as", "is", "are", "was", "were",
    "be", "been", "being", "it", "this", "that", "these", "those", "we", "you",
    "they", "i", "he", "she", "our", "your", "their", "will", "can", "should",
    "would", "could", "about", "into", "over", "after", "before", "during",
    "today", "session", "meeting", "room", "study", "discussed", "discuss",
}

_DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "yopmail.com", "trashmail.com", "throwaway.email",
}

_EVENT_WEIGHTS = {
    "tab_switch": 12,
    "secondary_display": 20,
    "face_missing": 10,
    "multiple_faces": 22,
    "camera_off": 18,
    "camera_obstructed": 15,
    "identity_mismatch": 35,
    "copy_paste": 10,
    "network_restored": 0,
}


def _tokens(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if tok not in _STOPWORDS]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").replace("\n", " ").strip())
    return [part.strip() for part in parts if len(part.strip()) > 3]


class MockTranscriber:
    provider = "mock"

    def transcribe(self, audio_uri: str, *, context: dict | None = None) -> Transcript:
        context = context or {}
        title = context.get("title") or "Study session"
        participants = context.get("participants") or ["Student A", "Student B", "Student C"]
        duration = float(context.get("duration_seconds") or 900)
        topics = context.get("topics") or _tokens(title) or ["the course material"]

        lines = [
            f"Speaker 1 ({participants[0]}): Welcome to {title}. Today we will review "
            f"{', '.join(topics[:3])} and prepare for the upcoming assessment.",
        ]
        for index, participant in enumerate(participants[1:4], start=2):
            topic = topics[(index - 1) % len(topics)]
            lines.append(
                f"Speaker {index} ({participant}): I reviewed {topic}. The main difficulty "
                f"is applying it to the practice questions, so we should work through examples."
            )
        lines.extend(
            [
                f"Speaker 1 ({participants[0]}): Agreed. We decided to split the chapter into "
                f"three parts and each person will prepare a short explanation.",
                f"Speaker 2 ({participants[1]}): I will summarize the key formulas and share "
                f"them in the group before the next session.",
                f"Speaker 3 ({participants[-1]}): We should schedule a follow-up and review "
                f"the exam-style problems together.",
            ]
        )
        text = "\n".join(lines)
        segments = []
        step = max(1.0, duration / len(lines))
        for index, line in enumerate(lines):
            segments.append(
                {
                    "start": round(index * step, 1),
                    "end": round((index + 1) * step, 1),
                    "text": line,
                }
            )
        return Transcript(
            text=text,
            segments=segments,
            duration_seconds=duration,
            provider=self.provider,
        )


class MockSummarizer:
    provider = "mock"
    model = "heuristic"

    def summarize(self, transcript: Transcript, *, context: dict | None = None) -> SummaryReport:
        context = context or {}
        sentences = _sentences(transcript.text)
        key_points = [s for s in sentences if len(s.split()) >= 8][:5]
        action_items = [
            s for s in sentences
            if re.search(r"\b(will|need to|should|must|prepare|review|schedule|share)\b", s, re.I)
        ][:5]
        decisions = [
            s for s in sentences
            if re.search(r"\b(decided|agreed|concluded|resolved|settled)\b", s, re.I)
        ][:5]
        topics = [word for word, _ in Counter(_tokens(transcript.text)).most_common(6)]
        participants = context.get("participants") or sorted(
            set(re.findall(r"Speaker \d+ \(([^)]+)\)", transcript.text))
        )
        title = context.get("title") or "Study room session"
        overview = (
            f"'{title}' ran for about {int(transcript.duration_seconds / 60)} minutes with "
            f"{len(participants)} participants. The group covered "
            f"{', '.join(topics[:4]) or 'the planned material'} and closed with concrete "
            f"follow-up actions."
        )
        return SummaryReport(
            title=title,
            overview=overview,
            key_points=key_points,
            action_items=action_items,
            decisions=decisions,
            topics=topics,
            participants=participants,
            provider=self.provider,
            model=self.model,
        )


class MockRegistrationReviewer:
    provider = "mock"

    def review(self, profile: dict) -> RegistrationReview:
        flags: list[str] = []
        risk = 0.0
        email = (profile.get("email") or "").lower()
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if domain in _DISPOSABLE_DOMAINS:
            risk += 40
            flags.append("disposable_email_domain")
        if not profile.get("photo_url"):
            risk += 20
            flags.append("missing_photo")
        age = profile.get("age")
        if age is not None and age < int(profile.get("minimum_age", 13)):
            risk += 30
            flags.append("under_minimum_age")
        name_parts = profile.get("name_parts") or 0
        if name_parts < 4:
            risk += 10
            flags.append("incomplete_four_part_name")
        if not profile.get("country"):
            risk += 10
            flags.append("missing_country")
        if risk >= 60:
            recommendation = "reject"
        elif risk >= 25:
            recommendation = "review"
        else:
            recommendation = "approve"
        rationale = (
            "Profile matches the standard onboarding pattern; no material risk signals."
            if not flags
            else "Detected signals: " + ", ".join(flags) + "."
        )
        return RegistrationReview(
            risk_score=clamp(risk, 0, 100),
            recommendation=recommendation,
            flags=flags,
            rationale=rationale,
            provider=self.provider,
        )


class MockIntegrityAnalyzer:
    provider = "mock"

    def analyze(self, events: list[dict], *, attempt: dict | None = None) -> IntegrityReport:
        counts = Counter(event.get("kind", "unknown") for event in events)
        risk = 0.0
        flags: list[str] = []
        for kind, count in counts.items():
            weight = _EVENT_WEIGHTS.get(kind, 8)
            risk += weight * min(count, 4)
            flags.append(f"{kind} x{count}")
        risk = clamp(risk, 0, 100)
        if risk >= 70:
            recommendation = "invalidate"
        elif risk >= 30:
            recommendation = "flag_for_review"
        else:
            recommendation = "clear"
        rationale = (
            "No proctoring violations were recorded."
            if not flags
            else "Aggregated proctoring signals: " + "; ".join(flags) + "."
        )
        return IntegrityReport(
            risk_score=risk,
            recommendation=recommendation,
            flags=flags,
            rationale=rationale,
            provider=self.provider,
        )


class MockSearchRanker:
    provider = "mock"

    def rank(self, query: str, documents: list[dict], *, limit: int = 20) -> list[SearchHit]:
        query_tokens = set(_tokens(query))
        query_norm = (query or "").lower().strip()
        if not query_norm:
            return [
                SearchHit(id=doc["id"], score=1.0, reason="recent")
                for doc in documents[:limit]
            ]
        hits: list[SearchHit] = []
        for doc in documents:
            title = (doc.get("title") or "").lower()
            author = (doc.get("author") or "").lower()
            tags = " ".join(doc.get("tags") or []).lower()
            summary = (doc.get("summary") or "").lower()
            body = (doc.get("transcript") or "")[:4000].lower()
            score = 0.0
            reasons: list[str] = []
            title_tokens = set(_tokens(title))
            overlap = query_tokens & title_tokens
            if overlap:
                score += 3.0 * len(overlap)
                reasons.append("title: " + ", ".join(sorted(overlap)))
            if query_norm in title:
                score += 4.0
                reasons.append("exact title match")
            if query_tokens & set(_tokens(tags)):
                score += 2.0
                reasons.append("tag match")
            if query_tokens & set(_tokens(author)):
                score += 1.5
                reasons.append("author match")
            if query_tokens & set(_tokens(summary)):
                score += 1.0
                reasons.append("summary match")
            if query_tokens & set(_tokens(body)):
                score += 0.5
                reasons.append("content match")
            ratio = SequenceMatcher(None, query_norm, title).ratio()
            if ratio > 0.55:
                score += ratio
                reasons.append(f"similar title ({ratio:.2f})")
            if score > 0:
                hits.append(
                    SearchHit(id=doc["id"], score=round(score, 3), reason="; ".join(reasons))
                )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]


class MockHelpdesk:
    provider = "mock"

    _FAQ = (
        (
            ("camera", "webcam", "video", "not working", "black screen"),
            "Camera checklist: 1) close other apps using the webcam, 2) allow camera "
            "permission in the browser, 3) reconnect the USB camera, 4) reload the page. "
            "If the preview is still black, run the camera test from Settings > Devices.",
        ),
        (
            ("internet", "connection", "offline", "disconnect", "network", "wifi"),
            "For connectivity issues: switch to a stable network, keep the exam tab open "
            "(answers auto-save every second locally and sync when you reconnect), and "
            "avoid VPNs. Your saved answers are restored automatically.",
        ),
        (
            ("exam", "time", "submit", "timer", "expired"),
            "Exams open exactly at the scheduled time and submit automatically at the "
            "deadline. Answers are saved locally every second, so a short disconnection "
            "will not lose your work.",
        ),
        (
            ("library", "book", "pdf", "download", "offline", "audio"),
            "Library resources can be streamed or downloaded in 144p, 360p or 720p, and "
            "video lectures also offer an audio-only track to save data. Downloads are "
            "watermarked with your name and academic ID.",
        ),
        (
            ("room", "study", "join", "capacity"),
            "Study rooms support 10-15 students and require an active camera. Join with "
            "your academic ID; summaries arrive by email and in your dashboard within "
            "5-10 minutes after the room ends.",
        ),
        (
            ("apply", "application", "admission", "admit", "enroll", "enrol", "sign up", "signup", "join the platform", "get started", "register", "registration", "otp", "verify", "verification", "approval", "approved", "academic id", "requirement", "document", "photo", "pending"),
            "Applying to DEIY takes about five minutes: 1) choose Apply and enter your "
            "four-part full name, email, a password with upper case, lower case and a "
            "digit, date of birth and country; 2) upload a clear photo (JPG, PNG or "
            "WebP, 5 MB maximum); 3) submit and enter the 6-digit code or activation "
            "link sent to your email; 4) your status becomes Pending Approval while an "
            "administrator reviews it (usually 1-2 working days); 5) once approved your "
            "unique academic ID is emailed to you and you can sign in. If a field is "
            "rejected, the form explains exactly what to correct.",
        ),
        (
            ("login", "log in", "sign in", "signin", "password", "forgot", "reset", "locked", "access denied"),
            "Sign in with the email address and password you used to register. If your "
            "status is Pending Approval, wait for the administrator review. If you "
            "forgot your password, contact your administrator or open a support ticket "
            "after signing in. Never share your password or academic ID.",
        ),
    )


    def answer(self, question: str, *, context: dict | None = None) -> HelpdeskAnswer:
        lowered = (question or "").lower()
        best = None
        best_score = 0
        for keywords, answer in self._FAQ:
            score = sum(1 for keyword in keywords if keyword in lowered)
            if score > best_score:
                best, best_score = answer, score
        if best is None:
            return HelpdeskAnswer(
                answer=(
                    "I could not resolve this automatically. I can open a support ticket "
                    "so a human agent can help you with the camera, connectivity or exam issue."
                ),
                confidence=0.25,
                escalate=True,
                suggested_ticket_subject=(question or "Technical support request")[:120],
                provider=self.provider,
            )
        confidence = clamp(0.55 + 0.1 * best_score, 0.55, 0.95)
        return HelpdeskAnswer(
            answer=best,
            confidence=confidence,
            escalate=False,
            suggested_ticket_subject="",
            provider=self.provider,
        )


class MockGrader:
    provider = "mock"

    def grade(self, question: str, answer: str, *, max_points: float) -> GradeResult:
        words = len((answer or "").split())
        if words == 0:
            return GradeResult(score=0.0, feedback="No answer provided.", provider=self.provider)
        keyword_hits = len(set(_tokens(question)) & set(_tokens(answer)))
        ratio = clamp(words / 80, 0.0, 1.0)
        quality = clamp(0.35 + 0.08 * keyword_hits + 0.4 * ratio, 0.0, 1.0)
        score = round(max_points * quality, 2)
        feedback = (
            f"Answer addresses {keyword_hits} key concept(s) in {words} words. "
            + ("Add a concrete example to strengthen it." if ratio < 0.5 else "Good coverage.")
        )
        return GradeResult(score=score, feedback=feedback, provider=self.provider)


class MockStudentAdvisor:
    provider = "mock"

    def advise(self, gradebook: dict) -> StudentInsight:
        scores = [float(item.get("score") or 0) for item in gradebook.get("exams", [])]
        attendance = float(gradebook.get("attendance_rate") or 0)
        average = sum(scores) / len(scores) if scores else 0.0
        strengths: list[str] = []
        risks: list[str] = []
        next_steps: list[str] = []
        if average >= 75:
            strengths.append(f"Strong exam average ({average:.1f}%).")
        elif scores:
            risks.append(f"Exam average is {average:.1f}%; aim for 75% or above.")
            next_steps.append("Review the lowest-scoring exam topics this week.")
        if attendance >= 85:
            strengths.append(f"Consistent attendance ({attendance:.1f}%).")
        elif attendance:
            risks.append(f"Attendance is {attendance:.1f}%.")
            next_steps.append("Attend the next live session and catch up on recordings.")
        if not next_steps:
            next_steps.append("Keep the current study rhythm and join a micro study room.")
        return StudentInsight(
            summary=(
                f"Across {len(scores)} graded exam(s), the current average is "
                f"{average:.1f}% with {attendance:.1f}% attendance."
            ),
            strengths=strengths,
            risks=risks,
            next_steps=next_steps,
            provider=self.provider,
        )


class MockResourceEnricher:
    provider = "mock"

    def enrich(self, title: str, body: str, *, kind: str) -> ResourceEnrichment:
        tags = [word.capitalize() for word, _ in Counter(_tokens(f"{title} {body}")).most_common(6)]
        summary = " ".join(_sentences(body)[:2])[:400]
        if not summary:
            summary = f"{kind.upper()} resource titled '{title}'."
        return ResourceEnrichment(tags=tags, summary=summary, provider=self.provider)


def build_mock_stack() -> dict:
    """Return the complete offline AI stack used as fallback everywhere."""

    return {
        "transcriber": MockTranscriber(),
        "summarizer": MockSummarizer(),
        "registration_reviewer": MockRegistrationReviewer(),
        "integrity_analyzer": MockIntegrityAnalyzer(),
        "search_ranker": MockSearchRanker(),
        "helpdesk": MockHelpdesk(),
        "grader": MockGrader(),
        "advisor": MockStudentAdvisor(),
        "enricher": MockResourceEnricher(),
    }
