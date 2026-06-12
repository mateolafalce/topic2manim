"""Shared visual style registry carried across all scenes for continuity."""

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

DEFAULT_REGISTRY: Dict[str, Any] = {
    "background_color": "#1a1a2e",
    "title_color": "WHITE",
    "body_color": "WHITE",
    "accent_color": "BLUE",
    "emphasis_color": "YELLOW",
    "positive_color": "GREEN",
    "warning_color": "RED",
    "font_scale_title": 1.2,
    "font_scale_body": 0.8,
    "named_objects": [],
    "last_scene_title": "",
    "last_scene_summary": "",
    "scenes_completed": 0,
}


def create_style_registry(video_settings=None) -> Dict[str, Any]:
    registry = deepcopy(DEFAULT_REGISTRY)
    if video_settings:
        style = video_settings.get("style_preset") or {}
        visual = style.get("visual_style", "")
        if "beginner" in style.get("label", "").lower():
            registry["accent_color"] = "BLUE"
        if "#0f0f1a" in visual:
            registry["background_color"] = "#0f0f1a"
    return registry


def _extract_named_objects(code: str) -> List[str]:
    if not code:
        return []
    names = re.findall(
        r"^\s*(\w+)\s*=\s*(?:Text|MathTex|Paragraph|Circle|Square|Arrow|Line|Axes|NumberPlane|VGroup)\(",
        code,
        re.MULTILINE,
    )
    return list(dict.fromkeys(names))[:12]


def update_style_registry(
    registry: Dict[str, Any],
    scene_data: dict,
    code: str = "",
) -> Dict[str, Any]:
    updated = deepcopy(registry)
    updated["scenes_completed"] = int(updated.get("scenes_completed", 0)) + 1
    updated["last_scene_title"] = scene_data.get("title") or scene_data.get("chapter") or ""
    text = scene_data.get("text", "")
    updated["last_scene_summary"] = text[:200] + ("..." if len(text) > 200 else "")

    new_objects = _extract_named_objects(code)
    existing = list(updated.get("named_objects") or [])
    for name in new_objects:
        if name not in existing:
            existing.append(name)
    updated["named_objects"] = existing[-20:]

    return updated


def format_registry_for_prompt(registry: Optional[Dict[str, Any]]) -> str:
    if not registry:
        return ""
    objects = registry.get("named_objects") or []
    objects_text = ", ".join(objects) if objects else "none yet"
    return f"""SHARED STYLE REGISTRY (use these values in EVERY scene for consistency):
- Background: self.camera.background_color = "{registry.get('background_color', '#1a1a2e')}"
- Title text color: {registry.get('title_color', 'WHITE')}
- Body text color: {registry.get('body_color', 'WHITE')}
- Accent/highlight color: {registry.get('accent_color', 'BLUE')}
- Emphasis color: {registry.get('emphasis_color', 'YELLOW')}
- Title font scale: {registry.get('font_scale_title', 1.2)}
- Body font scale: {registry.get('font_scale_body', 0.8)}
- Named objects from prior scenes (reuse names/styles if continuing): {objects_text}
- Previous scene: {registry.get('last_scene_title') or 'N/A'} — {registry.get('last_scene_summary') or 'N/A'}

CRITICAL: Match colors, background, and font sizes exactly. Reuse named objects when narratively appropriate.
"""
