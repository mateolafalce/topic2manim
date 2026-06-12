"""Narrative arc planner for educational video scripts.

Generates a structured pedagogical plan before any scene script is written.
The plan informs the LLM about the hook, aha moment, pacing, and visual
metaphors so the final script and animation have narrative coherence.
"""

import json
from typing import Any, Dict, List, Optional

from llm_chat import complete_llm


NARRATIVE_PROMPT = """You are a narrative architect for educational explainer videos in the style of 3Blue1Brown, Veritasium, and Kurzgesagt.

Your job is to design the narrative arc for a video about:
TOPIC: {topic}

Target audience: {audience}
Desired length: {length}

## Output Format (JSON)

Return a JSON object with these fields:

- "title": A compelling, curiosity-driven title (not dry or academic)
- "hook": One sentence that opens a curiosity gap. Avoid "Today we will learn about..." 
- "misconception": The wrong intuition most viewers have about this topic
- "aha_moment": The single insight that makes everything click. Describe it in plain language.
- "emotional_arc": One of ["wonder", "tension-release", "mystery-solved", "paradox-resolved", "scale-awe"]
- "scene_beats": Array of 3-8 scene objects, each with:
  - "scene_number": integer
  - "purpose": One of ["hook", "setup", "build_tension", "reveal", "elaborate", "connect", "payoff", "closing"]
  - "narration_summary": 1-2 sentences of what the narrator says
  - "visual_approach": How to visualize this (geometric, algorithmic, data-driven, analogy, etc.)
  - "estimated_seconds": approximate duration
  - "key_visual": The single most important visual element in this scene
  - "pause_after": true if this scene should have extra breathing room after it
- "visual_metaphors": Object mapping abstract concepts to concrete visual analogies
- "color_theme": One of ["classic_3b1b", "warm_academic", "neon_tech", "monochrome", "earth"]
- "estimated_total_seconds": sum of scene beats
- "pacing_notes": Any special timing instructions (e.g., "slow down for the proof", "fast montage for examples")

## Narrative Principles

1. **Hook before math**: The first scene must pose a question, paradox, or mystery—not a definition.
2. **Geometry before algebra**: Visual intuition comes before formulas.
3. **One aha moment**: Every video has a single insight. Everything else is scaffolding.
4. **Show wrong paths**: Briefly show an intuitive but wrong approach before the correct one.
5. **Real-world anchor**: Connect to something the viewer already cares about.
6. **Breathing room**: The aha-moment scene needs 2-3x the pause of a normal scene.

## Example Output Structure

```json
{{
  "title": "The Counterintuitive Truth About Random Walks",
  "hook": "If you keep flipping a coin and moving left or right, how far will you really get?",
  "misconception": "People expect the distance to grow linearly with steps.",
  "aha_moment": "The distance grows like the square root of steps—not linearly. That's why drunk people don't get far.",
  "emotional_arc": "paradox-resolved",
  "scene_beats": [
    {{
      "scene_number": 1,
      "purpose": "hook",
      "narration_summary": "Pose the drunkard's walk paradox with a dot wandering on a line.",
      "visual_approach": "Animated dot moving randomly; counter keeps climbing.",
      "estimated_seconds": 15,
      "key_visual": "Wandering dot with step counter",
      "pause_after": true
    }}
  ],
  "visual_metaphors": {{
    "random_walk": "A drunk person staggering on a sidewalk",
    "square_root_growth": "A spiral that tightens as it expands"
  }},
  "color_theme": "classic_3b1b",
  "estimated_total_seconds": 120,
  "pacing_notes": "Slow down during the proof; speed up for examples."
}}
```

Respond with ONLY the JSON object. No markdown fences, no extra commentary.
"""


def generate_narrative_plan(
    client,
    topic: str,
    provider: str = "openai",
    model: str = "gpt-4o",
    audience: str = "college-level learners",
    length_seconds: int = 180,
) -> Optional[Dict[str, Any]]:
    """Generate a narrative arc plan for an educational video.

    Returns a dict with keys: title, hook, misconception, aha_moment,
    emotional_arc, scene_beats, visual_metaphors, color_theme,
    estimated_total_seconds, pacing_notes.

    Returns None if generation fails.
    """
    prompt = NARRATIVE_PROMPT.format(
        topic=topic,
        audience=audience,
        length=f"{length_seconds}s (~{length_seconds // 60}m)",
    )

    try:
        response_text = complete_llm(
            client=client,
            provider=provider,
            model=model,
            system_prompt="You are a master educational video narrative designer.",
            user_prompt=prompt,
            max_tokens=4000,
        )
    except Exception as exc:
        print(f"[WARN] Narrative plan generation failed: {exc}")
        return None

    try:
        plan = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Try stripping markdown fences
        cleaned = response_text.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence) :].strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[: -len("```")].strip()
        try:
            plan = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Could not parse narrative plan JSON: {exc}")
            return None

    # Validate expected keys
    required = ("title", "hook", "scene_beats", "aha_moment")
    for key in required:
        if key not in plan:
            print(f"[WARN] Narrative plan missing key: {key}")
            return None

    # Normalize scene_beats
    beats = plan.get("scene_beats", [])
    if not isinstance(beats, list) or len(beats) == 0:
        print("[WARN] Narrative plan has no scene beats")
        return None

    # Ensure scene_numbers are sequential
    for i, beat in enumerate(beats, 1):
        beat["scene_number"] = i

    # Ensure estimated_total_seconds is reasonable
    total = plan.get("estimated_total_seconds")
    if not total:
        plan["estimated_total_seconds"] = sum(
            b.get("estimated_seconds", 20) for b in beats
        )

    return plan


def plan_to_prompt_context(plan: Dict[str, Any]) -> str:
    """Convert a narrative plan into a prompt appendix for script generation."""
    lines = [
        "## NARRATIVE ARC",
        f"Title: {plan.get('title', '')}",
        f"Hook: {plan.get('hook', '')}",
        f"Misconception: {plan.get('misconception', '')}",
        f"Aha Moment: {plan.get('aha_moment', '')}",
        f"Emotional Arc: {plan.get('emotional_arc', '')}",
        f"Color Theme: {plan.get('color_theme', 'classic_3b1b')}",
        f"Pacing Notes: {plan.get('pacing_notes', '')}",
        "",
        "## SCENE BEATS",
    ]
    for beat in plan.get("scene_beats", []):
        lines.append(
            f"Scene {beat['scene_number']} ({beat.get('purpose', '')}): "
            f"{beat.get('narration_summary', '')} | "
            f"Visual: {beat.get('visual_approach', '')} | "
            f"~{beat.get('estimated_seconds', 20)}s"
        )
    lines.append("")
    lines.append("## VISUAL METAPHORS")
    for concept, metaphor in plan.get("visual_metaphors", {}).items():
        lines.append(f"- {concept}: {metaphor}")
    return "\n".join(lines)
