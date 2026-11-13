"""Regression tests for the delete actions and database backup endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_course_and_resource_deletion(client, teacher, onboard):
    student = onboard(email="delete.library@deiy.test")
    headers = auth(teacher["token"])

    course = client.post(
        "/library/courses",
        headers=headers,
        json={"code": "DEL101", "title": "Deletable Course", "department": "Testing"},
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["course"]["id"]

    upload = client.post(
        "/library/resources/upload",
        headers=headers,
        data={"title": "Delete Me Notes", "kind": "pdf", "course_id": course_id},
        files={"file": ("delete-me.pdf", b"%PDF-1.4 delete test", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    resource_id = upload.json()["resource"]["id"]

    link = client.post(
        f"/library/resources/{resource_id}/links",
        headers=headers,
        json={"target_type": "room", "target_id": "room-x", "label": "Reference"},
    )
    assert link.status_code == 201, link.text

    assignment = client.post(
        "/utilities/assignments",
        headers=headers,
        json={"title": "Course Assignment", "due_at": iso(60), "course_id": course_id},
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["assignment"]["id"]

    removed_course = client.delete(f"/library/courses/{course_id}", headers=headers)
    assert removed_course.status_code == 200, removed_course.text
    assert removed_course.json()["course"]["id"] == course_id
    missing_course = client.delete(f"/library/courses/{course_id}", headers=headers)
    assert missing_course.status_code == 404

    # Dependent records are kept but unlinked from the deleted course.
    resource = client.get(f"/library/resources/{resource_id}", headers=student["headers"])
    assert resource.status_code == 200, resource.text
    assert resource.json()["resource"]["course_id"] is None
    assignments = client.get("/utilities/assignments", headers=headers)
    assert assignments.status_code == 200
    kept = {row["id"]: row for row in assignments.json()["assignments"]}
    assert kept[assignment_id]["course_id"] is None

    removed_resource = client.delete(f"/library/resources/{resource_id}", headers=headers)
    assert removed_resource.status_code == 200, removed_resource.text
    missing_resource = client.get(f"/library/resources/{resource_id}", headers=student["headers"])
    assert missing_resource.status_code == 404
    links = client.get(
        "/library/links",
        params={"target_type": "room", "target_id": "room-x"},
        headers=headers,
    )
    assert links.status_code == 200
    assert links.json()["links"] == []
    assert client.delete(f"/library/resources/{resource_id}", headers=headers).status_code == 404


def test_live_session_and_exam_deletion(client, teacher, onboard):
    student = onboard(email="delete.exam@deiy.test")
    headers = auth(teacher["token"])

    session = client.post(
        "/library/live-sessions",
        headers=headers,
        json={"title": "Deletable Lecture", "scheduled_at": iso(30)},
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["session"]["id"]
    removed_session = client.delete(f"/library/live-sessions/{session_id}", headers=headers)
    assert removed_session.status_code == 200, removed_session.text
    assert client.delete(f"/library/live-sessions/{session_id}", headers=headers).status_code == 404

    exam = client.post(
        "/exams",
        headers=headers,
        json={
            "title": "Deletable Exam",
            "starts_at": iso(-1),
            "ends_at": iso(120),
            "duration_minutes": 30,
            "questions": [
                {
                    "prompt": "Pick one.",
                    "kind": "mcq",
                    "options": ["A", "B"],
                    "correct_index": 0,
                    "points": 5,
                }
            ],
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["exam"]["id"]

    started = client.post(
        f"/exams/{exam_id}/attempts",
        headers=student["headers"],
        json={"camera_verified": True, "camera_device": "cam-1"},
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["attempt"]["id"]

    removed_exam = client.delete(f"/exams/{exam_id}", headers=headers)
    assert removed_exam.status_code == 200, removed_exam.text
    assert client.get(f"/exams/{exam_id}", headers=headers).status_code == 404
    assert client.get(f"/exams/attempts/{attempt_id}", headers=student["headers"]).status_code == 404
    assert client.delete(f"/exams/{exam_id}", headers=headers).status_code == 404


def test_room_deletion_requires_host_or_admin(client, onboard):
    host = onboard(email="delete.room.host@deiy.test", full_name="Hodan Abdi Warsame Jama")
    other = onboard(email="delete.room.other@deiy.test", full_name="Yusuf Omar Aden Farah")

    room = client.post(
        "/rooms",
        headers=host["headers"],
        json={"title": "Deletable Room", "capacity": 12},
    )
    assert room.status_code == 201, room.text
    room_id = room.json()["room"]["id"]

    forbidden = client.delete(f"/rooms/{room_id}", headers=other["headers"])
    assert forbidden.status_code == 403
    removed = client.delete(f"/rooms/{room_id}", headers=host["headers"])
    assert removed.status_code == 200, removed.text
    assert client.get(f"/rooms/{room_id}", headers=host["headers"]).status_code == 404
    assert client.delete(f"/rooms/{room_id}", headers=host["headers"]).status_code == 404


def test_assignment_notification_and_ticket_deletion(client, container, teacher, onboard):
    owner = onboard(email="delete.owner@deiy.test")
    rival = onboard(email="delete.rival@deiy.test", full_name="Yusuf Omar Aden Farah")

    assignment = client.post(
        "/utilities/assignments",
        headers=auth(teacher["token"]),
        json={"title": "Deletable Assignment", "due_at": iso(60)},
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["assignment"]["id"]
    submitted = client.post(
        f"/utilities/assignments/{assignment_id}/submit",
        headers=owner["headers"],
        json={"content": "Answers."},
    )
    assert submitted.status_code == 200, submitted.text

    removed = client.delete(
        f"/utilities/assignments/{assignment_id}", headers=auth(teacher["token"])
    )
    assert removed.status_code == 200, removed.text
    assignments = client.get("/utilities/assignments", headers=owner["headers"])
    assert assignment_id not in {row["id"] for row in assignments.json()["assignments"]}
    assert client.delete(
        f"/utilities/assignments/{assignment_id}", headers=auth(teacher["token"])
    ).status_code == 404

    notification = container.utilities.notify(owner["id"], "Deletable notice", "Body text.")
    assert notification
    notification_id = notification["id"]
    rival_attempt = client.delete(
        f"/utilities/notifications/{notification_id}", headers=rival["headers"]
    )
    assert rival_attempt.status_code == 404
    removed_notification = client.delete(
        f"/utilities/notifications/{notification_id}", headers=owner["headers"]
    )
    assert removed_notification.status_code == 200, removed_notification.text

    ticket = client.post(
        "/utilities/tickets",
        headers=owner["headers"],
        json={"subject": "Deletable ticket", "body": "Please remove this ticket."},
    )
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["ticket"]["id"]
    forbidden = client.delete(f"/utilities/tickets/{ticket_id}", headers=rival["headers"])
    assert forbidden.status_code == 403
    removed_ticket = client.delete(f"/utilities/tickets/{ticket_id}", headers=owner["headers"])
    assert removed_ticket.status_code == 200, removed_ticket.text
    assert client.get(f"/utilities/tickets/{ticket_id}", headers=owner["headers"]).status_code == 404


def test_admin_database_overview_and_download(client, admin_token, onboard):
    student = onboard(email="delete.database@deiy.test")

    forbidden = client.get("/admin/database", headers=student["headers"])
    assert forbidden.status_code == 403

    overview = client.get("/admin/database", headers=auth(admin_token["token"]))
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["table_count"] == len(body["tables"]) > 0
    assert body["total_rows"] == sum(row["rows"] for row in body["tables"])

    download = client.get("/admin/database/download", headers=auth(admin_token["token"]))
    assert download.status_code == 200, download.text
    assert download.content.startswith(b"SQLite format 3\x00")
    assert "attachment" in download.headers.get("content-disposition", "")

    forbidden_download = client.get(
        "/admin/database/download", headers=student["headers"]
    )
    assert forbidden_download.status_code == 403


def test_live_session_deletion_preserves_attendance(
    client, teacher, onboard, container
):
    from deiy.models import AttendanceRecord

    student = onboard(email="attendance.delete@deiy.test")
    headers = auth(teacher["token"])

    created = client.post(
        "/library/live-sessions",
        headers=headers,
        json={
            "title": "Attendance Preservation Test",
            "scheduled_at": iso(30),
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session"]["id"]

    attendance = client.post(
        "/utilities/attendance",
        headers=headers,
        json={
            "student_id": student["id"],
            "session_id": session_id,
            "status": "present",
        },
    )
    assert attendance.status_code in (200, 201), attendance.text

    deleted = client.delete(
        f"/library/live-sessions/{session_id}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text

    with container.db.session() as db_session:
        record = (
            db_session.query(AttendanceRecord)
            .filter(AttendanceRecord.student_id == student["id"])
            .one()
        )
        assert record.session_id is None
        assert record.status == "present"


def test_live_session_deletion_preserves_attendance(
    client, teacher, onboard, container
):
    from deiy.models import AttendanceRecord

    student = onboard(email="attendance.delete@deiy.test")
    headers = auth(teacher["token"])

    # Create a live session.
    created = client.post(
        "/library/live-sessions",
        headers=headers,
        json={
            "title": "Attendance Preservation Test",
            "scheduled_at": iso(30),
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session"]["id"]

    # Record student attendance.
    attendance = client.post(
        "/utilities/attendance",
        headers=headers,
        json={
            "student_id": student["id"],
            "session_id": session_id,
            "status": "present",
        },
    )
    assert attendance.status_code == 201, attendance.text
    attendance_id = attendance.json()["attendance_id"]

    # Delete the live session.
    deleted = client.delete(
        f"/library/live-sessions/{session_id}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text

    # Verify attendance is preserved and detached from the session.
    with container.db.session() as db_session:
        record = db_session.get(AttendanceRecord, attendance_id)
        assert record is not None
        assert record.session_id is None
        assert record.status == "present"

