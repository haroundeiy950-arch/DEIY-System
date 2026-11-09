"""Shared pytest fixtures for the DEIY backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from deiy import Settings, create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        environment="test",
        debug=True,
        secret_key="test-secret-key-for-deiy-test-suite-0123456789",
        database_url=f"sqlite:///{(tmp_path / 'deiy-test.db').as_posix()}",
        storage_root=tmp_path / "storage",
        public_base_url="http://testserver",
        expose_dev_codes=True,
        job_worker_enabled=False,
        job_poll_interval_seconds=0.01,
        room_min_capacity=10,
        room_max_capacity=15,
        room_max_duration_minutes=45,
        summary_sla_minutes=10,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def container(app):
    return app.state.container


@pytest.fixture
def admin_token(container):
    container.auth.ensure_admin("admin@deiy.test", "AdminPass1")
    token, user = container.auth.login("admin@deiy.test", "AdminPass1")
    return {"token": token, "user": user}


@pytest.fixture
def teacher(container):
    user = container.auth.create_staff(
        {
            "full_name": "Tariq Mahmoud Saleh Nasser",
            "email": "teacher@deiy.test",
            "password": "TeacherPass1",
            "country": "Egypt",
        },
        role="teacher",
    )
    token, _ = container.auth.login(user.email, "TeacherPass1")
    return {"token": token, "user": user}


@pytest.fixture
def onboard(client, container, admin_token):
    """Register -> verify OTP -> admin approve -> login. Returns auth context."""

    def _onboard(
        email: str = "student@deiy.test",
        full_name: str = "Amina Yusuf Hassan Ali",
        password: str = "StudentPass1",
        approve: bool = True,
    ) -> dict:
        response = client.post(
            "/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
                "photo": "https://example.com/photo.jpg",
                "date_of_birth": "2001-04-12",
                "program": "Computer Science",
                "phone_number": "+252 61 234 5678",
                "father_phone_number": "+252 61 876 5432",
                "nationality": "Somali",
                "country": "Somalia",
                "auth_provider": "email",
                "language": "en",
            },
        )
        assert response.status_code == 201, response.text
        registration = response.json()
        verification = client.post(
            "/auth/verify-email",
            json={"email": email, "code": registration["dev_code"]},
        )
        assert verification.status_code == 200, verification.text
        user_id = registration["user"]["id"]
        if approve:
            approved = client.post(
                f"/admin/users/{user_id}/approve",
                headers={"Authorization": f"Bearer {admin_token['token']}"},
            )
            assert approved.status_code == 200, approved.text
            user = approved.json()["user"]
        else:
            user = verification.json()["user"]
        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        return {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "token": token,
            "user": user,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return _onboard


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
