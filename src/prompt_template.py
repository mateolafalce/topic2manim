"""Copy-paste prompt templates for ChatGPT / Claude script generation."""

from video_settings import normalize_video_settings
from visual_events import VISUAL_EVENT_CATALOG

LOOSE_FORMAT_EXAMPLE = """Scene 1: Opening Hook
Narration: Brief hook that explains why this topic matters (2-3 sentences max).
Visual: Describe what appears on screen — title card, diagram, equation, etc.

Scene 2: Core Concept
Narration: Explain the main idea in plain language.
Visual: Show the key visual for this idea (graph, formula, worked setup).

Scene 3: Worked Example
Narration: Walk through one clear example step by step.
Visual: Animate the example in sync with the narration.

Scene 4: Summary
Narration: Recap the takeaway in one or two sentences.
Visual: Show a summary slide with the key formula or idea highlighted."""


def build_external_script_prompt(
    topic: str = "",
    length: str = "standard",
    style: str = "balanced",
    output_format: str = "loose",
) -> str:
    """Prompt users can paste into ChatGPT or Claude to generate import-ready scripts."""
    video_settings = normalize_video_settings({"length": length, "style": style})
    length_preset = video_settings["length_preset"]
    style_preset = video_settings["style_preset"]
    scene_count = length_preset["scene_count"]
    events_sample = ", ".join(list(VISUAL_EVENT_CATALOG.keys())[:8])

    topic_line = topic.strip() or "[YOUR TOPIC HERE]"

    loose_block = f"""
PREFERRED OUTPUT FORMAT — Loose Scene Format (paste directly into Topic2Manim Import Script):

Scene 1: Opening Hook
Narration: ...
Visual: ...

Scene 2: ...
Narration: ...
Visual: ...

Rules for this format:
- Start each scene with `Scene N: Title` (number and title required)
- Use `Narration:` for voice-over text (also accepts Voiceover:)
- Use `Visual:` for on-screen animation notes (also accepts Animation: or On-screen:)
- One blank line between scenes is fine
- Create exactly {scene_count} scenes (acceptable range: {max(scene_count - 2, 4)}–{scene_count + 2})
- Each Narration: max {length_preset['max_sentences']} short sentences (~{length_preset['scene_duration_sec']}s spoken)
- Each Visual: specific Manim-friendly description (no Python code)
- Scene 1 = intro/hook; final scene = summary/takeaway
- Scenes must build logically — scene N should follow from scene N-1
- Match the language of the topic exactly

Example skeleton:
{LOOSE_FORMAT_EXAMPLE}
"""

    json_block = ""
    if output_format == "json":
        json_block = f"""
Alternative: JSON array (for automation pipelines):
```json
[
  {{
    "chapter": "Introduction",
    "title": "What is the topic",
    "text": "Narration the voice-over will speak.",
    "animation": "Detailed Manim animation description.",
    "visual_events": ["show_title", "show_axes"]
  }}
]
```
Use `text` for narration and `animation` for visuals. Optional: chapter, title, visual_events ({events_sample}, etc.).
"""

    return f"""Write an educational math video script for Topic2Manim (a Manim animation video generator).

TOPIC: {topic_line}

AUDIENCE: {style_preset['audience']}
TONE: {style_preset['tone']}
TARGET LENGTH: ~{length_preset['duration_sec']} seconds ({scene_count} scenes, ~{length_preset['scene_duration_sec']}s narration each)

VISUAL STYLE (apply to every scene):
{style_preset['visual_style']}

REQUIREMENTS:
1. Create exactly {scene_count} scenes
2. Every scene MUST have both Narration and Visual content
3. Use LaTeX-style math in narration where helpful (e.g. $f(x) = x^2$)
4. Keep visuals simple and implementable in Manim Community Edition
5. Do NOT output Python code — description only
{loose_block}
{json_block}
Output the complete script now using the Loose Scene Format shown above."""
