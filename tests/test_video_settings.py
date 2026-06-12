"""Tests for video_settings normalization and preset logic."""

from video_settings import (
    get_settings_options,
    normalize_video_settings,
    resolve_length_key,
)


# ---------------------------------------------------------------------------
# resolve_length_key
# ---------------------------------------------------------------------------
def test_resolve_length_key_exact():
    assert resolve_length_key("short") == "short"
    assert resolve_length_key("min_5") == "min_5"


def test_resolve_length_key_alias():
    assert resolve_length_key("long") == "min_2"
    assert resolve_length_key("lecture_10") == "min_10"


def test_resolve_length_key_unknown():
    assert resolve_length_key("nonsense") == "standard"


# ---------------------------------------------------------------------------
# normalize_video_settings
# ---------------------------------------------------------------------------
def test_normalize_defaults():
    result = normalize_video_settings()
    assert result["length"] == "standard"
    assert result["style"] == "balanced"
    assert result["quality"] == "standard"
    assert result["review_script"] is True
    assert "length_preset" in result
    assert "style_preset" in result
    assert "quality_preset" in result


def test_normalize_custom():
    result = normalize_video_settings(
        {"length": "min_5", "style": "technical", "quality": "high", "review_script": False}
    )
    assert result["length"] == "min_5"
    assert result["style"] == "technical"
    assert result["quality"] == "high"
    assert result["review_script"] is False


def test_normalize_invalid_style_fallback():
    result = normalize_video_settings({"style": "fancy"})
    assert result["style"] == "balanced"


def test_normalize_invalid_quality_fallback():
    result = normalize_video_settings({"quality": "8k"})
    assert result["quality"] == "standard"


def test_normalize_legacy_keys():
    result = normalize_video_settings({"video_length": "short", "video_style": "beginner"})
    assert result["length"] == "short"
    assert result["style"] == "beginner"


def test_normalize_review_script_default_true():
    result = normalize_video_settings({})
    assert result["review_script"] is True


def test_normalize_review_script_explicit_false():
    result = normalize_video_settings({"review_script": False})
    assert result["review_script"] is False


# ---------------------------------------------------------------------------
# get_settings_options
# ---------------------------------------------------------------------------
def test_get_settings_options_structure():
    opts = get_settings_options()
    assert "lengths" in opts
    assert "length_groups" in opts
    assert "styles" in opts
    assert "qualities" in opts


def test_get_settings_options_lengths():
    opts = get_settings_options()
    ids = {e["id"] for e in opts["lengths"]}
    assert "short" in ids
    assert "min_5" in ids


def test_get_settings_options_styles():
    opts = get_settings_options()
    ids = {e["id"] for e in opts["styles"]}
    assert "balanced" in ids
    assert "beginner" in ids
    assert "technical" in ids


def test_get_settings_options_qualities():
    opts = get_settings_options()
    ids = {e["id"] for e in opts["qualities"]}
    assert "preview" in ids
    assert "standard" in ids
    assert "high" in ids
