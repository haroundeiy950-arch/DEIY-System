"""Regression tests for the demo-data script."""

from __future__ import annotations

from sqlalchemy import func, select

import seed
from deiy import Settings, build_container
from deiy.models import (
    Assignment,
    AttendanceRecord,
    Course,
    Exam,
    ExamAttempt,
    Resource,
    StudyRoom,
    User,
)


def test_seed_is_repeatable_and_wired(tmp_path):
    settings = Settings(
        environment="test",
        debug=True,
        secret_key="test-secret-key-for-deiy-seed-suite-0123456789",
        database_url=f"sqlite:///{(tmp_path / 'seed.db').as_posix()}",
        storage_root=tmp_path / "storage",
        public_base_url="http://testserver",
        expose_dev_codes=True,
        job_worker_enabled=False,
        job_poll_interval_seconds=0.01,
    )
    container = build_container(settings)
    try:
        first = seed.seed(container)
        second = seed.seed(container)

        assert first["admin"].email == seed.ADMIN_EMAIL
        assert first["teacher"].role == "teacher"
        assert first["proctor"].role == "proctor"
        assert [student.academic_id for student in second["students"]] == [
            first["students"][0].academic_id,
            first["students"][1].academic_id,
        ]

        
        assert second["attempt"].score is not None
        assert second["attempt"].integrity is not None
        assert second["room_summary"].status == "ready"
        assert second["jobs_failed"] == 0

        with container.db.session() as session:
            counts = {
                "users": session.execute(select(func.count(User.id))).scalar(),
                "courses": session.execute(select(func.count(Course.id))).scalar(),
                "resources": session.execute(select(func.count(Resource.id))).scalar(),
                "exams": session.execute(select(func.count(Exam.id))).scalar(),
                "attempts": session.execute(select(func.count(ExamAttempt.id))).scalar(),
                "assignments": session.execute(
                    select(func.count(Assignment.id))
                ).scalar(),
                "attendance": session.execute(
                    select(func.count(AttendanceRecord.id))
                ).scalar(),
                "rooms": session.execute(select(func.count(StudyRoom.id))).scalar(),
            }
        assert counts == {
            "users": 5,
            "courses": 1,
            "resources": 3,
            "exams": 1,
            "attempts": 1,
            "assignments": 1,
            "attendance": 1,
            "rooms": 1,
        }

        token, user = container.auth.login(seed.STUDENT_EMAIL, seed.STUDENT_PASSWORD)
        assert token
        gradebook = container.utilities.gradebook(user.id, include_insights=True)
        assert gradebook["average_score"] is not None
        assert gradebook["ai_insights"]
    finally:
        container.db.dispose()
