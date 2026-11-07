"""Real provider adapters: OpenAI Whisper (STT) and Google Gemini (text).

Both adapters are optional.  They raise on failure and the :class:`AIEngine`
falls back to the deterministic mock stack, so a missing key or an API outage
never breaks a user flow.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from deiy.ai.base import Transcript

logger = logging.getLogger(__name__)

_OPENAI_TRANSCRIPTIONS = "https://api.openai.com/v1/audio/transcriptions"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class WhisperTranscriber:
    provider = "whisper"

    def __init__(self, api_key: str, model: str = "whisper-1", timeout: float = 60.0) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required for the Whisper adapter")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def transcribe(self, audio_uri: str, *, context: dict | None = None) -> Transcript:
        path = Path(audio_uri)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_uri}")
        with path.open("rb") as handle:
            response = httpx.post(
                _OPENAI_TRANSCRIPTIONS,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": self.model, "response_format": "verbose_json"},
                files={"file": (path.name, handle, "application/octet-stream")},
                timeout=self.timeout,
            )
        response.raise_for_status()
        data = response.json()
        segments = [
            {
                "start": float(item.get("start", 0)),
                "end": float(item.get("end", 0)),
                "text": item.get("text", "").strip(),
            }
            for item in data.get("segments", [])
        ]
        return Transcript(
            text=(data.get("text") or "").strip(),
            segments=segments,
            language=data.get("language", "en"),
            duration_seconds=float(data.get("duration") or 0),
            provider=self.provider,
        )


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required for the Gemini adapter")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_json(self, prompt: str) -> dict[str, Any]:
        response = httpx.post(
            f"{_GEMINI_BASE}/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json(text)


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Gemini response is not a JSON object")
    return value
