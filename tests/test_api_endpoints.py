"""Flask endpoint integration tests using test_client."""

from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    import os
    import sys

    sys.path.insert(0, "src")
    os.environ.setdefault("FLASK_DEBUG", "false")

    from main import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Health & Config
# ---------------------------------------------------------------------------
def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"


def test_config_endpoint(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    data = r.get_json()
    assert "llm_providers" in data
    assert "configured_llm_providers" in data
    assert "tts_providers" in data
    assert "defaults" in data
    assert "video_settings_options" in data


def test_llm_models_endpoint(client):
    r = client.get("/api/llm/models?provider=ollama")
    assert r.status_code == 200
    data = r.get_json()
    assert "models" in data
    assert isinstance(data["models"], list)


def test_tts_voices_endpoint(client):
    r = client.get("/api/tts/voices?provider=elevenlabs")
    assert r.status_code == 200
    data = r.get_json()
    assert "voices" in data
    assert isinstance(data["voices"], list)


# ---------------------------------------------------------------------------
# Script utilities
# ---------------------------------------------------------------------------
def test_script_prompt_template(client):
    r = client.get("/api/script/prompt-template?topic=Algebra")
    assert r.status_code == 200
    data = r.get_json()
    assert "prompt" in data
    assert "Algebra" in data["prompt"]


def test_script_parse(client):
    r = client.post(
        "/api/script/parse",
        json={
            "import_script": "Scene 1: Intro\nNarration: Hello\nVisual: Title",
            "topic": "Math",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["scene_count"] >= 1
    assert "scenes" in data


def test_script_parse_empty(client):
    r = client.post("/api/script/parse", json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Providers health
# ---------------------------------------------------------------------------
@patch("main.check_providers")
def test_providers_health_get(mock_check, client):
    mock_check.return_value = {"ready": True, "llm": {}, "tts": None}
    r = client.get("/api/providers/health")
    assert r.status_code == 200
    mock_check.assert_called_once()


@patch("main.check_providers")
def test_providers_health_post(mock_check, client):
    mock_check.return_value = {"ready": False, "llm": {}, "tts": None}
    r = client.post("/api/providers/health", json={"llm_provider": "openai"})
    assert r.status_code == 200
    assert not r.get_json()["ready"]


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------
@patch("main.start_video_generation")
def test_generate_endpoint(mock_start, client):
    mock_start.return_value = "job-123"
    r = client.post(
        "/api/generate",
        json={
            "topic": "Test",
            "llm_provider": "ollama",
            "enable_tts": False,
            "video_settings": {"quality": "standard"},
        },
    )
    assert r.status_code == 202
    data = r.get_json()
    assert data["job_id"] == "job-123"
    assert data["status"] == "queued"
    mock_start.assert_called_once()


def test_generate_missing_topic(client):
    r = client.post("/api/generate", json={})
    assert r.status_code == 400
    assert "error" in r.get_json()


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
@patch("main.get_job_status")
def test_progress_endpoint(mock_status, client):
    mock_status.return_value = {"job_id": "j1", "status": "running", "progress": 50}
    r = client.get("/api/progress/j1")
    assert r.status_code == 200
    assert r.get_json()["status"] == "running"


@patch("main.get_job_status")
def test_progress_not_found(mock_status, client):
    mock_status.return_value = None
    r = client.get("/api/progress/missing")
    assert r.status_code == 404


@patch("main.list_jobs")
def test_list_jobs_endpoint(mock_list, client):
    mock_list.return_value = [{"job_id": "j1", "status": "completed"}]
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert len(r.get_json()["jobs"]) == 1


@patch("main.cancel_video_generation")
def test_cancel_job(mock_cancel, client):
    mock_cancel.return_value = None
    r = client.post("/api/jobs/j1/cancel")
    assert r.status_code == 200
    mock_cancel.assert_called_once_with("j1")


@patch("main.cancel_video_generation", side_effect=ValueError("not found"))
def test_cancel_job_not_found(mock_cancel, client):
    r = client.post("/api/jobs/j1/cancel")
    assert r.status_code == 400
    assert "not found" in r.get_json()["error"]


@patch("main.update_job_script")
def test_save_script(mock_update, client):
    mock_update.return_value = [{"text": "scene"}]
    r = client.put("/api/jobs/j1/script", json={"script": [{"text": "scene"}]})
    assert r.status_code == 200
    mock_update.assert_called_once_with("j1", [{"text": "scene"}])


def test_save_script_missing_body(client):
    r = client.put("/api/jobs/j1/script", json={})
    assert r.status_code == 400


@patch("main.continue_video_generation")
def test_continue_job(mock_continue, client):
    mock_continue.return_value = None
    r = client.post("/api/jobs/j1/continue", json={"script": [{"text": "x"}]})
    assert r.status_code == 200
    mock_continue.assert_called_once_with("j1", [{"text": "x"}])


@patch("main.resume_video_generation")
def test_resume_job(mock_resume, client):
    mock_resume.return_value = None
    r = client.post("/api/jobs/j1/resume")
    assert r.status_code == 200
    mock_resume.assert_called_once_with("j1")


@patch("main.retry_scene_render")
def test_retry_scene(mock_retry, client):
    mock_retry.return_value = None
    r = client.post("/api/jobs/j1/scenes/2/retry", json={"regen_code": True})
    assert r.status_code == 200
    mock_retry.assert_called_once_with("j1", 2, regen_code=True)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------
@patch("main.start_scene_preview")
def test_preview_scene(mock_preview, client):
    mock_preview.return_value = "preview-job-1"
    r = client.post(
        "/api/preview-scene",
        json={
            "topic": "Preview",
            "script": [{"text": "Hello", "animation": "Fade"}],
            "scene_index": 1,
            "enable_tts": False,
            "llm_provider": "ollama",
        },
    )
    assert r.status_code == 202
    assert r.get_json()["job_id"] == "preview-job-1"


def test_preview_scene_missing_script(client):
    r = client.post("/api/preview-scene", json={})
    assert r.status_code == 400
    assert "script" in r.get_json()["error"]


def test_preview_code_missing_fields(client):
    r = client.post("/api/preview-code", json={})
    assert r.status_code == 400
    assert "code" in r.get_json()["error"]


def test_preview_code_invalid_class_name(client):
    r = client.post("/api/preview-code", json={"code": "print(1)", "class_name": "123Bad"})
    assert r.status_code == 400
    assert "class name" in r.get_json()["error"].lower()


@patch("main.compile_video")
def test_preview_code_success(mock_compile, client):
    mock_compile.return_value = ("media/videos/preview_test/pql/MyScene.mp4", None)
    r = client.post(
        "/api/preview-code",
        json={"code": "from manim import *\nclass MyScene(Scene): pass", "class_name": "MyScene", "topic": "Test"},
    )
    assert r.status_code == 200
    assert r.get_json()["video_url"] == "media/videos/preview_test/pql/MyScene.mp4"
    mock_compile.assert_called_once()


@patch("main.compile_video")
def test_preview_code_compilation_error(mock_compile, client):
    mock_compile.return_value = (None, "Syntax error on line 3")
    r = client.post(
        "/api/preview-code",
        json={"code": "bad code", "class_name": "MyScene"},
    )
    assert r.status_code == 500
    assert "syntax error" in r.get_json()["error"].lower()


@patch("main.start_video_generation")
def test_batch_create(mock_start, client):
    mock_start.side_effect = ["job-1", "job-2"]
    r = client.post(
        "/api/batch",
        json={
            "items": [{"topic": "A"}, {"topic": "B"}],
            "llm_provider": "openai",
            "enable_tts": False,
        },
    )
    assert r.status_code == 202
    data = r.get_json()
    assert data["total"] == 2
    assert len(data["job_ids"]) == 2
    assert data["status"] == "running"


def test_batch_empty_items(client):
    r = client.post("/api/batch", json={"items": []})
    assert r.status_code == 400


def test_batch_get_not_found(client):
    r = client.get("/api/batch/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Static / root
# ---------------------------------------------------------------------------
def test_index_serves_html(client):
    r = client.get("/")
    # May 404 if frontend files missing, or 200 if present
    assert r.status_code in (200, 404)
