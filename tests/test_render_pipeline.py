"""Tests for render_pipeline checkpointing, cancellation, and scene compilation."""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest

from render_pipeline import (
    empty_checkpoint,
    ensure_not_cancelled,
    is_job_cancelled,
    load_checkpoint,
    parallel_workers,
    save_checkpoint_to_job,
    _compile_with_repl,
    _build_context_from_checkpoint,
)


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------
def test_is_job_cancelled_without_lock():
    jobs = {"j1": {"cancel_requested": True}}
    assert is_job_cancelled(jobs, "j1") is True
    assert is_job_cancelled(jobs, "j2") is False


def test_is_job_cancelled_with_lock():
    jobs = {"j1": {"cancel_requested": True}}
    lock = threading.RLock()
    assert is_job_cancelled(jobs, "j1", lock) is True


def test_ensure_not_cancelled_raises():
    jobs = {"j1": {"cancel_requested": True}}
    from render_pipeline import JobCancelledError

    with pytest.raises(JobCancelledError):
        ensure_not_cancelled(jobs, "j1")


def test_ensure_not_cancelled_ok():
    jobs = {"j1": {"cancel_requested": False}}

    ensure_not_cancelled(jobs, "j1")  # should not raise


# ---------------------------------------------------------------------------
# parallel_workers
# ---------------------------------------------------------------------------
def test_parallel_workers_default():
    assert parallel_workers() == 2


@patch.dict(os.environ, {"RENDER_PARALLEL_WORKERS": "4"})
def test_parallel_workers_env():
    assert parallel_workers() == 4


@patch.dict(os.environ, {"RENDER_PARALLEL_WORKERS": "bad"})
def test_parallel_workers_invalid_env():
    assert parallel_workers() == 2


@patch.dict(os.environ, {"RENDER_PARALLEL_WORKERS": "10"})
def test_parallel_workers_capped():
    assert parallel_workers() == 6


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------
def test_empty_checkpoint():
    ck = empty_checkpoint()
    assert ck["audio_path"] is None
    assert ck["audio_durations"] == {}
    assert ck["scene_codes"] == {}
    assert ck["scene_videos"] == {}


def test_load_checkpoint_empty_job():
    assert load_checkpoint({}) == empty_checkpoint()


def test_load_checkpoint_existing():
    ck = {"audio_path": "a.mp3", "scene_codes": {"1": {}}}
    loaded = load_checkpoint({"render_checkpoint": ck})
    assert loaded["audio_path"] == "a.mp3"


def test_load_checkpoint_adds_style_registry():
    loaded = load_checkpoint({"render_checkpoint": {"audio_path": None}})
    assert "style_registry" in loaded


def test_save_checkpoint_to_job():
    jobs = {"j1": {}}
    persist_calls = []

    def fake_persist(jid, chk):
        persist_calls.append((jid, chk))

    ck = {"scene_codes": {"1": "code"}}
    save_checkpoint_to_job(jobs, "j1", ck, fake_persist)
    assert jobs["j1"]["render_checkpoint"] == ck
    assert persist_calls == [("j1", ck)]


def test_save_checkpoint_to_job_with_lock():
    jobs = {"j1": {}}
    lock = threading.RLock()
    save_checkpoint_to_job(jobs, "j1", {"x": 1}, lambda j, c: None, lock)
    assert jobs["j1"]["render_checkpoint"]["x"] == 1


# ---------------------------------------------------------------------------
# _compile_with_repl
# ---------------------------------------------------------------------------
@patch("render_pipeline.os.path.exists", return_value=True)
@patch("render_pipeline.compile_video")
def test_compile_with_repl_success_first_try(mock_compile, mock_exists):
    mock_compile.return_value = ("media/vid.mp4", None)
    path, code, cls = _compile_with_repl(
        MagicMock(), "openai", "gpt-4o", "/tmp/test.py", "code", "Scene1", "topic", 1, "standard"
    )
    assert path == "media/vid.mp4"
    assert code == "code"
    assert cls == "Scene1"
    mock_compile.assert_called_once()


@patch("render_pipeline.os.path.exists", return_value=True)
@patch("render_pipeline.compile_video")
@patch("render_pipeline.fix_manim_code")
def test_compile_with_repl_fix_on_second_try(mock_fix, mock_compile, mock_exists):
    mock_compile.side_effect = [
        (None, "syntax error"),
        ("media/vid.mp4", None),
    ]
    mock_fix.return_value = {"content": "fixed_code", "class_name": "Scene1Fixed"}
    path, code, cls = _compile_with_repl(
        MagicMock(), "openai", "gpt-4o", "/tmp/test.py", "code", "Scene1", "topic", 1, "standard"
    )
    assert path == "media/vid.mp4"
    assert code == "fixed_code"
    assert cls == "Scene1Fixed"
    assert mock_compile.call_count == 2


@patch("render_pipeline.compile_video")
@patch("render_pipeline.fix_manim_code")
def test_compile_with_repl_gives_up(mock_fix, mock_compile):
    mock_compile.return_value = (None, "syntax error")
    mock_fix.return_value = None
    path, code, cls = _compile_with_repl(
        MagicMock(), "openai", "gpt-4o", "/tmp/test.py", "code", "Scene1", "topic", 1, "standard"
    )
    assert path is None
    assert mock_fix.call_count == 1  # only tries once (max_repl=3, stops when fix returns None)


# ---------------------------------------------------------------------------
# _build_context_from_checkpoint
# ---------------------------------------------------------------------------
def test_build_context_from_checkpoint():
    scene = {"text": "hello", "animation": "fade", "chapter": "ch1"}
    ctx = _build_context_from_checkpoint(scene, "print('hi')")
    assert ctx["text"] == "hello"
    assert ctx["code"] == "print('hi')"
    assert ctx["chapter"] == "ch1"


def test_build_context_from_checkpoint_dict_code():
    scene = {"text": "hello"}
    ctx = _build_context_from_checkpoint(scene, {"content": "code"})
    assert ctx["code"] == "code"


# ---------------------------------------------------------------------------
# generate_scene_code custom code path
# ---------------------------------------------------------------------------
@patch("render_pipeline.generate_manim_code")
def test_generate_scene_code_uses_custom_code(mock_generate_manim_code):
    from render_pipeline import generate_scene_code

    scene_data = {
        "text": "hello",
        "animation": "fade",
        "code": "from manim import *\nclass CustomScene(Scene): pass",
        "code_class": "CustomScene",
    }
    result = generate_scene_code(
        llm_client=None,
        provider="openai",
        model="gpt-4o",
        scene_data=scene_data,
        index=1,
        style_registry={},
        previous_context=None,
        audio_duration=10,
        video_settings={},
    )
    assert result["content"] == scene_data["code"]
    assert result["class_name"] == scene_data["code_class"]
    mock_generate_manim_code.assert_not_called()


@patch("render_pipeline.generate_manim_code")
def test_generate_scene_code_falls_back_to_llm(mock_generate_manim_code):
    from render_pipeline import generate_scene_code

    mock_generate_manim_code.return_value = {"content": "generated", "class_name": "GeneratedScene"}
    scene_data = {"text": "hello", "animation": "fade"}
    result = generate_scene_code(
        llm_client=MagicMock(),
        provider="openai",
        model="gpt-4o",
        scene_data=scene_data,
        index=1,
        style_registry={},
        previous_context=None,
        audio_duration=10,
        video_settings={},
    )
    assert result["content"] == "generated"
    assert result["class_name"] == "GeneratedScene"
    mock_generate_manim_code.assert_called_once()
