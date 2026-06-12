"""Auto-caption generation for educational videos.

Generates SRT subtitle files from script text with estimated timestamps,
then burns them into the final video using ffmpeg.
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _estimate_word_durations(text: str, total_duration: float, wpm: float = 140) -> List[float]:
    """Estimate per-word duration based on total scene duration."""
    words = text.split()
    if not words:
        return []
    total_words = len(words)
    base_duration = total_duration / total_words
    durations = []
    for word in words:
        # Longer words get slightly more time; punctuation pauses
        factor = 1.0
        if len(word) > 8:
            factor = 1.2
        if word.endswith((",", ":", ";")):
            factor = 1.3
        if word.endswith((".", "!", "?")):
            factor = 1.5
        durations.append(base_duration * factor)
    # Normalize to total duration
    current_total = sum(durations)
    if current_total > 0:
        scale = total_duration / current_total
        durations = [d * scale for d in durations]
    return durations


def generate_srt(
    scenes: List[Dict],
    scene_durations: Optional[List[float]] = None,
    output_path: str = "output.srt",
    wpm: float = 140,
) -> str:
    """Generate an SRT subtitle file from script scenes.

    Args:
        scenes: List of scene dicts with 'text' key.
        scene_durations: Optional list of per-scene durations in seconds.
        output_path: Where to write the SRT file.
        wpm: Words per minute for timing estimation.

    Returns:
        Path to the generated SRT file.
    """
    lines = []
    cue_number = 1
    current_time = 0.0

    for i, scene in enumerate(scenes):
        text = scene.get("text", "").strip()
        if not text:
            continue

        if scene_durations and i < len(scene_durations):
            scene_duration = scene_durations[i]
        else:
            word_count = len(text.split())
            scene_duration = (word_count / wpm) * 60

        # Split text into chunks of ~8-12 words for readability
        words = text.split()
        chunk_size = 10
        chunks = [words[j : j + chunk_size] for j in range(0, len(words), chunk_size)]

        chunk_durations = _estimate_word_durations(text, scene_duration, wpm)
        word_idx = 0

        for chunk in chunks:
            chunk_text = " ".join(chunk)
            # Calculate chunk duration from word durations
            chunk_word_count = len(chunk)
            chunk_duration = sum(
                chunk_durations[word_idx + k]
                for k in range(chunk_word_count)
                if word_idx + k < len(chunk_durations)
            )
            word_idx += chunk_word_count

            start = current_time
            end = current_time + chunk_duration

            lines.append(str(cue_number))
            lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
            lines.append(chunk_text)
            lines.append("")

            cue_number += 1
            current_time = end

    srt_content = "\n".join(lines)
    Path(output_path).write_text(srt_content, encoding="utf-8")
    return output_path


def burn_captions_ffmpeg(
    video_path: str,
    srt_path: str,
    output_path: str,
    style: Optional[Dict] = None,
) -> bool:
    """Burn captions into video using ffmpeg.

    Args:
        video_path: Path to input MP4.
        srt_path: Path to SRT file.
        output_path: Where to write captioned MP4.
        style: Optional style dict with font, size, color, bg_color.

    Returns:
        True if successful.
    """
    style = style or {}
    font = style.get("font", "Arial")
    font_size = style.get("font_size", 24)

    # ffmpeg subtitle burn with styling
    filter_str = (
        f"subtitles={srt_path}:force_style='"
        f"FontName={font},"
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,'"  # White
        f"OutlineColour=&H00000000,"  # Black outline
        f"Outline=2,"
        f"BorderStyle=4,"  # Background box
        f"BackColour=&H80000000'"  # Semi-transparent black bg
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", filter_str,
        "-c:a", "copy",
        output_path,
    ]

    try:
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True
        print(f"[WARN] Caption burn failed: {result.stderr[:500]}")
        return False
    except Exception as exc:
        print(f"[WARN] Caption burn error: {exc}")
        return False


def generate_and_burn_captions(
    video_path: str,
    scenes: List[Dict],
    output_path: str,
    scene_durations: Optional[List[float]] = None,
    style: Optional[Dict] = None,
    temp_dir: Optional[str] = None,
) -> bool:
    """One-shot: generate SRT from scenes and burn into video.

    Returns True if successful.
    """
    temp_dir = temp_dir or os.path.dirname(video_path) or "."
    srt_path = os.path.join(temp_dir, f"captions_{os.path.basename(video_path)}.srt")

    try:
        generate_srt(scenes, scene_durations, srt_path)
        return burn_captions_ffmpeg(video_path, srt_path, output_path, style)
    except Exception as exc:
        print(f"[WARN] Caption generation failed: {exc}")
        return False
