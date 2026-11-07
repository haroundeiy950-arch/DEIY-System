from __future__ import annotations

import pytest

from deiy.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "secret_key": "A" * 32,
        "debug": False,
        "auto_admin": False,
        "expose_dev_codes": False,
        "public_base_url": "https://app.example.com",
        "cors_origins": ("https://app.example.com",),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret_key": "dev-only-change-me-please-32-bytes-minimum"},
        {"secret_key": "too-short"},
        {"debug": True},
        {"auto_admin": True},
        {"expose_dev_codes": True},
    ],
)
def test_production_rejects_insecure_settings(overrides):
    settings = production_settings(**overrides)

    with pytest.raises(ValueError, match="Insecure production configuration"):
        settings.validate_security()



@pytest.mark.parametrize(
    "overrides",
    [
        {"public_base_url": "http://app.example.com"},
        {"public_base_url": "not-a-url"},
        {"cors_origins": ("*",)},
        {"cors_origins": ()},
        {"cors_origins": ("http://app.example.com",)},
        {"cors_origins": ("https://app.example.com/path",)},
    ],
)
def test_production_rejects_insecure_https_and_cors_settings(overrides):
    settings = production_settings(**overrides)

    with pytest.raises(ValueError, match="Insecure production configuration"):
        settings.validate_security()

def test_production_accepts_secure_settings():
    production_settings().validate_security()


def test_development_keeps_default_settings_available():
    Settings().validate_security()


def test_create_app_validates_before_building_container(monkeypatch):
    import deiy.api.app as app_module

    def unexpected_build(*args, **kwargs):
        raise AssertionError("Container must not be built with insecure settings")

    monkeypatch.setattr(app_module, "build_container", unexpected_build)

    with pytest.raises(ValueError, match="Insecure production configuration"):
        app_module.create_app(production_settings(secret_key="dev-only-change-me-please-32-bytes-minimum"))


def test_build_container_validates_before_database_creation(monkeypatch):
    import deiy.container as container_module

    def unexpected_database(*args, **kwargs):
        raise AssertionError("Database must not be created with insecure settings")

    monkeypatch.setattr(container_module, "Database", unexpected_database)

    with pytest.raises(ValueError, match="Insecure production configuration"):
        container_module.build_container(
            production_settings(secret_key="dev-only-change-me-please-32-bytes-minimum")
        )
