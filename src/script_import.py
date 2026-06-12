"""Parse pasted scripts in many formats (LLM output, markdown, JSON, AV-style)."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from json_utils import extract_json_from_llm_response
from llm_chat import complete_llm
from video_settings import normalize_video_settings
from visual_events import enrich_scene_events, normalize_visual_events

DEFAULT_ANIMATION = (
    "Dark navy background (#1a1a2e). Illustrate the narration with clear Manim "
    "animations: title fade-in, then main visual elements. Use WHITE text, BLUE "
    "highlights, YELLOW emphasis. Keep layout uncluttered."
)

LOOSE_FORMAT_HINTS = frozenset({"loose", "text", "scene", "markdown"})

LOOSE_FORMAT_ERROR = (
    "Could not detect any scenes. Use the Loose Scene Format:\n\n"
    "Scene 1: Opening Hook\n"
    "Narration: What the narrator says.\n"
    "Visual: What appears on screen.\n\n"
    "Scene 2: Worked Example\n"
    "Narration: ...\n"
    "Visual: ...\n\n"
    "You can also use Voiceover/Animation or On-screen instead of Narration/Visual. "
    "JSON arrays remain supported when Script Format is JSON only or Auto-detect."
)

HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+)$")
TIMED_HEADING = re.compile(
    r"^\[?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*-\s*\d{1,2}:\d{2}(?::\d{2})?)?)\s*\]?\s*(.*)$"
)
STEP_LINE = re.compile(
    r"^(?:#{1,6}\s+)?(?:\*\*)?(?:Step|Scene|Section|Part|Slide)\s+\d+[.:)\]]\s*(.+?)(?:\*\*)?\s*$",
    re.I,
)
NUMBERED_SCENE = re.compile(r"^(?:\*\*)?(?:Scene|Step|Section)\s+\d+(?:\*\*)?\s*$", re.I)
METADATA_LINE = re.compile(
    r"^(?:TITLE|TARGET\s+RUNTIME|WORD\s+COUNT|DATE|VERSION|AUTHOR)\s*:",
    re.I,
)
TIMING_MARKER = re.compile(r"^\[~?\d{1,2}:\d{2}(?::\d{2})?\s*(?:-\s*[^\]]*)?\]\s*$")
SEPARATOR_LINE = re.compile(r"^-{3,}$|^\*{3,}$|^_{3,}$")
BRACKET_VISUAL = re.compile(
    r"^\[(?:VISUAL|ANIMATION|SCREEN|GRAPHIC|B-ROLL|ON-?SCREEN|VIDEO|MANIM)\s*:\s*(.+?)\]\s*$",
    re.I,
)
BRACKET_SKIP = re.compile(r"^\[(?:PAUSE|EMPHASIS|CUT|SFX|MUSIC|NOTE)\b[^\]]*\]\s*$", re.I)
LABELED_FIELD = re.compile(
    r"^(?:\*\*)?(Narration|Voiceover|Voice-over|VO|Audio|Script|Spoken\s+Text|Text|"
    r"Animation|Visuals?|Visual|On-?screen|Graphics?|Manim|B-?roll)"
    r"(?:\*\*)?\s*:\s*(.*)$",
    re.I,
)
NARRATION_KEYS = frozenset(
    {"narration", "voiceover", "voice-over", "vo", "audio", "script", "spoken text", "text"}
)
ANIMATION_KEYS = frozenset(
    {
        "animation",
        "visual",
        "visuals",
        "on-screen",
        "onscreen",
        "graphic",
        "graphics",
        "manim",
        "b-roll",
        "broll",
    }
)
FENCED_JSON = re.compile(r"```(?:json|JSON)?\s*\n([\s\S]*?)\n```", re.MULTILINE)


def _visual_fallback(title: Optional[str] = None, narration: str = "") -> str:
    """Build a simple Manim visual description when none was provided."""
    parts = ["Dark navy background (#1a1a2e)."]
    if title:
        parts.append(f'Fade in title text: "{title.strip()}".')
    snippet = " ".join(narration.split())[:140].strip()
    if snippet:
        parts.append(f"Illustrate the narration with clear visuals: {snippet}.")
    else:
        parts.append("Show a simple title card and relevant math visuals.")
    parts.append("Use WHITE text, BLUE highlights, YELLOW emphasis. Keep layout uncluttered.")
    return " ".join(parts)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("text", "narration", "voiceover", "script", "content", "spoken_text", "audio"):
            if value.get(key):
                return str(value[key]).strip()
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _coerce_animation(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in (
            "animation",
            "visual",
            "visuals",
            "on_screen",
            "graphics",
            "manim",
            "description",
        ):
            if value.get(key):
                return str(value[key]).strip()
        return ""
    return str(value).strip()


def _clean_heading_title(title: str) -> str:
    title = title.strip()
    timed = TIMED_HEADING.match(title)
    if timed:
        remainder = (timed.group(2) or "").strip()
        return remainder or timed.group(1).strip()
    return title


def _is_default_animation(animation: str) -> bool:
    return not animation or animation.strip() == DEFAULT_ANIMATION


def _is_inferred_animation(animation: str, title: Optional[str], narration: str) -> bool:
    if _is_default_animation(animation):
        return True
    if title or narration:
        return animation.strip() == _visual_fallback(title, narration).strip()
    return False


def _normalize_scene(raw: dict, chapter: Optional[str] = None) -> dict:
    scene = {
        "text": _coerce_text(
            raw.get("text")
            or raw.get("narration")
            or raw.get("voiceover")
            or raw.get("script")
            or raw.get("spoken_text")
            or raw.get("audio")
        ),
        "animation": _coerce_animation(
            raw.get("animation")
            or raw.get("visual")
            or raw.get("visuals")
            or raw.get("on_screen")
            or raw.get("graphics")
            or raw.get("manim")
        ),
    }
    title = raw.get("title") or raw.get("name") or raw.get("section")
    if title:
        scene["title"] = str(title).strip()
    if chapter:
        scene["chapter"] = chapter
    elif raw.get("chapter"):
        scene["chapter"] = str(raw["chapter"]).strip()
    title_str = scene.get("title")
    if not scene["animation"]:
        scene["animation"] = _visual_fallback(title_str, scene["text"])
        scene["_inferred_visual"] = True
    elif _is_default_animation(scene["animation"]):
        scene["animation"] = _visual_fallback(title_str, scene["text"])
        scene["_inferred_visual"] = True
    elif raw.get("_inferred_visual"):
        scene["_inferred_visual"] = True
    if raw.get("_missing_narration"):
        scene["_missing_narration"] = True
    events = normalize_visual_events(raw.get("visual_events"))
    if events:
        scene["visual_events"] = events
    return enrich_scene_events(scene)


def _flatten_chapters(data: dict) -> Tuple[List[dict], List[dict], Optional[str]]:
    title = data.get("title") or data.get("topic") or data.get("name")
    chapters_meta: List[dict] = []
    scenes: List[dict] = []

    chapters = data.get("chapters") or data.get("sections") or data.get("parts")
    if isinstance(chapters, list) and chapters:
        for chapter_index, chapter in enumerate(chapters, 1):
            if isinstance(chapter, str) and chapter.strip():
                scenes.append(_normalize_scene({"text": chapter}))
                continue
            if not isinstance(chapter, dict):
                continue
            chapter_title = (
                chapter.get("title")
                or chapter.get("name")
                or chapter.get("chapter")
                or f"Chapter {chapter_index}"
            )
            chapter_title = str(chapter_title).strip()
            chapter_scenes = (
                chapter.get("scenes")
                or chapter.get("sections")
                or chapter.get("slides")
                or chapter.get("parts")
                or []
            )
            if isinstance(chapter_scenes, list):
                chapters_meta.append({"title": chapter_title, "scene_count": len(chapter_scenes)})
                for raw_scene in chapter_scenes:
                    if isinstance(raw_scene, dict):
                        scenes.append(_normalize_scene(raw_scene, chapter=chapter_title))
                    elif isinstance(raw_scene, str) and raw_scene.strip():
                        scenes.append(_normalize_scene({"text": raw_scene}, chapter=chapter_title))
            elif isinstance(chapter.get("text"), str):
                scenes.append(_normalize_scene(chapter, chapter=chapter_title))
        return scenes, chapters_meta, title

    raw_scenes = data.get("scenes") or data.get("script") or data.get("slides") or []
    if isinstance(raw_scenes, list):
        for raw_scene in raw_scenes:
            if isinstance(raw_scene, dict):
                scenes.append(_normalize_scene(raw_scene))
            elif isinstance(raw_scene, str) and raw_scene.strip():
                scenes.append(_normalize_scene({"text": raw_scene}))
    return scenes, chapters_meta, title


def _parse_json_value(parsed: Any) -> Tuple[List[dict], List[dict], Optional[str]]:
    if isinstance(parsed, list):
        scenes = []
        for item in parsed:
            if isinstance(item, dict):
                scenes.append(_normalize_scene(item))
            elif isinstance(item, str) and item.strip():
                scenes.append(_normalize_scene({"text": item}))
        return scenes, [], None
    if isinstance(parsed, dict):
        return _flatten_chapters(parsed)
    raise ValueError("JSON must be an array of scenes or an object with chapters/scenes")


def _try_extract_json(raw_text: str) -> Optional[Any]:
    stripped = raw_text.strip()
    if not stripped:
        return None

    for candidate in (stripped,):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for match in FENCED_JSON.finditer(raw_text):
        block = match.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    try:
        return extract_json_from_llm_response(raw_text)
    except Exception:
        return None


def _parse_json_script(raw_text: str) -> Tuple[List[dict], List[dict], Optional[str]]:
    parsed = _try_extract_json(raw_text)
    if parsed is None:
        raise ValueError("Could not parse JSON from script")
    return _parse_json_value(parsed)


def _strip_metadata_prefix(lines: List[str]) -> Tuple[List[str], Optional[str]]:
    cleaned: List[str] = []
    title = None
    skipping = True

    for line in lines:
        stripped = line.strip()
        if skipping:
            if not stripped:
                continue
            if METADATA_LINE.match(stripped):
                if stripped.upper().startswith("TITLE:"):
                    title = stripped.split(":", 1)[1].strip()
                continue
            if SEPARATOR_LINE.match(stripped):
                continue
            skipping = False

        if SEPARATOR_LINE.match(stripped) and not cleaned:
            continue
        cleaned.append(line)

    return cleaned, title


def _collect_headings(lines: List[str]) -> List[Tuple[int, int, str]]:
    headings = []
    for index, line in enumerate(lines):
        match = HEADING_LINE.match(line.strip())
        if match:
            level = len(match.group(1))
            title = _clean_heading_title(match.group(2))
            if title:
                headings.append((level, index, title))
    return headings


def _infer_heading_roles(headings: List[Tuple[int, int, str]]) -> Dict[str, Any]:
    if not headings:
        return {"title": None, "chapter_level": None, "scene_level": None}

    title = None
    remaining = list(headings)

    if remaining[0][0] == 1:
        h1_count = sum(1 for level, _, _ in remaining if level == 1)
        if h1_count == 1 and (len(remaining) == 1 or remaining[1][0] > 1):
            title = remaining[0][2]
            remaining = remaining[1:]

    if not remaining:
        return {"title": title, "chapter_level": None, "scene_level": None}

    levels = sorted({level for level, _, _ in remaining})
    if len(levels) >= 2:
        return {"title": title, "chapter_level": levels[0], "scene_level": levels[1]}
    return {"title": title, "chapter_level": None, "scene_level": levels[0]}


def _is_scene_boundary_line(
    stripped: str, roles: Dict[str, Any]
) -> Optional[Tuple[str, Optional[str]]]:
    """Return (scene_title, chapter_override) if this line starts a new scene/chapter."""
    if (
        METADATA_LINE.match(stripped)
        or TIMING_MARKER.match(stripped)
        or SEPARATOR_LINE.match(stripped)
    ):
        return None

    heading = HEADING_LINE.match(stripped)
    if heading:
        level = len(heading.group(1))
        title = _clean_heading_title(heading.group(2))
        if roles.get("chapter_level") and level == roles["chapter_level"]:
            return ("__chapter__:" + title, title)
        if roles.get("scene_level") and level == roles["scene_level"]:
            return (title, None)
        if not roles.get("chapter_level") and not roles.get("scene_level"):
            return (title, None)
        return None

    step = STEP_LINE.match(stripped)
    if step:
        return (step.group(1).strip(), None)

    if NUMBERED_SCENE.match(stripped):
        return (stripped.replace("*", "").strip(), None)

    return None


def _parse_content_lines(
    lines: List[str], chapter: Optional[str], scene_title: Optional[str]
) -> Optional[dict]:
    narration_parts: List[str] = []
    animation_parts: List[str] = []
    current_field = "text"

    for line in lines:
        stripped = line.strip()
        if not stripped or METADATA_LINE.match(stripped) or TIMING_MARKER.match(stripped):
            continue
        if BRACKET_SKIP.match(stripped):
            continue

        visual = BRACKET_VISUAL.match(stripped)
        if visual:
            animation_parts.append(visual.group(1).strip())
            current_field = "animation"
            continue

        labeled = LABELED_FIELD.match(stripped)
        if labeled:
            label = labeled.group(1).lower().replace(" ", " ")
            content = labeled.group(2).strip()
            if label in NARRATION_KEYS:
                current_field = "text"
                if content:
                    narration_parts.append(content)
            elif (
                label.replace("-", "") in {k.replace("-", "") for k in ANIMATION_KEYS}
                or label in ANIMATION_KEYS
            ):
                current_field = "animation"
                if content:
                    animation_parts.append(content)
            continue

        if HEADING_LINE.match(stripped) or STEP_LINE.match(stripped):
            continue

        if current_field == "animation":
            animation_parts.append(stripped)
        else:
            narration_parts.append(stripped)

    text = " ".join(narration_parts).strip()
    animation = " ".join(animation_parts).strip()
    has_explicit_narration = bool(narration_parts)
    has_explicit_visual = bool(animation_parts)

    if not text and not animation:
        return None
    if not text and animation:
        text = scene_title or animation

    scene = {
        "text": text,
        "animation": animation,
        "_missing_narration": not has_explicit_narration,
        "_inferred_visual": not has_explicit_visual,
    }
    if scene_title and not scene_title.startswith("__chapter__:"):
        scene["title"] = scene_title
    if chapter:
        scene["chapter"] = chapter
    return scene


def _parse_flexible_text(raw_text: str) -> Tuple[List[dict], List[dict], Optional[str]]:
    lines, metadata_title = _strip_metadata_prefix(raw_text.splitlines())
    headings = _collect_headings(lines)
    roles = _infer_heading_roles(headings)

    has_structure = bool(headings) or any(
        SEPARATOR_LINE.match(line.strip())
        or STEP_LINE.match(line.strip())
        or NUMBERED_SCENE.match(line.strip())
        or BRACKET_VISUAL.match(line.strip())
        or LABELED_FIELD.match(line.strip())
        for line in lines
    )
    if not has_structure:
        return _parse_paragraph_fallback(raw_text), [], metadata_title

    scenes: List[dict] = []
    chapters_meta: List[dict] = []
    current_chapter: Optional[str] = None
    buffer: List[str] = []
    pending_title: Optional[str] = None

    def flush_buffer():
        nonlocal buffer, pending_title
        if not buffer:
            pending_title = None
            return
        scene = _parse_content_lines(buffer, current_chapter, pending_title)
        buffer = []
        pending_title = None
        if scene and scene.get("text"):
            scenes.append(_normalize_scene(scene))

    boundary_indices = set()
    for _, index, _ in headings:
        boundary_indices.add(index)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if STEP_LINE.match(stripped) or NUMBERED_SCENE.match(stripped):
            boundary_indices.add(index)

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        if SEPARATOR_LINE.match(stripped):
            flush_buffer()
            index += 1
            continue

        boundary = _is_scene_boundary_line(stripped, roles)
        if boundary is not None:
            flush_buffer()
            scene_title, chapter_override = boundary
            if scene_title.startswith("__chapter__:"):
                current_chapter = chapter_override
                if not any(c["title"] == current_chapter for c in chapters_meta):
                    chapters_meta.append({"title": current_chapter, "scene_count": 0})
                index += 1
                continue
            pending_title = scene_title
            index += 1
            continue

        buffer.append(lines[index])
        index += 1

    flush_buffer()

    title = metadata_title or roles.get("title")

    if not scenes:
        scenes = _parse_paragraph_fallback(raw_text)

    if chapters_meta:
        counts: Dict[str, int] = {}
        for scene in scenes:
            chapter_name = scene.get("chapter") or "Main"
            counts[chapter_name] = counts.get(chapter_name, 0) + 1
        for chapter in chapters_meta:
            chapter["scene_count"] = counts.get(chapter["title"], 0)

    return scenes, chapters_meta, title


def _parse_paragraph_fallback(raw_text: str) -> List[dict]:
    blocks: List[str] = []
    current: List[str] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if SEPARATOR_LINE.match(stripped):
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        if not stripped:
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        if METADATA_LINE.match(stripped) or TIMING_MARKER.match(stripped):
            continue
        current.append(line)

    if current:
        blocks.append("\n".join(current).strip())

    scenes = []
    for block in blocks:
        if block.startswith("#"):
            continue
        scene = _parse_content_lines(block.splitlines(), None, None)
        if scene:
            scenes.append(_normalize_scene(scene))
    return scenes


def _is_json_script(raw_text: str) -> bool:
    stripped = raw_text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return _try_extract_json(raw_text) is not None
    if FENCED_JSON.search(raw_text):
        return _try_extract_json(raw_text) is not None
    return False


def _detect_format(raw_text: str) -> str:
    if _is_json_script(raw_text):
        return "json"
    return "loose"


def _parse_loose_script(raw_text: str) -> Tuple[List[dict], List[dict], Optional[str], str]:
    """Parse loose scene format; fall back to JSON when content is clearly JSON."""
    if _is_json_script(raw_text):
        scenes, chapters, title = _parse_json_script(raw_text)
        return scenes, chapters, title, "json"
    scenes, chapters, title = _parse_flexible_text(raw_text)
    if not scenes:
        parsed = _try_extract_json(raw_text)
        if parsed is not None:
            scenes, chapters, title = _parse_json_value(parsed)
            return scenes, chapters, title, "json"
    return scenes, chapters, title, "loose"


def _strip_internal_scene_keys(scenes: List[dict]) -> None:
    for scene in scenes:
        scene.pop("_missing_narration", None)
        scene.pop("_inferred_visual", None)


def _collect_scene_warnings(scenes: List[dict]) -> List[str]:
    warnings: List[str] = []
    for index, scene in enumerate(scenes, 1):
        label = scene.get("title") or f"Scene {index}"
        if scene.get("_missing_narration"):
            warnings.append(
                f'Scene {index} ({label}): missing Narration — add a "Narration:" line before rendering.'
            )
        if scene.get("_inferred_visual"):
            warnings.append(
                f"Scene {index} ({label}): no Visual instructions — using a simple auto-generated visual description."
            )
    return warnings


def parse_import_script(raw_text: str, format_hint: str = "loose", title: Optional[str] = None):
    """Parse pasted script into normalized scenes. Accepts many LLM/markdown/JSON formats."""
    if not raw_text or not str(raw_text).strip():
        raise ValueError("Script content is empty")

    text = str(raw_text)
    hint = (format_hint or "loose").strip().lower()

    if hint == "json":
        try:
            scenes, chapters, parsed_title = _parse_json_script(text)
            resolved_fmt = "json"
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    elif hint == "auto":
        if _is_json_script(text):
            scenes, chapters, parsed_title = _parse_json_script(text)
            resolved_fmt = "json"
        else:
            scenes, chapters, parsed_title, resolved_fmt = _parse_loose_script(text)
    else:
        scenes, chapters, parsed_title, resolved_fmt = _parse_loose_script(text)

    resolved_title = (title or parsed_title or "").strip() or None

    if len(scenes) < 1:
        raise ValueError(LOOSE_FORMAT_ERROR)

    warnings = _collect_scene_warnings(scenes)
    _strip_internal_scene_keys(scenes)

    if len(scenes) == 1:
        warnings.append("Only one scene found — add at least one more for a full video.")

    return {
        "scenes": scenes,
        "chapters": chapters,
        "title": resolved_title,
        "scene_count": len(scenes),
        "warnings": warnings,
        "format": resolved_fmt,
    }


def enrich_script_animations(
    client,
    scenes: List[dict],
    provider: str,
    model: str,
    video_settings=None,
    batch_size: int = 5,
) -> List[dict]:
    """Use LLM to generate Manim animation descriptions for scenes that lack them."""
    video_settings = normalize_video_settings(video_settings)
    style = video_settings["style_preset"]
    enriched = []

    for start in range(0, len(scenes), batch_size):
        batch = scenes[start : start + batch_size]
        batch_payload = []
        for index, scene in enumerate(batch, start + 1):
            batch_payload.append(
                {
                    "scene": index,
                    "chapter": scene.get("chapter"),
                    "title": scene.get("title"),
                    "text": scene.get("text", ""),
                    "current_animation": scene.get("animation", ""),
                }
            )

        prompt = f"""For each scene below, write a detailed Manim animation description.

VISUAL STYLE (apply to every scene):
{style['visual_style']}

AUDIENCE: {style['audience']}
TONE: {style['tone']}

Rules:
- Animations must be specific enough to implement in Manim Community Edition
- No Python code — description only
- Match narration pacing; keep visuals simple
- Maintain consistent colors and layout across scenes
- If current_animation is already detailed (not generic), refine it rather than replacing entirely

Scenes:
{json.dumps(batch_payload, ensure_ascii=False, indent=2)}

Respond ONLY with a JSON array of objects:
[{{"scene": 1, "animation": "..."}}]
"""

        response_text = complete_llm(
            client=client,
            provider=provider,
            model=model,
            system_prompt=(
                "You write Manim animation descriptions for educational math videos. "
                "Respond only with valid JSON."
            ),
            user_prompt=prompt,
        )
        animation_map: Dict[int, str] = {}
        try:
            parsed = extract_json_from_llm_response(response_text)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and item.get("scene"):
                        animation_map[int(item["scene"])] = _coerce_animation(item.get("animation"))
        except Exception:
            pass

        for offset, scene in enumerate(batch):
            scene_number = start + offset + 1
            copy = dict(scene)
            new_animation = animation_map.get(scene_number)
            if new_animation:
                copy["animation"] = new_animation
            elif _is_inferred_animation(
                copy.get("animation", ""), copy.get("title"), copy.get("text", "")
            ):
                copy["animation"] = _visual_fallback(copy.get("title"), copy.get("text", ""))
            enriched.append(copy)

    return enriched


def prepare_imported_scenes(
    raw_text: Optional[str] = None,
    script: Optional[list] = None,
    format_hint: str = "loose",
    title: Optional[str] = None,
    enrich: bool = False,
    client=None,
    provider: str = "openai",
    model: str = "gpt-4o",
    video_settings=None,
) -> Tuple[List[dict], dict]:
    """Parse and optionally enrich imported script; returns (scenes, meta)."""
    if script is not None:
        if not isinstance(script, list):
            raise ValueError("script must be a list of scenes")
        scenes = [
            _normalize_scene(item) if isinstance(item, dict) else _normalize_scene({"text": item})
            for item in script
        ]
        meta = {
            "title": title,
            "chapters": _build_chapters_from_scenes(scenes),
            "scene_count": len(scenes),
            "warnings": [],
            "format": "json",
        }
    elif raw_text:
        meta = parse_import_script(raw_text, format_hint=format_hint, title=title)
        scenes = meta["scenes"]
    else:
        raise ValueError("Provide import_script text or a script array")

    if enrich:
        if not client:
            raise ValueError("LLM client required to enrich animations")
        scenes = enrich_script_animations(
            client, scenes, provider, model, video_settings=video_settings
        )
        meta["warnings"] = [
            w for w in meta.get("warnings", []) if "default animation" not in w.lower()
        ]

    return scenes, meta


def _build_chapters_from_scenes(scenes: List[dict]) -> List[dict]:
    seen: Dict[str, int] = {}
    for scene in scenes:
        chapter = scene.get("chapter") or "Main"
        seen[chapter] = seen.get(chapter, 0) + 1
    return [{"title": name, "scene_count": count} for name, count in seen.items()]
