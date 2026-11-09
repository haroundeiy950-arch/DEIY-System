"""Create reproducible demo data for the DEIY backend.

Usage::

    python seed.py
    python seed.py --database-url sqlite:///./demo.db

The script walks the same service layer the HTTP API uses, so every demo row
also exercises the production wiring:

* onboarding (register -> OTP verification -> admin approval -> academic ID);
* course + library resources (AI enrichment, tags and summaries);
* a live lecture that is started/ended so the automatic archive job is queued;
* a complete exam attempt (camera check, answers, autosave, proctoring event,
  AI grading and integrity report);
* a micro study room with camera-verified participants and a queued AI summary;
* an assignment with a graded submission and an attendance record.

It is safe to run repeatedly: existing demo rows are reused instead of
duplicated. The default credentials are only intended for local development.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from deiy import Settings, build_container
from deiy.errors import AppError
from deiy.models import (
    Assignment,
    AttendanceRecord,
    Course,
    Exam,
    ExamAttempt,
    JobRecord,
    LiveSession,
    Resource,
    RoomSummary,
    StudyRoom,
    User,
)
from deiy.utils import naive_utc

ADMIN_EMAIL = "admin@deiy.local"
ADMIN_PASSWORD = "AdminPass1"
TEACHER_EMAIL = "teacher@deiy.local"
TEACHER_PASSWORD = "TeacherPass1"
PROCTOR_EMAIL = "proctor@deiy.local"
PROCTOR_PASSWORD = "ProctorPass1"
STUDENT_EMAIL = "student@deiy.local"
STUDENT_PASSWORD = "StudentPass1"
STUDENT2_EMAIL = "student2@deiy.local"
STUDENT2_PASSWORD = "StudentPass1"

COURSE_CODE = "CS201"
COURSE_TITLE = "Algorithms and Data Structures"
ASSIGNMENT_TITLE = "Complexity analysis worksheet"
EXAM_TITLE = "Algorithms midterm (proctored)"
ROOM_TITLE = "Algorithms revision room"
SESSION_TITLE = "Algorithms live lecture: graph traversal"


def _now() -> datetime:
    return naive_utc(datetime.now(timezone.utc))


def _user_by_email(container, email: str) -> User | None:
    with container.db.session() as session:
        return session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()


def _ensure_admin(container) -> User:
    user = container.auth.ensure_admin(
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
        full_name="System Administrator Account",
    )
    # ``ensure_admin`` returns a detached instance; reload for a stable object.
    return container.auth.get_user(user.id)


def _ensure_staff(container, *, email: str, password: str, role: str, full_name: str) -> User:
    existing = _user_by_email(container, email)
    if existing is not None:
        return existing
    user = container.auth.create_staff(
        {
            "full_name": full_name,
            "email": email,
            "password": password,
            "country": "N/A",
        },
        role=role,
    )
    return container.auth.get_user(user.id)


def _verify_and_approve(container, *, user: User, registration: dict, admin: User) -> User:
    code = registration.get("dev_code")
    link = registration.get("dev_link")
    if code:
        container.auth.verify_email(email=user.email, code=code)
    elif link:
        token = link.split("token=", 1)[-1]
        container.auth.verify_email(email=user.email, token=token)
    else:
        raise RuntimeError(
            "Verification secrets are not exposed. Set DEIY_EXPOSE_DEV_CODES=true "
            "for local seeding, or create the student through the API."
        )
    return container.auth.approve(user.id, actor_id=admin.id)


def _ensure_student(
    container,
    *,
    email: str,
    password: str,
    full_name: str,
    country: str,
    date_of_birth: date,
    admin: User,
    program: str = "Computer Science",
    phone_number: str = "+252 61 234 5678",
    father_phone_number: str = "+252 61 876 5432",
    nationality: str | None = None,
) -> User:
    existing = _user_by_email(container, email)
    if existing is not None:
        if existing.status == "active":
            return existing
        if existing.status == "pending_email":
            resent = container.auth.resend_verification(email)
            code = resent.get("dev_code")
            if not code:
                raise RuntimeError(
                    f"{email} is pending email verification and no development "
                    "code was returned. Set DEIY_EXPOSE_DEV_CODES=true."
                )
            container.auth.verify_email(email=email, code=code)
            existing = container.auth.get_user(existing.id)
        if existing.status == "pending_approval":
            return container.auth.approve(existing.id, actor_id=admin.id)
        raise RuntimeError(f"{email} has unsupported status '{existing.status}'.")

    registration = container.auth.register(
        {
            "full_name": full_name,
            "email": email,
            "password": password,
            "photo": "https://placehold.co/512x512/png?text=DEIY",
            "date_of_birth": date_of_birth,
            "country": country,
            "program": program,
            "phone_number": phone_number,
            "father_phone_number": father_phone_number,
            "nationality": nationality or country,
            "auth_provider": "email",
            "language": "en",
        }
    )
    user = container.auth.get_user(registration["user"]["id"])
    return _verify_and_approve(
        container, user=user, registration=registration, admin=admin
    )


def _ensure_course(container, teacher: User) -> Course:
    with container.db.session() as session:
        existing = session.execute(
            select(Course).where(Course.code == COURSE_CODE)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    return container.library.create_course(
        {
            "code": COURSE_CODE,
            "title": COURSE_TITLE,
            "department": "Computer Science",
            "level": "Undergraduate",
            "description": (
                "Core algorithms course covering complexity, sorting, graphs and "
                "data-structure selection with weekly labs."
            ),
            "teacher_id": teacher.id,
        },
        actor_id=teacher.id,
    )


def _ensure_resource(
    container,
    *,
    course: Course,
    teacher: User,
    title: str,
    kind: str,
    storage_key: str,
    body: bytes,
    mime_type: str,
    transcript: str | None = None,
    duration_seconds: int = 0,
) -> Resource:
    with container.db.session() as session:
        existing = session.execute(
            select(Resource).where(
                Resource.title == title, Resource.course_id == course.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    if not container.storage.exists(storage_key):
        container.storage.put_bytes(storage_key, body)

    return container.library.create_resource(
        {
            "course_id": course.id,
            "title": title,
            "author": teacher.full_name,
            "kind": kind,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "size_bytes": len(body),
            "duration_seconds": duration_seconds,
            "transcript": transcript,
        },
        actor_id=teacher.id,
    )


def _ensure_live_session(container, course: Course, teacher: User) -> LiveSession:
    with container.db.session() as session:
        existing = session.execute(
            select(LiveSession).where(LiveSession.title == SESSION_TITLE)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    row = container.library.schedule_session(
        {
            "title": SESSION_TITLE,
            "scheduled_at": _now() - timedelta(minutes=45),
            "course_id": course.id,
        },
        actor_id=teacher.id,
    )
    container.library.start_session(row.id)
    container.library.end_session(row.id)
    with container.db.session() as session:
        return session.get(LiveSession, row.id)


def _ensure_exam(container, course: Course, teacher: User, student: User) -> Exam:
    with container.db.session() as session:
        existing = session.execute(
            select(Exam).where(Exam.title == EXAM_TITLE)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    payload = container.exams.create_exam(
        {
            "course_id": course.id,
            "title": EXAM_TITLE,
            "instructions": (
                "The webcam must stay on for the whole attempt. Tab switching, "
                "secondary displays and multiple faces are recorded as integrity events."
            ),
            "starts_at": _now() - timedelta(minutes=10),
            "ends_at": _now() + timedelta(days=3),
            "duration_minutes": 60,
            "questions": [
                {
                    "prompt": "Which complexity class describes binary search?",
                    "kind": "mcq",
                    "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                    "correct_index": 1,
                    "points": 2,
                },
                {
                    "prompt": "State the eigenvalue equation for a matrix A and vector v.",
                    "kind": "short",
                    "expected_answer": "A v = lambda v",
                    "points": 2,
                },
                {
                    "prompt": "Explain when a hash table is preferable to a balanced search tree.",
                    "kind": "essay",
                    "rubric": (
                        "Mention expected O(1) lookup, collision handling, ordering "
                        "trade-offs and worst-case behaviour."
                    ),
                    "points": 4,
                },
            ],
        },
        actor_id=teacher.id,
    )
    exam_id = payload["exam"]["id"]
    question_ids = [question["id"] for question in payload["questions"]]

    # Demo a complete attempt so the gradebook, notifications and AI integrity
    # report have real data. Camera verification is mandatory, as in production.
    container.exams.camera_check(exam_id, device_id="seed-webcam", stream_ok=True)
    attempt_payload = container.exams.start_attempt(
        student,
        exam_id,
        camera_verified=True,
        camera_device="seed-webcam",
    )
    attempt_id = attempt_payload["attempt"]["id"]
    container.exams.record_events(
        attempt_id,
        [
            {
                "kind": "tab_switch",
                "severity": "medium",
                "payload": {"count": 1, "source": "seed-demo"},
            }
        ],
        actor=student,
    )
    container.exams.autosave(
        attempt_id,
        student.id,
        [
            {"question_id": question_ids[0], "answer": {"index": 1}},
            {
                "question_id": question_ids[1],
                "answer": "A v = lambda v, where v is a non-zero eigenvector.",
            },
            {
                "question_id": question_ids[2],
                "answer": (
                    "Hash tables give expected O(1) lookup and are preferable when "
                    "ordering is irrelevant and collisions are controlled. Balanced "
                    "trees keep O(log n) worst-case guarantees and support range queries."
                ),
            },
        ],
        client_seq=1,
    )
    container.exams.submit(attempt_id, student.id)

    with container.db.session() as session:
        return session.get(Exam, exam_id)


def _ensure_assignment(container, course: Course, teacher: User, student: User) -> Assignment:
    with container.db.session() as session:
        existing = session.execute(
            select(Assignment).where(Assignment.title == ASSIGNMENT_TITLE)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    assignment = container.utilities.create_assignment(
        {
            "course_id": course.id,
            "title": ASSIGNMENT_TITLE,
            "description": "Derive the complexity of merge sort and binary search.",
            "due_at": _now() + timedelta(days=5),
        },
        actor_id=teacher.id,
    )
    container.utilities.submit_assignment(
        assignment.id,
        student.id,
        (
            "Merge sort performs O(n log n) comparisons in all cases; binary "
            "search halves the interval each step, giving O(log n)."
        ),
    )
    container.utilities.grade_submission(
        assignment.id,
        student.id,
        92,
        "Clear derivation. Add a short note on space complexity next time.",
        actor_id=teacher.id,
    )
    return assignment


def _ensure_attendance(container, course: Course, teacher: User, student: User) -> AttendanceRecord:
    with container.db.session() as session:
        existing = session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.course_id == course.id,
                AttendanceRecord.student_id == student.id,
            )
        ).scalars().first()
        if existing is not None:
            return existing
    return container.utilities.record_attendance(
        {
            "student_id": student.id,
            "course_id": course.id,
            "status": "present",
            "occurred_at": _now() - timedelta(hours=2),
        },
        actor_id=teacher.id,
    )


def _ensure_room(
    container, course: Course, teacher: User, students: list[User]
) -> StudyRoom | None:
    with container.db.session() as session:
        existing = session.execute(
            select(StudyRoom).where(StudyRoom.title == ROOM_TITLE)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    room = container.rooms.create_room(
        teacher,
        {
            "title": ROOM_TITLE,
            "course_id": course.id,
            "capacity": 12,
        },
    )
    for student in students:
        container.rooms.join(
            room["id"],
            student,
            academic_id=student.academic_id or "",
            camera_on=True,
        )
    container.rooms.end_room(
        room["id"],
        actor=teacher,
        transcript_hint=(
            "The group reviewed graph traversal, compared BFS and DFS, and agreed "
            "to practise topological sorting before the midterm."
        ),
    )
    with container.db.session() as session:
        return session.get(StudyRoom, room["id"])


def seed(container, *, drain_queue: bool = True) -> dict:
    """Seed demo data and return a summary of the created objects."""

    admin = _ensure_admin(container)
    teacher = _ensure_staff(
        container,
        email=TEACHER_EMAIL,
        password=TEACHER_PASSWORD,
        role="teacher",
        full_name="Tariq Mahmoud Saleh Nasser",
    )
    proctor = _ensure_staff(
        container,
        email=PROCTOR_EMAIL,
        password=PROCTOR_PASSWORD,
        role="proctor",
        full_name="Hodan Abdi Farah Warsame",
    )
    student = _ensure_student(
        container,
        email=STUDENT_EMAIL,
        password=STUDENT_PASSWORD,
        full_name="Amina Yusuf Hassan Ali",
        country="Somalia",
        date_of_birth=date(2004, 5, 12),
        admin=admin,
    )
    student2 = _ensure_student(
        container,
        email=STUDENT2_EMAIL,
        password=STUDENT2_PASSWORD,
        full_name="Mohamed Ahmed Omar Nur",
        country="Kenya",
        date_of_birth=date(2003, 11, 2),
        admin=admin,
    )

    course = _ensure_course(container, teacher)
    resources = [
        _ensure_resource(
            container,
            course=course,
            teacher=teacher,
            title="Algorithms course handbook",
            kind="pdf",
            storage_key="demo/resources/algorithms-handbook.pdf",
            body=(
                b"%PDF-1.4\n"
                b"% DEIY demo handbook\n"
                b"Complexity analysis, sorting, graphs and data-structure selection.\n"
            ),
            mime_type="application/pdf",
            transcript=(
                "This handbook covers asymptotic notation, sorting algorithms, "
                "graph traversal and exam preparation guidance."
            ),
        ),
        _ensure_resource(
            container,
            course=course,
            teacher=teacher,
            title="Graph traversal lecture recording",
            kind="video",
            storage_key="demo/resources/graph-traversal.mp4",
            body=b"DEIY demo video placeholder\n",
            mime_type="video/mp4",
            duration_seconds=1800,
            transcript=(
                "In this lecture we compare breadth-first and depth-first search, "
                "discuss topological sorting and review shortest paths."
            ),
        ),
        _ensure_resource(
            container,
            course=course,
            teacher=teacher,
            title="Data structures reference (EPUB)",
            kind="epub",
            storage_key="demo/resources/data-structures.epub",
            body=b"DEIY demo EPUB placeholder\n",
            mime_type="application/epub+zip",
            transcript=(
                "Reference chapters on arrays, linked lists, stacks, queues, hash "
                "tables, trees and heaps."
            ),
        ),
    ]
    live_session = _ensure_live_session(container, course, teacher)
    exam = _ensure_exam(container, course, teacher, student)
    assignment = _ensure_assignment(container, course, teacher, student)
    attendance = _ensure_attendance(container, course, teacher, student)
    room = _ensure_room(container, course, teacher, [student, student2])

    jobs_done = 0
    if drain_queue:
        jobs_done = container.queue.drain(limit=200)

    with container.db.session() as session:
        summary_status = (
            session.execute(
                select(RoomSummary).where(RoomSummary.room_id == room.id)
            ).scalar_one_or_none()
            if room is not None
            else None
        )
        attempt = session.execute(
            select(ExamAttempt).where(
                ExamAttempt.exam_id == exam.id,
                ExamAttempt.student_id == student.id,
            )
        ).scalar_one_or_none()
        failed_jobs = session.execute(
            select(func.count(JobRecord.id)).where(JobRecord.status == "failed")
        ).scalar() or 0

    return {
        "admin": admin,
        "teacher": teacher,
        "proctor": proctor,
        "students": [student, student2],
        "course": course,
        "resources": resources,
        "live_session": live_session,
        "exam": exam,
        "attempt": attempt,
        "assignment": assignment,
        "attendance": attendance,
        "room": room,
        "room_summary": summary_status,
        "jobs_drained": jobs_done,
        "jobs_pending": container.queue.pending(),
        "jobs_failed": int(failed_jobs),
    }


def _print_summary(settings: Settings, result: dict) -> None:
    admin: User = result["admin"]
    teacher: User = result["teacher"]
    proctor: User = result["proctor"]
    student, student2 = result["students"]
    exam = result["exam"]
    attempt = result["attempt"]
    summary = result["room_summary"]

    print()
    print("=" * 72)
    print(f"DEIY demo data ready - {settings.database_url}")
    print("=" * 72)
    print("Accounts (development credentials)")
    print(f"  Admin    {ADMIN_EMAIL:<24} {ADMIN_PASSWORD:<14} {admin.academic_id}")
    print(f"  Teacher  {TEACHER_EMAIL:<24} {TEACHER_PASSWORD:<14} {teacher.academic_id}")
    print(f"  Proctor  {PROCTOR_EMAIL:<24} {PROCTOR_PASSWORD:<14} {proctor.academic_id}")
    print(f"  Student  {STUDENT_EMAIL:<24} {STUDENT_PASSWORD:<14} {student.academic_id}")
    print(f"  Student  {STUDENT2_EMAIL:<23} {STUDENT2_PASSWORD:<14} {student2.academic_id}")
    print()
    print("Demo content")
    print(f"  Course      {result['course'].code} - {result['course'].title}")
    print(f"  Library     {len(result['resources'])} resources (PDF, video, EPUB)")
    print(f"  Live        {result['live_session'].title} ({result['live_session'].status})")
    print(f"  Exam        {exam.title}")
    if attempt is not None:
        print(
            f"  Attempt     score {attempt.score}, status {attempt.status}, "
            f"integrity {(attempt.integrity or {}).get('recommendation')}"
        )
    print(f"  Assignment  {ASSIGNMENT_TITLE} (graded)")
    print(f"  Attendance  {result['attendance'].status}")
    print(
        "  Study room  "
        f"{result['room'].title} ({result['room'].capacity} seats, {result['room'].status})"
    )
    if summary is not None:
        print(f"  AI summary  {summary.status} ({summary.provider or 'queued'})")
    print()
    print(
        f"Background jobs: {result['jobs_drained']} processed, "
        f"{result['jobs_pending']} pending, {result['jobs_failed']} failed"
    )
    print(f"Storage root:    {settings.storage_root}")
    print(f"API docs:        {settings.public_base_url}/docs")
    if settings.is_production:
        print()
        print("WARNING: development credentials were used in a production environment.")
        print("Change every password and disable DEIY_EXPOSE_DEV_CODES immediately.")
    print("=" * 72)
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the DEIY demo database.")
    parser.add_argument(
        "--database-url",
        help="Override DEIY_DATABASE_URL (e.g. sqlite:///./demo.db).",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        help="Override DEIY_STORAGE_ROOT for local storage.",
    )
    parser.add_argument(
        "--no-drain",
        action="store_true",
        help="Leave background jobs queued instead of processing due jobs now.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if args.database_url:
        settings.database_url = args.database_url
    if args.storage_root:
        settings.storage_root = args.storage_root

    container = build_container(settings)
    try:
        result = seed(container, drain_queue=not args.no_drain)
        _print_summary(settings, result)
    except AppError as exc:
        print(f"Seed failed: {exc.message}", file=sys.stderr)
        return 1
    finally:
        container.db.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
