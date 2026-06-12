"""Tests for flexible script import parsing."""

from script_import import parse_import_script


def test_markdown_chapters():
    md = """# How Pi Works

## Introduction

Pi is the ratio of a circle circumference to its diameter.

## The Formula

### Area of a circle
The area equals pi times r squared.

### Circumference
The circumference equals two pi r.
"""
    result = parse_import_script(md)
    assert result["scene_count"] >= 3
    assert result["title"] == "How Pi Works"


def test_clipmaster_style():
    raw = """TITLE: Gradient Descent
TARGET RUNTIME: 5:00

---

# Introduction

## [0:00-0:45] Hook

[VISUAL: Parabola on axes with a ball rolling down]

We want to find the lowest point on this curve.

---

# Main Idea

## [0:45-2:00] The Update Rule

Move opposite the gradient, scaled by the learning rate.
"""
    result = parse_import_script(raw)
    assert result["scene_count"] >= 2
    assert result["title"] == "Gradient Descent"
    assert any("[VISUAL" not in s["text"] for s in result["scenes"])
    assert any(
        "Parabola" in s.get("animation", "") or "parabola" in s.get("animation", "").lower()
        for s in result["scenes"]
    )


def test_labeled_fields():
    raw = """Scene 1: Opening

Narration: The derivative measures instantaneous rate of change.
Animation: Plot f(x), then show secant lines shrinking to a tangent.

Scene 2: Example

Voiceover: For x squared, the derivative is two x.
Visual: Display x^2 and highlight slope at several points.
"""
    result = parse_import_script(raw)
    assert result["scene_count"] == 2
    assert "secant" in result["scenes"][0]["animation"].lower()
    assert (
        "x squared" in result["scenes"][1]["text"].lower() or "x^2" in result["scenes"][1]["text"]
    )


def test_json_chapters():
    raw = """{
      "title": "Linear Algebra",
      "chapters": [
        {"title": "Vectors", "scenes": [
          {"text": "A vector has magnitude and direction.", "animation": "Show arrow"},
          {"text": "We add vectors tip to tail.", "animation": "Vector addition"}
        ]}
      ]
    }"""
    result = parse_import_script(raw)
    assert result["scene_count"] == 2
    assert result["title"] == "Linear Algebra"


def test_json_in_markdown_fence():
    raw = """Here is the script:

```json
[
  {"text": "First scene narration.", "animation": "Title card"},
  {"text": "Second scene narration.", "animation": "Diagram"}
]
```
"""
    result = parse_import_script(raw)
    assert result["scene_count"] == 2
    assert result["format"] == "json"


def test_plain_paragraphs():
    raw = """Pi is the ratio of a circle's circumference to its diameter.

The area of a circle is pi r squared.

Euler's formula connects pi, e, and i in a beautiful way.
"""
    result = parse_import_script(raw)
    assert result["scene_count"] == 3


def test_step_headers():
    raw = """**Step 1:** Define the function

We start with f(x) = x squared.

**Step 2:** Differentiate

The derivative is 2x.
"""
    result = parse_import_script(raw)
    assert result["scene_count"] == 2
