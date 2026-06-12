"""Tests for env_loader path resolution."""

import os
from unittest.mock import patch

from env_loader import ENV_EXAMPLE_PATH, ENV_PATH, ensure_env_file, get_env, load_app_env


def test_env_path_exists():
    """env_loader looks for .env next to project root."""
    from env_loader import ENV_PATH

    assert ENV_PATH.name == ".env"


def test_load_app_env_runs_without_error():
    load_app_env()  # should not raise


def test_get_env_reads_existing():
    with patch.dict(os.environ, {"TEST_VAR_12345": "hello"}, clear=False):
        assert get_env("TEST_VAR_12345") == "hello"


def test_get_env_default():
    assert get_env("NONEXISTENT_VAR_XYZ", "fallback") == "fallback"


def test_get_env_none_default():
    assert get_env("NONEXISTENT_VAR_XYZ") is None


def test_ensure_env_file_creates_from_example(tmp_path, monkeypatch):
    example = tmp_path / ".env.example"
    example.write_text("FOO=bar\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    monkeypatch.setattr("env_loader.ENV_PATH", env_file)
    monkeypatch.setattr("env_loader.ENV_EXAMPLE_PATH", example)

    assert ensure_env_file() is True
    assert env_file.read_text(encoding="utf-8") == "FOO=bar\n"
    assert ensure_env_file() is False
