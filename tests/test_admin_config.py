"""Admin runtime-configuration API tests."""

from __future__ import annotations

from deiy import Settings, build_container
from tests.conftest import auth


def test_admin_config_update_is_audited_and_persisted(
    client, container, admin_token, onboard, settings
):
    student = onboard(email="config.student@deiy.test")

    initial = client.get("/admin/config", headers=auth(admin_token["token"]))
    assert initial.status_code == 200, initial.text
    body = initial.json()["config"]
    assert body["values"]["default_exam_duration_minutes"] == 60
    assert "default_exam_duration_minutes" in body["allowed"]

    denied = client.patch(
        "/admin/config",
        headers=student["headers"],
        json={"values": {"default_exam_duration_minutes": 90}},
    )
    assert denied.status_code == 403

    updated = client.patch(
        "/admin/config",
        headers=auth(admin_token["token"]),
        json={
            "values": {
                "default_exam_duration_minutes": 90,
                "require_camera_for_exam": False,
                "access_token_ttl_seconds": 3600,
            }
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["updated"] == {
        "default_exam_duration_minutes": 90,
        "require_camera_for_exam": False,
        "access_token_ttl_seconds": 3600,
    }
    assert container.settings.default_exam_duration_minutes == 90
    assert container.settings.require_camera_for_exam is False
    assert container.settings.access_token_ttl_seconds == 3600
    assert "default_exam_duration_minutes" in container.config.overrides

    logs = client.get("/admin/audit-logs", headers=auth(admin_token["token"])).json()
    assert any(
        item["action"] == "admin.config.updated" for item in logs["logs"]
    )

    # A fresh process/container must reload the persisted overrides.
    fresh_settings = Settings(
        environment="test",
        secret_key=settings.secret_key,
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        public_base_url=settings.public_base_url,
        job_worker_enabled=False,
    )
    assert fresh_settings.default_exam_duration_minutes == 60
    reloaded = build_container(fresh_settings)
    try:
        assert reloaded.settings.default_exam_duration_minutes == 90
        assert reloaded.settings.require_camera_for_exam is False
        assert reloaded.settings.access_token_ttl_seconds == 3600
        assert "access_token_ttl_seconds" in reloaded.config.overrides
    finally:
        reloaded.db.dispose()

    unknown = client.patch(
        "/admin/config",
        headers=auth(admin_token["token"]),
        json={"values": {"not_a_setting": 1}},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"] == "validation_failed"

    out_of_range = client.patch(
        "/admin/config",
        headers=auth(admin_token["token"]),
        json={"values": {"default_exam_duration_minutes": 1}},
    )
    assert out_of_range.status_code == 422
    assert out_of_range.json()["details"]["minimum"] == 5
