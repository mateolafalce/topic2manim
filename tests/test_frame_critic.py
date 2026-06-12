"""Tests for frame_critic env parsing and vision critique logic."""

import os
from unittest.mock import MagicMock, patch


from frame_critic import (
    build_critic_fix_prompt,
    critic_max_retries,
    critic_min_score,
    is_critic_enabled,
    critique_scene_frames,
)


# ---------------------------------------------------------------------------
# Env parsing
# ---------------------------------------------------------------------------
@patch.dict(os.environ, {"ENABLE_FRAME_CRITIC": ""}, clear=True)
def test_critic_enabled_default():
    assert is_critic_enabled() is True


@patch.dict(os.environ, {"ENABLE_FRAME_CRITIC": "false"})
def test_critic_enabled_false():
    assert is_critic_enabled() is False


@patch.dict(os.environ, {"ENABLE_FRAME_CRITIC": "0"})
def test_critic_enabled_zero():
    assert is_critic_enabled() is False


@patch.dict(os.environ, {"ENABLE_FRAME_CRITIC": "no"})
def test_critic_enabled_no():
    assert is_critic_enabled() is False


@patch.dict(os.environ, {}, clear=True)
def test_critic_min_score_default():
    assert critic_min_score() == 8.0


@patch.dict(os.environ, {"CRITIC_MIN_SCORE": "7.5"})
def test_critic_min_score_override():
    assert critic_min_score() == 7.5


@patch.dict(os.environ, {"CRITIC_MIN_SCORE": "bad"})
def test_critic_min_score_invalid():
    assert critic_min_score() == 8.0


@patch.dict(os.environ, {}, clear=True)
def test_critic_max_retries_default():
    assert critic_max_retries() == 2


@patch.dict(os.environ, {"CRITIC_MAX_RETRIES": "5"})
def test_critic_max_retries_override():
    assert critic_max_retries() == 5


# ---------------------------------------------------------------------------
# critique_scene_frames
# ---------------------------------------------------------------------------
def test_critique_no_frames_skips():
    result = critique_scene_frames(MagicMock(), "openai", "gpt-4o", [], "narration", "animation")
    assert result["skipped"] is True
    assert result["ok"] is True
    assert result["score"] == 10


@patch("frame_critic.complete_llm_vision")
@patch("frame_critic._encode_image")
def test_critique_success(mock_encode, mock_vision):
    mock_encode.return_value = "b64img"
    mock_vision.return_value = '{"score": 8, "issues": [], "suggestions": "", "ok": true}'
    with patch("frame_critic.format_events_for_prompt", return_value=""):
        result = critique_scene_frames(
            MagicMock(), "openai", "gpt-4o", ["/tmp/fake.jpg"], "narration", "animation"
        )
    assert result["ok"] is True
    assert result["score"] == 8.0
    assert result["skipped"] is False


@patch("frame_critic.complete_llm_vision")
@patch("frame_critic._encode_image")
def test_critique_exception_fallback(mock_encode, mock_vision):
    mock_encode.return_value = "b64img"
    mock_vision.side_effect = ValueError("bad response")
    with patch("frame_critic.format_events_for_prompt", return_value=""):
        result = critique_scene_frames(
            MagicMock(), "openai", "gpt-4o", ["/tmp/fake.jpg"], "narration", "animation"
        )
    assert result["skipped"] is True
    assert result["ok"] is True
    assert "error" in result


# ---------------------------------------------------------------------------
# build_critic_fix_prompt
# ---------------------------------------------------------------------------
def test_build_critic_fix_prompt_contains_issues():
    prompt = build_critic_fix_prompt(
        "code", {"issues": ["wrong color"], "suggestions": "use blue"}, "hello"
    )
    assert "wrong color" in prompt
    assert "use blue" in prompt
    assert "hello" in prompt
    assert "code" in prompt
