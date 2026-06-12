"""Script quality metrics: WPM, readability, retention prediction.

Analyzes script text to compute engagement and accessibility scores.
"""

import re
from typing import Dict, List


def count_syllables(word: str) -> int:
    """Estimate syllable count for a word using vowel groups."""
    word = word.lower().strip()
    if not word:
        return 0
    # Remove trailing e (silent in English)
    if word.endswith("e") and len(word) > 2:
        word = word[:-1]
    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    if count == 0:
        count = 1
    return count


def flesch_reading_ease(text: str) -> float:
    """Calculate Flesch Reading Ease score.

    Score ranges:
        90-100: Very Easy (5th grade)
        80-89: Easy (6th grade)
        70-79: Fairly Easy (7th grade)
        60-69: Standard (8th-9th grade)
        50-59: Fairly Difficult (10th-12th grade)
        30-49: Difficult (College)
        0-29: Very Difficult (Graduate)
    """
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences) if sentences else 1

    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    if word_count == 0:
        return 100.0

    syllable_count = sum(count_syllables(w) for w in words)

    avg_sentence_length = word_count / sentence_count
    avg_syllables_per_word = syllable_count / word_count

    score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
    return max(0, min(100, score))


def flesch_kincaid_grade(text: str) -> float:
    """Calculate Flesch-Kincaid Grade Level."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences) if sentences else 1

    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    if word_count == 0:
        return 0.0

    syllable_count = sum(count_syllables(w) for w in words)

    avg_sentence_length = word_count / sentence_count
    avg_syllables_per_word = syllable_count / word_count

    grade = (0.39 * avg_sentence_length) + (11.8 * avg_syllables_per_word) - 15.59
    return max(0, grade)


def count_long_words(text: str) -> int:
    """Count words with >2 syllables."""
    words = re.findall(r"\b\w+\b", text)
    return sum(1 for w in words if count_syllables(w) > 2)


def gunning_fog_index(text: str) -> float:
    """Calculate Gunning Fog Index (grade level approximation)."""
    words = re.findall(r"\b\w+\b", text)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not words or not sentences:
        return 0.0
    complex_words = count_long_words(text)
    return 0.4 * ((len(words) / len(sentences)) + 100 * (complex_words / len(words)))


def analyze_script_readability(text: str) -> Dict:
    """Compute readability metrics for a script."""
    fre = flesch_reading_ease(text)
    fkg = flesch_kincaid_grade(text)
    gfi = gunning_fog_index(text)
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    sentence_count = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
    avg_word_length = sum(len(w) for w in words) / word_count if word_count else 0
    avg_sentence_length = word_count / sentence_count if sentence_count else 0
    long_word_ratio = count_long_words(text) / word_count if word_count else 0

    # Determine audience label
    if fre >= 80:
        audience = "Elementary / Early Middle School"
    elif fre >= 60:
        audience = "Middle School / High School"
    elif fre >= 40:
        audience = "High School / College"
    else:
        audience = "College / Graduate"

    return {
        "flesch_reading_ease": round(fre, 2),
        "flesch_kincaid_grade": round(fkg, 2),
        "gunning_fog_index": round(gfi, 2),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "long_word_ratio": round(long_word_ratio, 3),
        "recommended_audience": audience,
    }


def estimate_wpm(text: str, duration_seconds: float) -> float:
    """Calculate words per minute for a given text and duration."""
    words = len(re.findall(r"\b\w+\b", text))
    if duration_seconds <= 0:
        return 0.0
    return (words / duration_seconds) * 60


def analyze_pacing(
    scenes: List[Dict], scene_durations: List[float]
) -> List[Dict]:
    """Analyze per-scene WPM and flag pacing issues.

    Args:
        scenes: List of scene dicts with 'text' key.
        scene_durations: List of durations in seconds.

    Returns:
        List of analysis dicts per scene.
    """
    results = []
    for i, scene in enumerate(scenes):
        text = scene.get("text", "")
        duration = scene_durations[i] if i < len(scene_durations) else 0
        wpm = estimate_wpm(text, duration)
        words = len(re.findall(r"\b\w+\b", text))

        # WPM guidelines
        if wpm < 100:
            pace = "slow"
            suggestion = "Consider tightening narration or reducing pause time."
        elif wpm <= 160:
            pace = "optimal"
            suggestion = "Good pacing."
        elif wpm <= 200:
            pace = "fast"
            suggestion = "Consider adding more visual time or slowing narration."
        else:
            pace = "too_fast"
            suggestion = "Narration is too dense. Shorten text or extend scene duration."

        results.append(
            {
                "scene_index": i,
                "word_count": words,
                "duration": round(duration, 2),
                "wpm": round(wpm, 1),
                "pace": pace,
                "suggestion": suggestion,
            }
        )
    return results


def compute_retention_score(
    script_text: str,
    scene_pacing: List[Dict],
    has_hook: bool = True,
    has_visual_metaphor: bool = True,
    scene_count: int = 0,
) -> Dict:
    """Predict audience retention using heuristics.

    Based on YouTube-style engagement research:
    - Hook in first 5 seconds: +15%
    - Optimal WPM (120-160): +10%
    - Visual metaphors: +8%
    - Scene variety (5-8 scenes): +7%
    - Optimal readability (FRE 60-80): +5%
    - Penalties: fast WPM, high fog index, no hook
    """
    base_retention = 0.50  # 50% baseline for educational content

    # Hook bonus
    hook_bonus = 0.15 if has_hook else 0.0

    # Visual metaphor bonus
    metaphor_bonus = 0.08 if has_visual_metaphor else 0.0

    # Scene variety
    variety_bonus = 0.0
    if 5 <= scene_count <= 8:
        variety_bonus = 0.07
    elif scene_count < 3:
        variety_bonus = -0.10  # Too few scenes
    elif scene_count > 12:
        variety_bonus = -0.05  # Too many scenes

    # Pacing score
    optimal_scenes = sum(1 for p in scene_pacing if p["pace"] == "optimal")
    slow_scenes = sum(1 for p in scene_pacing if p["pace"] == "slow")
    fast_scenes = sum(1 for p in scene_pacing if p["pace"] in ("fast", "too_fast"))
    total_scenes = len(scene_pacing) if scene_pacing else 1
    pacing_score = (
        (optimal_scenes / total_scenes * 0.10)
        - (slow_scenes / total_scenes * 0.03)
        - (fast_scenes / total_scenes * 0.08)
    )

    # Readability
    readability = analyze_script_readability(script_text)
    fre = readability["flesch_reading_ease"]
    readability_bonus = 0.0
    if 60 <= fre <= 80:
        readability_bonus = 0.05
    elif fre < 40:
        readability_bonus = -0.10  # Too hard
    elif fre > 90:
        readability_bonus = -0.03  # Too simple

    predicted_retention = (
        base_retention
        + hook_bonus
        + metaphor_bonus
        + variety_bonus
        + pacing_score
        + readability_bonus
    )
    predicted_retention = max(0.10, min(0.95, predicted_retention))

    return {
        "predicted_retention": round(predicted_retention * 100, 1),
        "base_retention": round(base_retention * 100, 1),
        "hook_bonus": round(hook_bonus * 100, 1),
        "metaphor_bonus": round(metaphor_bonus * 100, 1),
        "variety_bonus": round(variety_bonus * 100, 1),
        "pacing_score": round(pacing_score * 100, 1),
        "readability_bonus": round(readability_bonus * 100, 1),
        "readability": readability,
        "breakdown": {
            "optimal_pacing_pct": round(optimal_scenes / total_scenes * 100, 1),
            "fast_pacing_pct": round(fast_scenes / total_scenes * 100, 1),
            "slow_pacing_pct": round(slow_scenes / total_scenes * 100, 1),
        },
    }


def analyze_full_script(
    scenes: List[Dict],
    scene_durations: List[float],
    topic: str = "",
) -> Dict:
    """Complete quality analysis of a video script."""
    full_text = " ".join(s.get("text", "") for s in scenes)
    pacing = analyze_pacing(scenes, scene_durations)

    # Check for hook heuristic: first 10 words contain question or strong verb
    first_scene_text = scenes[0].get("text", "") if scenes else ""
    first_ten = " ".join(first_scene_text.split()[:10]).lower()
    has_hook = any(
        marker in first_ten
        for marker in ("why", "how", "what if", "imagine", "did you", "ever", "wrong", "surprising")
    )

    # Check for visual metaphor heuristic
    has_metaphor = any(
        marker in full_text.lower()
        for marker in ("like a", "imagine a", "picture a", "think of", "similar to")
    )

    retention = compute_retention_score(
        full_text,
        pacing,
        has_hook=has_hook,
        has_visual_metaphor=has_metaphor,
        scene_count=len(scenes),
    )

    return {
        "topic": topic,
        "scene_count": len(scenes),
        "total_words": len(re.findall(r"\b\w+\b", full_text)),
        "total_duration": round(sum(scene_durations), 2),
        "overall_wpm": round(estimate_wpm(full_text, sum(scene_durations)), 1),
        "readability": retention["readability"],
        "pacing": pacing,
        "retention_prediction": {
            "predicted_retention_pct": retention["predicted_retention"],
            "has_hook": has_hook,
            "has_visual_metaphor": has_metaphor,
            "scoring_breakdown": {
                "base": retention["base_retention"],
                "hook": retention["hook_bonus"],
                "metaphor": retention["metaphor_bonus"],
                "variety": retention["variety_bonus"],
                "pacing": retention["pacing_score"],
                "readability": retention["readability_bonus"],
            },
        },
        "suggestions": _generate_suggestions(retention, pacing, has_hook, has_metaphor),
    }


def _generate_suggestions(
    retention: Dict, pacing: List[Dict], has_hook: bool, has_metaphor: bool
) -> List[str]:
    """Generate human-readable improvement suggestions."""
    suggestions = []
    if not has_hook:
        suggestions.append(
            "HOOK: Scene 1 should open with a surprising question or paradox, "
            "not a definition. Try 'Why does...?' or 'What if...?'"
        )
    if not has_metaphor:
        suggestions.append(
            "METAPHOR: Add a visual analogy. Compare abstract concepts to "
            "concrete objects (e.g., 'like a...')."
        )

    fast_scenes = [p for p in pacing if p["pace"] in ("fast", "too_fast")]
    if fast_scenes:
        idx_list = ", ".join(str(p["scene_index"]) for p in fast_scenes[:3])
        suggestions.append(
            f"PACING: Scenes {idx_list} are too fast. Consider splitting or extending duration."
        )

    slow_scenes = [p for p in pacing if p["pace"] == "slow"]
    if slow_scenes:
        idx_list = ", ".join(str(p["scene_index"]) for p in slow_scenes[:3])
        suggestions.append(
            f"PACING: Scenes {idx_list} are slow. Consider tightening narration."
        )

    if retention["predicted_retention"] < 55:
        suggestions.append(
            "OVERALL: Predicted retention is low. Consider adding more visual variety, "
            "a stronger hook, or simplifying language."
        )

    return suggestions
