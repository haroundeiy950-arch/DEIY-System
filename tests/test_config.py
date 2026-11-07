"""Configuration tests, including the dependency-free .env loader."""

from __future__ import annotations

import os

from deiy.config import load_env_file


def test_env_file_is_parsed_without_overwriting_existing_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "",
                "DEIY_TEST_FROM_FILE=loaded",
                "export DEIY_TEST_QUOTED='quoted value'",
                "DEIY_TEST_EXISTING=from-file",
                "not a valid line",
                "1INVALID=ignored",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEIY_TEST_EXISTING", "from-process")
    monkeypatch.delenv("DEIY_TEST_FROM_FILE", raising=False)
    monkeypatch.delenv("DEIY_TEST_QUOTED", raising=False)

    assert load_env_file(env_file) == env_file
    assert os.environ["DEIY_TEST_FROM_FILE"] == "loaded"
    assert os.environ["DEIY_TEST_QUOTED"] == "quoted value"
    assert os.environ["DEIY_TEST_EXISTING"] == "from-process"
    assert "1INVALID" not in os.environ


def test_missing_env_file_is_harmless(tmp_path):
    assert load_env_file(tmp_path / "missing.env") is None
