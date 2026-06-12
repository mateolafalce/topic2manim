"""Visual event checklist for math video scenes — improves Manim alignment."""

import re
from typing import Any, Dict, List

# Canonical events the Manim generator must satisfy per scene.
VISUAL_EVENT_CATALOG: Dict[str, str] = {
    "show_title": "Fade in a title card at the top of the frame",
    "show_axes": "Display 2D coordinate axes (NumberPlane or Axes)",
    "plot_function": "Plot a mathematical function on axes",
    "show_equation": "Display a key equation with MathTex",
    "highlight_term": "Highlight or color a specific term in an equation",
    "show_graph": "Show a graph or chart relevant to the narration",
    "show_geometry": "Draw geometric shapes (circle, triangle, vectors)",
    "show_arrow": "Use arrows to indicate direction, vectors, or flow",
    "show_label": "Add text labels to important elements",
    "transform_shape": "Animate a transformation (shift, scale, rotate)",
    "step_reveal": "Reveal content step-by-step in sync with narration",
    "show_table": "Display a simple table or grid of values",
    "show_number_line": "Show a number line with marked points",
    "compare_objects": "Show two objects side-by-side for comparison",
    "summarize": "End scene with a brief summary or key takeaway text",
}

EVENT_KEYWORDS: Dict[str, List[str]] = {
    "show_title": ["title", "title card", "introduce the topic", "heading"],
    "show_axes": ["axes", "axis", "coordinate", "numberplane", "grid"],
    "plot_function": ["plot", "graph of", "function", "curve", "parabola", "sin", "cos"],
    "show_equation": ["equation", "formula", "mathtex", "latex", "equals"],
    "highlight_term": ["highlight", "emphasize", "color the", "underline"],
    "show_graph": ["chart", "bar chart", "diagram", "graph"],
    "show_geometry": ["circle", "triangle", "square", "polygon", "angle", "geometry"],
    "show_arrow": ["arrow", "vector", "direction", "point to"],
    "show_label": ["label", "caption", "annotate", "call out"],
    "transform_shape": ["transform", "morph", "animate", "scale", "rotate", "shift"],
    "step_reveal": ["step by step", "reveal", "one at a time", "sequentially"],
    "show_table": ["table", "matrix", "grid of values"],
    "show_number_line": ["number line", "numberline"],
    "compare_objects": ["compare", "versus", "vs", "side by side", "difference between"],
    "summarize": ["summary", "recap", "takeaway", "conclude", "in conclusion"],
}


def normalize_visual_events(raw: Any) -> List[str]:
    """Coerce visual_events to a list of known event ids."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]
    if not isinstance(raw, list):
        return []

    normalized = []
    catalog_keys = {k.lower(): k for k in VISUAL_EVENT_CATALOG}
    for item in raw:
        key = str(item).strip().lower().replace(" ", "_").replace("-", "_")
        if key in catalog_keys:
            normalized.append(catalog_keys[key])
        elif key in VISUAL_EVENT_CATALOG:
            normalized.append(key)
    return list(dict.fromkeys(normalized))


def infer_visual_events(text: str = "", animation: str = "", title: str = "") -> List[str]:
    """Infer visual events from narration and animation description."""
    combined = f"{title} {text} {animation}".lower()
    inferred = []
    for event_id, keywords in EVENT_KEYWORDS.items():
        if any(keyword in combined for keyword in keywords):
            inferred.append(event_id)
    if not inferred and text.strip():
        inferred.append("step_reveal")
    return inferred


def enrich_scene_events(scene: dict) -> dict:
    """Ensure scene has visual_events list."""
    enriched = dict(scene)
    events = normalize_visual_events(enriched.get("visual_events"))
    if not events:
        events = infer_visual_events(
            enriched.get("text", ""),
            enriched.get("animation", ""),
            enriched.get("title", ""),
        )
    enriched["visual_events"] = events
    return enriched


def enrich_script_events(scenes: List[dict]) -> List[dict]:
    return [enrich_scene_events(scene) for scene in scenes]


def format_events_for_prompt(events: List[str]) -> str:
    if not events:
        return "No specific visual events — follow the animation description."
    lines = []
    for event_id in events:
        desc = VISUAL_EVENT_CATALOG.get(event_id, event_id)
        lines.append(f"- {event_id}: {desc}")
    return "\n".join(lines)


def get_catalog_for_api() -> List[dict]:
    return [{"id": k, "description": v} for k, v in VISUAL_EVENT_CATALOG.items()]
