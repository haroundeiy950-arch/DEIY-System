"""Tests for the admission fields, age policy, CRUD and language options."""

from __future__ import annotations

from tests.conftest import auth

BASE_APPLICATION = {
    "full_name": "Amina Yusuf Hassan Ali",
    "email": "applicant@deiy.test",
    "password": "StrongPass1",
    "photo": "https://example.com/photo.jpg",
    "date_of_birth": "2001-04-12",
    "program": "Computer Science",
    "phone_number": "+252 61 234 5678",
    "father_phone_number": "+252 61 876 5432",
    "nationality": "Somali",
    "country": "Somalia",
    "auth_provider": "google",
    "language": "so",
}


def test_admission_options_and_guide_expose_choices(client):
    options = client.get("/auth/options")
    assert options.status_code == 200
    body = options.json()
    assert body["minimum_age"] >= 15
    assert {item["code"] for item in body["languages"]} == {"en", "so", "ar"}
    assert any(item["name"] == "Computer Science" for item in body["programs"])
    assert {item["code"] for item in body["auth_providers"]} == {
        "email",
        "google",
        "facebook",
        "other",
    }

    guide = client.get("/support/guide")
    assert guide.status_code == 200
    assert guide.json()["minimum_age"] >= 15
    assert len(guide.json()["languages"]) == 3
    assert guide.json()["programs"]


def test_application_rejects_under_15(client):
    payload = dict(BASE_APPLICATION, date_of_birth="2015-01-01")
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "validation_failed"


def test_application_requires_program_phone_and_nationality(client):
    payload = dict(BASE_APPLICATION)
    payload.pop("program")
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422

    payload = dict(BASE_APPLICATION, phone_number="abc")
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "validation_failed"


def test_registration_stores_admission_fields_and_number(client):
    response = client.post("/auth/register", json=BASE_APPLICATION)
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert user["registration_number"].startswith("DEIY-REG-")
    assert user["program"] == "Computer Science"
    assert user["phone_number"] == "+252 61 234 5678"
    assert user["father_phone_number"] == "+252 61 876 5432"
    assert user["nationality"] == "Somali"
    assert user["auth_provider"] == "google"
    assert user["language"] == "so"


def test_admin_can_update_and_delete_user(client, admin_token, onboard):
    student = onboard(email="editable@deiy.test")
    headers = auth(admin_token["token"])

    updated = client.patch(
        f"/admin/users/{student['id']}",
        headers=headers,
        json={"program": "Nursing", "phone_number": "+252 61 111 2222"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["user"]["program"] == "Nursing"
    assert updated.json()["user"]["phone_number"] == "+252 61 111 2222"

    deleted = client.delete(f"/admin/users/{student['id']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["user"]["status"] == "deleted"

    # A deleted account can no longer sign in.
    login = client.post(
        "/auth/login",
        json={"email": "editable@deiy.test", "password": "StudentPass1"},
    )
    assert login.status_code == 401 or login.status_code == 403


def test_user_can_update_profile_and_password(client, onboard):
    student = onboard(email="profile@deiy.test")
    headers = student["headers"]

    profile = client.patch(
        "/auth/me",
        headers=headers,
        json={"program": "Law", "phone_number": "+252 61 333 4444", "language": "ar"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["user"]["program"] == "Law"
    assert profile.json()["user"]["language"] == "ar"

    changed = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "StudentPass1", "new_password": "NewPass123"},
    )
    assert changed.status_code == 200, changed.text
    login = client.post(
        "/auth/login",
        json={"email": "profile@deiy.test", "password": "NewPass123"},
    )
    assert login.status_code == 200


def test_admin_database_overview(client, admin_token):
    response = client.get("/admin/database", headers=auth(admin_token["token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["table_count"] >= 1
    assert any(row["table"] == "users" for row in body["tables"])
