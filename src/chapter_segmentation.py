"""Automatic chapter segmentation for educational videos.

Groups scenes into chapters based on semantic topic shifts.
Uses LLM for grouping when available, falls back to heuristics.
"""

import re
from typing import Dict, List, Optional


def _heuristic_segment(scenes: List[Dict]) -> List[Dict]:
    """Group scenes into chapters using title/text heuristics.

    Rules:
    - Explicit chapter field triggers a new chapter
    - Scene title changes that are semantically different trigger chapters
    - Every 3-5 scenes, force a chapter boundary if no natural break
    """
    if not scenes:
        return []

    chapters = []
    current_chapter = {"title": "Introduction", "scenes": []}
    last_title_words = set()

    for i, scene in enumerate(scenes):
        # Explicit chapter field
        explicit = scene.get("chapter", "").strip()
        if explicit and current_chapter["scenes"] and explicit != current_chapter.get("title"):
            chapters.append(current_chapter)
            current_chapter = {"title": explicit, "scenes": []}

        # Title-based boundary detection
        title = scene.get("title", "").strip()
        if title and current_chapter["scenes"]:
            title_words = set(re.findall(r"\b\w+\b", title.lower()))
            # Common stop words to ignore
            stop = {"the", "a", "an", "is", "are", "of", "to", "and", "in", "on", "at", "for", "with", "how", "what", "why"}
            title_words -= stop
            if last_title_words and title_words:
                overlap = len(title_words & last_title_words) / max(len(title_words), len(last_title_words))
                if overlap < 0.3 and len(current_chapter["scenes"]) >= 2:
                    # Significant topic shift
                    chapters.append(current_chapter)
                    current_chapter = {"title": title, "scenes": []}
            last_title_words = title_words

        current_chapter["scenes"].append(i)

        # Force chapter boundary every 4 scenes if no natural break
        if len(current_chapter["scenes"]) >= 4 and i < len(scenes) - 1:
            next_title = scenes[i + 1].get("title", "").strip()
            next_text = scenes[i + 1].get("text", "")[:60]
            new_title = next_title or next_text or f"Part {len(chapters) + 2}"
            chapters.append(current_chapter)
            current_chapter = {"title": new_title, "scenes": []}

    if current_chapter["scenes"]:
        chapters.append(current_chapter)

    # If only one chapter with all scenes, try to split by content shifts
    if len(chapters) == 1 and len(scenes) > 4:
        return _split_by_content(scenes)

    return chapters


def _split_by_content(scenes: List[Dict]) -> List[Dict]:
    """Split a long single-chapter video by content keywords."""
    mid = len(scenes) // 2
    first_text = " ".join(s.get("text", "") for s in scenes[:mid]).lower()
    second_text = " ".join(s.get("text", "") for s in scenes[mid:]).lower()

    # Try to find distinguishing keywords
    first_words = set(re.findall(r"\b\w{5,}\b", first_text))
    second_words = set(re.findall(r"\b\w{5,}\b", second_text))
    unique_second = second_words - first_words

    # Pick a representative word for the second half title
    title2 = ""
    if unique_second:
        # Prefer words that appear multiple times
        word_counts = {}
        for w in re.findall(r"\b\w{5,}\b", second_text):
            if w in unique_second:
                word_counts[w] = word_counts.get(w, 0) + 1
        if word_counts:
            title2 = max(word_counts, key=word_counts.get).title()

    return [
        {"title": scenes[0].get("title", "Introduction") or "Introduction", "scenes": list(range(mid))},
        {"title": title2 or "Continuation", "scenes": list(range(mid, len(scenes)))},
    ]


def _llm_segment(
    scenes: List[Dict],
    client,
    provider: str,
    model: Optional[str] = None,
) -> List[Dict]:
    """Use LLM to group scenes into chapters."""
    from llm_chat import complete_llm

    scene_list = "\n".join(
        f"Scene {i + 1}: {s.get('title', '')}\nText: {s.get('text', '')[:120]}"
        for i, s in enumerate(scenes)
    )

    prompt = f"""Group these video scenes into logical chapters.

SCENES:
{scene_list}

RULES:
- Each chapter should cover one coherent sub-topic
- Aim for 2-4 scenes per chapter
- Chapter titles should be concise (2-4 words)
- Return ONLY a JSON array like: [{{"title": "Chapter Name", "scenes": [1,2,3]}}]
- Scene numbers are 1-based
"""

    try:
        response = complete_llm(
            client=client,
            provider=provider,
            model=model,
            system_prompt="You are a video editor. Group scenes into chapters. Return only JSON.",
            user_prompt=prompt,
            max_tokens=2000,
        )
        from json_utils import extract_json_from_llm_response
        data = extract_json_from_llm_response(response)
        if isinstance(data, list):
            # Convert 1-based scene numbers to 0-based indices
            chapters = []
            for ch in data:
                scenes_1based = ch.get("scenes", [])
                scenes_0based = [s - 1 for s in scenes_1based if isinstance(s, int) and 1 <= s <= len(scenes)]
                if scenes_0based:
                    chapters.append({"title": ch.get("title", "Chapter"), "scenes": scenes_0based})
            if chapters:
                return chapters
    except Exception as exc:
        print(f"[WARN] LLM chapter segmentation failed: {exc}")

    return []


def auto_segment_chapters(
    scenes: List[Dict],
    client=None,
    provider: str = "openai",
    model: Optional[str] = None,
    use_llm: bool = True,
) -> List[Dict]:
    """Automatically segment scenes into chapters.

    Args:
        scenes: List of scene dicts with text, title, chapter keys.
        client: LLM client (optional, for LLM-based segmentation).
        provider: LLM provider name.
        model: LLM model name.
        use_llm: Whether to try LLM-based segmentation.

    Returns:
        List of chapter dicts with title and scenes (0-based indices).
    """
    if not scenes:
        return []
    if len(scenes) <= 2:
        return [{"title": scenes[0].get("title", "Video") or "Video", "scenes": list(range(len(scenes)))}]

    # Try LLM first if available
    if use_llm and client:
        llm_result = _llm_segment(scenes, client, provider, model)
        if llm_result:
            print(f"[OK] LLM segmented into {len(llm_result)} chapters")
            return llm_result

    # Fallback to heuristic
    result = _heuristic_segment(scenes)
    print(f"[OK] Heuristic segmented into {len(result)} chapters")
    return result


def chapters_to_html_metadata(chapters: List[Dict], scene_durations: List[float]) -> List[Dict]:
    """Convert chapter segments to HTML player metadata with timestamps.

    Args:
        chapters: List of {title, scenes} where scenes are 0-based indices.
        scene_durations: Duration in seconds for each scene.

    Returns:
        List of {title, start, end} dicts for the HTML player.
    """
    metadata = []
    cumulative = 0.0

    for ch in chapters:
        chapter_start = cumulative
        for si in ch["scenes"]:
            if si < len(scene_durations):
                cumulative += scene_durations[si]
        chapter_end = cumulative
        metadata.append(
            {
                "title": ch["title"],
                "start": round(chapter_start, 2),
                "end": round(chapter_end, 2),
            }
        )

    return metadata
