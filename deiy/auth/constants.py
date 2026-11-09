"""Shared admission constants: programs, languages and sign-in providers.

Keeping these lists in one module means the API, the public guide and the web
frontend all offer exactly the same options.
"""

from __future__ import annotations

PROGRAMS: list[dict[str, str]] = [
    {"code": "CS", "name": "Computer Science"},
    {"code": "IT", "name": "Information Technology"},
    {"code": "SE", "name": "Software Engineering"},
    {"code": "BBA", "name": "Business Administration"},
    {"code": "AF", "name": "Accounting and Finance"},
    {"code": "NUR", "name": "Nursing"},
    {"code": "PH", "name": "Public Health"},
    {"code": "EDU", "name": "Education"},
    {"code": "CE", "name": "Civil Engineering"},
    {"code": "EE", "name": "Electrical Engineering"},
    {"code": "LAW", "name": "Law"},
    {"code": "AGR", "name": "Agriculture"},
    {"code": "ECO", "name": "Economics"},
    {"code": "SW", "name": "Social Work"},
    {"code": "GEN", "name": "General Studies"},
]

LANGUAGES: list[dict[str, str]] = [
    {"code": "en", "name": "English", "native": "English", "dir": "ltr"},
    {"code": "so", "name": "Somali", "native": "Soomaali", "dir": "ltr"},
    {"code": "ar", "name": "Arabic", "native": "العربية", "dir": "rtl"},
]

AUTH_PROVIDERS: list[dict[str, str]] = [
    {"code": "email", "name": "Email and password"},
    {"code": "google", "name": "Google"},
    {"code": "facebook", "name": "Facebook"},
    {"code": "other", "name": "Other provider"},
]

PROGRAM_CODES = {item["code"].lower() for item in PROGRAMS}
PROGRAM_NAMES = {item["name"].lower(): item["name"] for item in PROGRAMS}
LANGUAGE_CODES = {item["code"] for item in LANGUAGES}
AUTH_PROVIDER_CODES = {item["code"] for item in AUTH_PROVIDERS}

__all__ = [
    "PROGRAMS",
    "LANGUAGES",
    "AUTH_PROVIDERS",
    "PROGRAM_CODES",
    "PROGRAM_NAMES",
    "LANGUAGE_CODES",
    "AUTH_PROVIDER_CODES",
]
