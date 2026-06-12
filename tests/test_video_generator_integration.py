"""Integration tests for video_generator workflow with mocked LLM/TTS/render."""

from unittest.mock import MagicMock, patch

import pytest

from video_generator import (
    cancel_video_generation,
    continue_video_generation,
    generate_video_workflow,
    get_job_status,
    start_video_generation,
    update_job_script,
)


import time


@pytest.fixture(autouse=True)
def clean_jobs():
    """Clear in-memory jobs dict and cancel lingering threads before each test."""
    from video_generator import jobs, jobs_lock

    def _drain():
        with jobs_lock:
            for job in list(jobs.values()):
                job["cancel_requested"] = True
        from video_generator import _job_threads

        for jid, thread in list(_job_threads.items()):
            if thread.is_alive():
                thread.join(timeout=0.5)
        _job_threads.clear()
        jobs.clear()

    _drain()
    yield
    _drain()


def test_start_video_generation_creates_job():
    job_id = start_video_generation(
        topic="Test Topic",
        enable_tts=False,
        llm_provider="openai",
        video_settings={"quality": "standard"},
    )
    assert job_id is not None
    status = get_job_status(job_id)
    # Race: thread may already have switched status to "running"
    assert status["status"] in ("queued", "running")
    assert status["topic"] == "Test Topic"


def test_cancel_video_generation():
    job_id = start_video_generation(
        topic="Cancel Test",
        enable_tts=False,
        llm_provider="openai",
    )
    cancel_video_generation(job_id)
    status = get_job_status(job_id)
    assert status["status"] == "cancelled"
    assert status["cancel_requested"] is True


def test_cancel_nonexistent_job_raises():
    with pytest.raises(ValueError, match="Job not found"):
        cancel_video_generation("nonexistent-job-id")


def test_update_job_script():
    job_id = start_video_generation(
        topic="Script Test",
        enable_tts=False,
        llm_provider="openai",
    )
    # Simulate job reaching review state
    from video_generator import jobs

    jobs[job_id]["status"] = "awaiting_review"

    new_script = [
        {"text": "Scene 1", "animation": "Title card"},
        {"text": "Scene 2", "animation": "Diagram"},
    ]
    result = update_job_script(job_id, new_script)
    assert len(result) == 2
    assert result[0]["text"] == "Scene 1"


def test_update_job_script_not_reviewable():
    job_id = start_video_generation(
        topic="Script Test",
        enable_tts=False,
        llm_provider="openai",
    )
    with pytest.raises(ValueError, match="not awaiting script review"):
        update_job_script(job_id, [])


@patch("video_generator.concatenate_videos")
@patch("video_generator.merge_video_and_audio")
@patch("video_generator.render_scenes_with_pipeline")
@patch("video_generator.generate_complete_audio")
@patch("video_generator.generate_script_json")
@patch("video_generator.setup_llm_client")
def test_generate_video_workflow_success(
    mock_setup_llm,
    mock_generate_script,
    mock_generate_audio,
    mock_render_pipeline,
    mock_merge,
    mock_concat,
):
    """End-to-end happy path for video generation with all dependencies mocked."""
    mock_setup_llm.return_value = {
        "client": MagicMock(),
        "provider": "openai",
        "model": "gpt-4o",
    }
    mock_generate_script.return_value = (
        [
            {"text": "Scene 1", "animation": "Title"},
            {"text": "Scene 2", "animation": "Diagram"},
        ],
        None,
    )
    mock_generate_audio.return_value = ("media/audio_test.mp3", {1: 12.0, 2: 15.0})
    mock_render_pipeline.return_value = [
        "media/videos/scene1.mp4",
        "media/videos/scene2.mp4",
    ]
    mock_concat.return_value = True
    mock_merge.return_value = True

    job_id = "test-job-123"
    from video_generator import jobs

    jobs[job_id] = {
        "job_id": job_id,
        "topic": "Integration Test",
        "status": "queued",
        "llm_provider": "openai",
        "video_settings": {"quality": "standard"},
    }

    generate_video_workflow(
        job_id=job_id,
        topic="Integration Test",
        enable_tts=True,
        llm_provider="openai",
        tts_provider="openai",
        llm_model="gpt-4o",
        video_settings={"quality": "standard"},
        tts_voice="alloy",
        input_mode="topic",
    )

    status = get_job_status(job_id)
    assert status["status"] == "completed"
    assert status["progress"] == 100
    assert status["scenes_total"] == 2
    assert status["video_url"] is not None

    mock_setup_llm.assert_called_once_with("openai", "gpt-4o")
    mock_generate_script.assert_called_once()
    mock_generate_audio.assert_called_once()
    mock_render_pipeline.assert_called_once()
    mock_concat.assert_called_once()
    mock_merge.assert_called_once()


@patch("video_generator.setup_llm_client")
def test_generate_video_workflow_script_failure(mock_setup_llm):
    """Verify job is marked failed when script generation fails."""
    mock_setup_llm.return_value = {
        "client": MagicMock(),
        "provider": "openai",
        "model": "gpt-4o",
    }

    job_id = "test-job-fail"
    from video_generator import jobs

    jobs[job_id] = {
        "job_id": job_id,
        "topic": "Fail Test",
        "status": "queued",
        "llm_provider": "openai",
    }

    with patch(
        "video_generator.generate_script_json",
        return_value=(None, "LLM refused"),
    ):
        generate_video_workflow(
            job_id=job_id,
            topic="Fail Test",
            enable_tts=False,
            llm_provider="openai",
        )

    status = get_job_status(job_id)
    assert status["status"] == "failed"
    assert "LLM refused" in status["error"] or "Could not generate" in status["message"]


@patch("video_generator.setup_llm_client")
def test_continue_video_generation_starts_worker(mock_setup_llm):
    """continue_video_generation should spawn a background thread."""
    mock_setup_llm.return_value = {
        "client": MagicMock(),
        "provider": "openai",
        "model": "gpt-4o",
    }

    job_id = "test-continue"
    from video_generator import jobs

    jobs[job_id] = {
        "job_id": job_id,
        "topic": "Continue Test",
        "status": "awaiting_review",
        "script": [{"text": "Scene 1", "animation": "Title"}],
        "enable_tts": False,
        "llm_provider": "openai",
        "video_settings": {"quality": "standard"},
    }

    with patch("video_generator.render_scenes_with_pipeline", return_value=[]):
        with patch("video_generator.concatenate_videos", return_value=True):
            with patch("video_generator.merge_video_and_audio", return_value=True):
                continue_video_generation(job_id)

    # Give the thread a moment to start

    time.sleep(0.2)

    status = get_job_status(job_id)
    # After continue, status should be running or completed depending on thread speed
    assert status["status"] in ("running", "completed", "failed")
