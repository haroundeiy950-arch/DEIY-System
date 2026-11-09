"""End-to-end tests for each section of the DEIY specification."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from deiy.models import ExamAttempt, JobRecord
from deiy.utils import utcnow
from tests.conftest import auth


def iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


# ---------------------------------------------------------------------------
# 1. Onboarding, registration and access control
# ---------------------------------------------------------------------------
def test_onboarding_rejects_incomplete_name(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Amina Yusuf Ali",
            "email": "short@example.com",
            "password": "StrongPass1",
            "photo": "https://example.com/p.jpg",
            "date_of_birth": "2001-04-12",
            "program": "Computer Science",
            "phone_number": "+252 61 234 5678",
            "father_phone_number": "+252 61 876 5432",
            "nationality": "Somali",
            "country": "Somalia",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_failed"


def test_full_onboarding_and_rbac(client, container, admin_token, onboard):
    # Registration -> pending email, AI review attached, welcome mail sent.
    registration = client.post(
        "/auth/register",
        json={
            "full_name": "Amina Yusuf Hassan Ali",
            "email": "new.student@deiy.test",
            "password": "StrongPass1",
            "photo": "https://example.com/photo.jpg",
            "date_of_birth": "2001-04-12",
            "program": "Computer Science",
            "phone_number": "+252 61 234 5678",
            "father_phone_number": "+252 61 876 5432",
            "nationality": "Somali",
            "country": "Somalia",
        },
    )
    assert registration.status_code == 201, registration.text
    body = registration.json()
    assert body["user"]["status"] == "pending_email"
    assert re.fullmatch(r"\d{6}", body["dev_code"])
    assert body["user"]["ai_review"]["recommendation"] in {"approve", "review"}

    # Login is blocked before verification.
    blocked = client.post(
        "/auth/login", json={"email": "new.student@deiy.test", "password": "StrongPass1"}
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "email_not_verified"

    # Verify via OTP -> pending approval.
    verified = client.post(
        "/auth/verify-email",
        json={"email": "new.student@deiy.test", "code": body["dev_code"]},
    )
    assert verified.status_code == 200
    assert verified.json()["user"]["status"] == "pending_approval"

    pending = client.post(
        "/auth/login", json={"email": "new.student@deiy.test", "password": "StrongPass1"}
    )
    assert pending.status_code == 403
    assert pending.json()["error"] == "pending_approval"

    # Admin reviews the application and approves it.
    applications = client.get("/admin/applications", headers=auth(admin_token["token"]))
    assert applications.status_code == 200
    assert any(
        item["email"] == "new.student@deiy.test"
        for item in applications.json()["applications"]
    )

    user_id = body["user"]["id"]
    approved = client.post(
        f"/admin/users/{user_id}/approve", headers=auth(admin_token["token"])
    )
    assert approved.status_code == 200, approved.text
    user = approved.json()["user"]
    assert user["status"] == "active"
    assert re.fullmatch(r"DEIY-\d{4}-\d{6}", user["academic_id"])

    # Academic ID is emailed alongside the activation link.
    with container.db.session() as session:
        from deiy.models import OutboxEmail

        emails = session.execute(
            select(OutboxEmail).where(OutboxEmail.to == "new.student@deiy.test")
        ).scalars().all()
    assert any(user["academic_id"] in email.body for email in emails)

    # Login works and /me returns the identity.
    login = client.post(
        "/auth/login", json={"email": "new.student@deiy.test", "password": "StrongPass1"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["user"]["academic_id"] == user["academic_id"]

    # RBAC: a student cannot author content.
    forbidden = client.post(
        "/library/courses",
        headers=auth(token),
        json={"code": "CS101", "title": "Intro"},
    )
    assert forbidden.status_code == 403

    # AI usage was metered for the registration review.
    usage = client.get("/admin/ai-usage", headers=auth(admin_token["token"]))
    assert usage.status_code == 200
    tasks = {row["task"] for row in usage.json()["breakdown"]}
    assert "registration_review" in tasks


# ---------------------------------------------------------------------------
# 2. Content management and digital library
# ---------------------------------------------------------------------------
def test_library_search_watermark_upload_and_live_archive(
    client, container, teacher, onboard
):
    student = onboard(email="library.student@deiy.test")
    headers = teacher["token"]

    course = client.post(
        "/library/courses",
        headers=auth(headers),
        json={
            "code": "MATH201",
            "title": "Linear Algebra",
            "department": "Mathematics",
            "level": "Undergraduate",
        },
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["course"]["id"]

    upload = client.post(
        "/library/resources/upload",
        headers=auth(headers),
        data={
            "title": "Algebra Lecture Notes",
            "kind": "pdf",
            "course_id": course_id,
            "author": "Prof. Nasser",
        },
        files={"file": ("algebra.pdf", b"%PDF-1.4 DEIY test", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    pdf_id = upload.json()["resource"]["id"]

    video = client.post(
        "/library/resources",
        headers=auth(headers),
        json={
            "title": "Matrix Transformations Video",
            "kind": "video",
            "course_id": course_id,
            "author": "Prof. Nasser",
            "storage_key": "resources/video/matrices.mp4",
            "duration_seconds": 900,
            "transcript": "Today we discuss matrix algebra and transformation exercises. "
            "Students should review eigenvalues before the exam.",
        },
    )
    assert video.status_code == 201, video.text
    video_id = video.json()["resource"]["id"]
    assert video.json()["resource"]["resolutions"] == [144, 360, 720]

    # AI-ranked smart search by concept.
    search = client.get(
        "/library/resources",
        params={"q": "matrix algebra"},
        headers=student["headers"],
    )
    assert search.status_code == 200, search.text
    ids = [item["id"] for item in search.json()["results"]]
    assert video_id in ids
    assert search.json()["results"][0]["match"]["score"] > 0

    # Dynamic watermark contains the student's name + academic ID.
    access = client.get(
        f"/library/resources/{video_id}/access", headers=student["headers"]
    )
    assert access.status_code == 200, access.text
    access_body = access.json()
    assert student["full_name"] in access_body["watermark"]["overlay"]["text"]
    assert student["user"]["academic_id"] in access_body["watermark"]["overlay"]["text"]
    assert access_body["viewer"]["full_text_search"] is True
    variants = {item["resolution"] for item in access_body["variants"]}
    assert {"144p", "360p", "720p", "audio"} <= variants

    # Download variant + watermark manifest.
    download = client.get(
        f"/library/resources/{video_id}/download",
        params={"variant": "720p"},
        headers=student["headers"],
    )
    assert download.status_code == 200
    assert download.json()["watermark"]["overlay"]["applies_to"] == ["download"]
    invalid = client.get(
        f"/library/resources/{video_id}/download",
        params={"variant": "1080p"},
        headers=student["headers"],
    )
    assert invalid.status_code == 422

    # Uploaded object is served through a signed media URL.
    pdf_download = client.get(
        f"/library/resources/{pdf_id}/download", headers=student["headers"]
    )
    assert pdf_download.status_code == 200
    url = pdf_download.json()["download_url"]
    media = client.get(url)
    assert media.status_code == 200
    assert media.content == b"%PDF-1.4 DEIY test"
    tampered = client.get(urlparse(url).path)
    assert tampered.status_code in {401, 422}

    # Interactive resource linking inside a lecture/room/exam.
    link = client.post(
        f"/library/resources/{pdf_id}/links",
        headers=auth(headers),
        json={"target_type": "room", "target_id": "room-123", "label": "Reference"},
    )
    assert link.status_code == 201
    links = client.get(
        "/library/links",
        params={"target_type": "room", "target_id": "room-123"},
        headers=student["headers"],
    )
    assert links.status_code == 200
    assert links.json()["links"][0]["resource"]["id"] == pdf_id

    # Live stream auto-archive.
    session = client.post(
        "/library/live-sessions",
        headers=auth(headers),
        json={"title": "Matrix Review Live", "scheduled_at": iso(-1), "course_id": course_id},
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["session"]["id"]
    assert client.post(
        f"/library/live-sessions/{session_id}/start", headers=auth(headers)
    ).status_code == 200
    ended = client.post(f"/library/live-sessions/{session_id}/end", headers=auth(headers))
    assert ended.status_code == 200
    assert ended.json()["session"]["recording_key"]

    assert container.queue.drain() >= 1
    with container.db.session() as db_session:
        jobs = db_session.execute(select(JobRecord)).scalars().all()
        assert any(job.kind == "media.archive_recording" and job.status == "done" for job in jobs)


# ---------------------------------------------------------------------------
# 3. Smart proctored exams
# ---------------------------------------------------------------------------
def test_proctored_exam_camera_autosave_submit_and_integrity(
    client, container, teacher, onboard
):
    student = onboard(email="exam.student@deiy.test")
    exam = client.post(
        "/exams",
        headers=auth(teacher["token"]),
        json={
            "title": "Algebra Midterm",
            "starts_at": iso(-1),
            "ends_at": iso(120),
            "duration_minutes": 60,
            "questions": [
                {
                    "prompt": "What is the identity matrix?",
                    "kind": "mcq",
                    "options": ["Zero matrix", "Diagonal of ones", "Row vector"],
                    "correct_index": 1,
                    "points": 5,
                },
                {
                    "prompt": "Explain eigenvalues in one paragraph.",
                    "kind": "short",
                    "points": 5,
                    "rubric": "Definition plus an example",
                },
            ],
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["exam"]["id"]
    question_ids = [item["id"] for item in exam.json()["questions"]]

    # Camera is mandatory.
    no_camera = client.post(
        f"/exams/{exam_id}/attempts",
        headers=student["headers"],
        json={"camera_verified": False, "camera_device": None},
    )
    assert no_camera.status_code == 422
    assert no_camera.json()["error"] == "camera_required"

    failed_check = client.post(
        f"/exams/{exam_id}/camera-check",
        headers=student["headers"],
        json={"device_id": "cam-1", "stream_ok": False},
    )
    assert failed_check.status_code == 422

    check = client.post(
        f"/exams/{exam_id}/camera-check",
        headers=student["headers"],
        json={"device_id": "cam-1", "stream_ok": True},
    )
    assert check.status_code == 200

    started = client.post(
        f"/exams/{exam_id}/attempts",
        headers=student["headers"],
        json={"camera_verified": True, "camera_device": "cam-1"},
    )
    assert started.status_code == 201, started.text
    attempt = started.json()["attempt"]
    attempt_id = attempt["id"]
    assert attempt["remaining_seconds"] > 0
    assert attempt["policy"]["tab_switching_blocked"] is True
    assert "answer_key" not in started.json()["questions"][0]

    # Second-by-second offline autosave (idempotent replay).
    payload = {
        "client_seq": 5,
        "answers": [
            {"question_id": question_ids[0], "answer": 1, "client_seq": 5},
            {
                "question_id": question_ids[1],
                "answer": "Eigenvalues are scalars describing how a matrix stretches vectors.",
                "client_seq": 5,
            },
        ],
    }
    saved = client.post(
        f"/exams/attempts/{attempt_id}/autosave", headers=student["headers"], json=payload
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["synced"]) == 2

    replay = client.post(
        f"/exams/attempts/{attempt_id}/autosave", headers=student["headers"], json=payload
    )
    assert replay.status_code == 200
    assert len(replay.json()["synced"]) == 2

    stale = client.post(
        f"/exams/attempts/{attempt_id}/autosave",
        headers=student["headers"],
        json={
            "client_seq": 1,
            "answers": [{"question_id": question_ids[0], "answer": 0, "client_seq": 1}],
        },
    )
    assert stale.status_code == 200
    assert stale.json()["synced"] == []

    # Anti-cheat events are recorded.
    events = client.post(
        f"/exams/attempts/{attempt_id}/proctor-events",
        headers=student["headers"],
        json={
            "events": [
                {"kind": "tab_switch", "severity": "high"},
                {"kind": "tab_switch", "severity": "high"},
                {"kind": "face_missing", "severity": "medium"},
            ]
        },
    )
    assert events.status_code == 201, events.text
    assert events.json()["recorded"] == 3

    # Submission grades MCQ automatically and subjective answers with AI.
    submitted = client.post(
        f"/exams/attempts/{attempt_id}/submit", headers=student["headers"]
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["attempt"]["status"] == "submitted"
    assert result["attempt"]["score"] > 0
    assert result["integrity"]["risk_score"] > 0
    assert result["integrity"]["recommendation"] in {"flag_for_review", "invalidate"}

    # Teacher view exposes answer keys; student cannot read another attempt.
    teacher_exam = client.get(f"/exams/{exam_id}", headers=auth(teacher["token"]))
    assert teacher_exam.status_code == 200
    assert "answer_key" in teacher_exam.json()["questions"][0]

    # Deadline enforcement: move the deadline into the past, then read -> terminated.
    with container.db.session() as db_session:
        row = db_session.get(ExamAttempt, attempt_id)
        row.status = "in_progress"
        row.deadline_at = utcnow() - timedelta(seconds=1)
    expired = client.get(f"/exams/attempts/{attempt_id}", headers=student["headers"])
    assert expired.status_code == 200
    assert expired.json()["attempt"]["status"] == "terminated"


# ---------------------------------------------------------------------------
# 4. Micro study rooms + AI summary queue
# ---------------------------------------------------------------------------
def test_study_room_capacity_camera_and_ai_summary(client, container, onboard):
    host = onboard(email="room.host@deiy.test", full_name="Hodan Abdi Warsame Jama")
    academic_id = host["user"]["academic_id"]

    small = client.post(
        "/rooms",
        headers=host["headers"],
        json={"title": "Too small", "capacity": 9},
    )
    assert small.status_code == 422

    room = client.post(
        "/rooms",
        headers=host["headers"],
        json={"title": "Algebra Sprint Room", "capacity": 12},
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["room"]["id"]
    assert room.json()["room"]["max_duration_minutes"] == 45

    wrong_id = client.post(
        f"/rooms/{room_id}/join",
        headers=host["headers"],
        json={"academic_id": "DEIY-0000-000000", "camera_on": True},
    )
    assert wrong_id.status_code == 403

    no_camera = client.post(
        f"/rooms/{room_id}/join",
        headers=host["headers"],
        json={"academic_id": academic_id, "camera_on": False},
    )
    assert no_camera.status_code == 422
    assert no_camera.json()["error"] == "camera_required"

    joined = client.post(
        f"/rooms/{room_id}/join",
        headers=host["headers"],
        json={"academic_id": academic_id, "camera_on": True},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["webrtc"]["token"]
    assert joined.json()["room"]["participant_count"] == 1

    ended = client.post(
        f"/rooms/{room_id}/end",
        headers=host["headers"],
        json={
            "transcript": (
                "Speaker 1 (Hodan): Welcome to the algebra sprint. Today we reviewed "
                "eigenvalues and matrix transformations.\n"
                "Speaker 2 (Student B): I will prepare the formula sheet and share it.\n"
                "Speaker 1 (Hodan): We decided to meet again before the midterm."
            )
        },
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["summary"]["status"] == "queued"

    assert container.queue.drain() >= 1

    summary = client.get(f"/rooms/{room_id}/summary", headers=host["headers"])
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["status"] == "ready"
    assert body["summary"]["overview"]
    assert body["summary"]["key_points"]
    assert body["provider"].endswith("+mock") or "mock" in body["provider"]

    notifications = client.get("/utilities/notifications", headers=host["headers"])
    assert notifications.status_code == 200
    assert any("Study room summary" in item["title"] for item in notifications.json()["notifications"])


# ---------------------------------------------------------------------------
# 5. Utilities, helpdesk, gradebook, calendar
# ---------------------------------------------------------------------------
def test_helpdesk_tickets_calendar_and_gradebook(client, container, teacher, onboard):
    student = onboard(email="utility.student@deiy.test")

    faq = client.post(
        "/utilities/helpdesk",
        headers=student["headers"],
        json={"question": "My camera is black and the webcam is not working"},
    )
    assert faq.status_code == 200, faq.text
    assert faq.json()["escalated"] is False
    assert "camera" in faq.json()["answer"].lower()

    unknown = client.post(
        "/utilities/helpdesk",
        headers=student["headers"],
        json={"question": "My tuition invoice has the wrong billing address for next semester"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["escalated"] is True
    ticket_id = unknown.json()["ticket_id"]
    assert ticket_id

    ticket = client.get(f"/utilities/tickets/{ticket_id}", headers=student["headers"])
    assert ticket.status_code == 200
    roles = [message["role"] for message in ticket.json()["messages"]]
    assert "assistant" in roles

    assignment = client.post(
        "/utilities/assignments",
        headers=auth(teacher["token"]),
        json={"title": "Eigenvalue Worksheet", "due_at": iso(60 * 24)},
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["assignment"]["id"]

    submitted = client.post(
        f"/utilities/assignments/{assignment_id}/submit",
        headers=student["headers"],
        json={"content": "Worked solutions attached."},
    )
    assert submitted.status_code == 200

    graded = client.post(
        f"/utilities/assignments/{assignment_id}/grade",
        headers=auth(teacher["token"]),
        json={"student_id": student["id"], "grade": 92, "feedback": "Excellent work."},
    )
    assert graded.status_code == 200
    assert graded.json()["grade"] == 92

    calendar = client.get("/utilities/calendar", headers=student["headers"])
    assert calendar.status_code == 200
    assert any(event["type"] == "assignment" for event in calendar.json()["events"])

    gradebook = client.get(
        "/utilities/gradebook", params={"insights": True}, headers=student["headers"]
    )
    assert gradebook.status_code == 200, gradebook.text
    assert "ai_insights" in gradebook.json()
    assert gradebook.json()["assignments"][0]["grade"] == 92

    metrics = client.get("/utilities/metrics", headers=auth(teacher["token"]))
    assert metrics.status_code == 403


def test_settings_container_health_and_package_exports(container):
    from deiy import __version__, build_container

    assert __version__ == "1.0.0"
    health = container.health()
    assert health["status"] == "ok"
    assert "exam.expire" in health["job_handlers"]
    assert "room.summarize" in health["job_handlers"]
    assert health["ai"]["text_provider"] == "mock"
    assert health["mail"] == "outbox"

    from deiy.config import Settings

    env_settings = Settings.from_env()
    assert isinstance(env_settings.secret_key, str)
    assert env_settings.secret_key != "member 'secret_key' of 'Settings' objects"
