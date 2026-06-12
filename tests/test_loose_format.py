"""Tests for loose scene format import (user acceptance cases)."""

from script_import import parse_import_script


def test_strict_json():
    raw = """[
      {"text": "First scene.", "animation": "Title card"},
      {"text": "Second scene.", "animation": "Diagram"}
    ]"""
    result = parse_import_script(raw, format_hint="json")
    assert result["scene_count"] == 2
    assert result["format"] == "json"


def test_loose_scene_script():
    raw = """Scene 1: Opening Hook
Narration: If you struggle with percentages in CSEC Math Paper 1, this lesson will make things easier.
Visual: Show title: CSEC Math Percentages.

Scene 2: Meaning of Percent
Narration: Percent means out of 100.
Visual: Show Percent = out of 100."""
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] == 2
    assert result["scenes"][0].get("title") == "Opening Hook"
    assert "percentages" in result["scenes"][0]["text"].lower()
    assert (
        "CSEC" in result["scenes"][0]["animation"]
        or "Percentages" in result["scenes"][0]["animation"]
    )


def test_alternative_labels():
    raw = """Scene 1: Opening
Voiceover: Today we are learning 10 percent.
Animation: Show 10% = 1/10."""
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] == 1
    assert "10 percent" in result["scenes"][0]["text"]
    assert "10%" in result["scenes"][0]["animation"]


def test_missing_visual_fallback():
    raw = """Scene 1: Opening
Narration: Today we are learning percentages."""
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] == 1
    anim = result["scenes"][0]["animation"]
    assert "Opening" in anim or "percentages" in anim.lower()
    assert any("visual" in w.lower() or "auto-generated" in w.lower() for w in result["warnings"])


def test_missing_narration_warning():
    raw = """Scene 1: Silent Intro
Visual: Show a title card only."""
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] >= 1
    assert any("narration" in w.lower() for w in result["warnings"])


def test_json_in_loose_mode():
    raw = '[{"text": "A", "animation": "B"}, {"text": "C", "animation": "D"}]'
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] == 2
    assert result["format"] == "json"


def test_loose_many_scenes():
    lines = []
    for i in range(1, 26):
        lines.append(f"Scene {i}: Part {i}")
        lines.append(f"Narration: This is narration for scene {i} about math topic {i}.")
        lines.append(f"Visual: Show diagram for concept {i}.")
        lines.append("")
    raw = "\n".join(lines)
    result = parse_import_script(raw, format_hint="loose")
    assert result["scene_count"] == 25


def test_visual_fallback_helper():
    from script_import import _visual_fallback

    fb = _visual_fallback("Intro", "Learn about fractions today.")
    assert "Intro" in fb
    assert "fractions" in fb
