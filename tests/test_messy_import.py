"""Messy / real-world script import cases — auto-detect and format boundaries."""

from script_import import parse_import_script


def test_auto_detect_loose_scenes():
    raw = """Scene 1: Hook
Narration: Percent means out of 100.
Visual: Show a percent symbol.

Scene 2: Example
Narration: Ten percent is ten out of 100.
Visual: Display 10% = 10/100."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 2
    assert result["format"] in ("loose", "text")


def test_auto_detect_json_array():
    raw = '[{"text": "Hello.", "animation": "Title."}, {"text": "World.", "animation": "Chart."}]'
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 2
    assert result["format"] == "json"


def test_markdown_headings_auto():
    raw = """# Quadratic Functions

## What is a parabola?
A parabola is the graph of a quadratic function.

## Vertex form
The vertex form makes the turning point easy to read."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] >= 2
    assert result["title"] == "Quadratic Functions"


def test_plain_paragraphs_auto():
    raw = """Fractions represent parts of a whole.

To add fractions, use a common denominator.

Always simplify the final answer."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 3


def test_prose_then_fenced_json_auto():
    raw = """Here is the exported script:

```json
[
  {"text": "Intro narration.", "animation": "Title card"},
  {"text": "Main idea.", "animation": "Diagram"}
]
```
"""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 2
    assert result["format"] == "json"


def test_on_screen_label():
    raw = """Scene 1: Intro
Narration: We start with ratios.
On-screen: Show a ratio table with two columns."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 1
    assert "ratio" in result["scenes"][0]["animation"].lower()


def test_narration_only_gets_visual_fallback():
    raw = """Scene 1: Warm-up
Narration: Today we study linear equations."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 1
    assert result["scenes"][0]["animation"]
    assert any("visual" in w.lower() for w in result["warnings"])


def test_json_only_rejects_loose():
    raw = """Scene 1: Hook
Narration: Hello.
Visual: Title."""
    try:
        parse_import_script(raw, format_hint="json")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "json" in str(exc).lower() or "JSON" in str(exc)


def test_many_scenes_auto():
    lines = []
    for i in range(1, 26):
        lines.extend(
            [
                f"Scene {i}: Part {i}",
                f"Narration: Lesson segment {i} about algebra topic {i}.",
                f"Visual: Diagram for idea {i}.",
                "",
            ]
        )
    result = parse_import_script("\n".join(lines), format_hint="auto")
    assert result["scene_count"] == 25


def test_blank_lines_and_spacing():
    raw = """Scene 1:  Opening


Narration:   Spaced   narration   here.

Visual:   Title card.


Scene 2:Next

Narration:Second scene text.
Visual:Second visual."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] == 2
    assert "Spaced" in result["scenes"][0]["text"]


def test_bracket_visual_cues():
    raw = """Scene 1: Graph intro

[VISUAL: Axes with a line through the origin]

This line has slope two.

Scene 2: Summary
Narration: Slope measures steepness.
Visual: Highlight rise over run."""
    result = parse_import_script(raw, format_hint="auto")
    assert result["scene_count"] >= 2
    assert (
        "Axes" in result["scenes"][0]["animation"] or "slope" in result["scenes"][0]["text"].lower()
    )
