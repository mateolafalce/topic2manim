"""Tests for path traversal protections in subprocess calls."""

import os
import tempfile
from pathlib import Path

import pytest

from concat_video import (
    _safe_project_path,
    compile_video,
    concatenate_videos,
    merge_video_and_audio,
)
from tts_generator import _safe_project_path as tts_safe_path
from frame_critic import _safe_project_path as fc_safe_path, extract_video_frames


# ---------------------------------------------------------------------------
# _safe_project_path (concat_video)
# ---------------------------------------------------------------------------
def test_safe_path_allows_project_subpath():
    path = str(Path(__file__).parent.parent / "media" / "test.mp4")
    assert _safe_project_path(path, "video") == str(Path(path).resolve())


def test_safe_path_rejects_traversal():
    with pytest.raises(ValueError, match="inside project directory"):
        _safe_project_path("../../etc/passwd")


def test_safe_path_rejects_absolute_outside():
    with pytest.raises(ValueError, match="inside project directory"):
        _safe_project_path("/etc/passwd")


def test_safe_path_rejects_null_bytes():
    with pytest.raises(ValueError, match="null bytes"):
        _safe_project_path("media/test\x00.mp4")


def test_safe_path_rejects_empty():
    with pytest.raises(ValueError, match="non-empty string"):
        _safe_project_path("")


# ---------------------------------------------------------------------------
# compile_video path validation
# ---------------------------------------------------------------------------
def test_compile_video_rejects_traversal_path():
    path, err = compile_video("../../etc/passwd", "Scene1", "topic", 1)
    assert path is None
    assert "Invalid" in err


# ---------------------------------------------------------------------------
# concatenate_videos path validation
# ---------------------------------------------------------------------------
def test_concatenate_videos_rejects_traversal():
    result = concatenate_videos(["../../etc/passwd"], "out.mp4")
    assert result is False


# ---------------------------------------------------------------------------
# merge_video_and_audio path validation
# ---------------------------------------------------------------------------
def test_merge_rejects_traversal_video():
    result = merge_video_and_audio("../../secret.mp4", "audio.mp3", "out.mp4")
    assert result is False


def test_merge_rejects_traversal_audio():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mp4", delete=False) as vf:
        vf.write("x")
        vid = vf.name
    try:
        result = merge_video_and_audio(vid, "../../secret.mp3", "out.mp4")
        assert result is False
    finally:
        os.remove(vid)


def test_merge_rejects_traversal_output():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mp4", delete=False) as vf:
        vf.write("x")
        vid = vf.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mp3", delete=False) as af:
        af.write("x")
        aud = af.name
    try:
        result = merge_video_and_audio(vid, aud, "../../secret.mp4")
        assert result is False
    finally:
        os.remove(vid)
        os.remove(aud)


# ---------------------------------------------------------------------------
# tts_generator path validation
# ---------------------------------------------------------------------------
def test_tts_safe_path_rejects_traversal():
    with pytest.raises(ValueError, match="inside project directory"):
        tts_safe_path("../../secret.mp3")


# ---------------------------------------------------------------------------
# frame_critic path validation
# ---------------------------------------------------------------------------
def test_fc_safe_path_rejects_traversal():
    with pytest.raises(ValueError, match="inside project directory"):
        fc_safe_path("../../secret.mp4")


def test_extract_frames_rejects_traversal():
    frames = extract_video_frames("../../secret.mp4")
    assert frames == []
