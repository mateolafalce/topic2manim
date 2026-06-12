"""Video assembly pipeline using MoviePy.

Replaces raw ffmpeg concat/merge with a programmable editing pipeline that
can add title cards, end screens, transitions, and audio processing.
"""

import os
from typing import List, Optional

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
    vfx,
)


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _find_font() -> str:
    """Find a usable system font path for TextClip."""
    import os

    candidates = []
    if os.name == "nt":
        win_fonts = r"C:\Windows\Fonts"
        candidates = [
            os.path.join(win_fonts, "arial.ttf"),
            os.path.join(win_fonts, "calibri.ttf"),
            os.path.join(win_fonts, "segoeui.ttf"),
            os.path.join(win_fonts, "verdana.ttf"),
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "Arial"


_FONT_PATH = _find_font()


def _dark_style():
    """Return style dict matching Topic2Manim's dark navy aesthetic."""
    return {
        "bg_color": _hex_to_rgb("#1a1a2e"),
        "title_color": "white",
        "subtitle_color": "#a0a0c0",
        "accent_color": "#6366f1",
        "font": _FONT_PATH,
    }


def make_title_card(
    topic: str,
    subtitle: str = "",
    duration: float = 2.5,
    size: tuple = (1920, 1080),
    fps: int = 30,
) -> VideoFileClip:
    """Generate a title card clip with dark background and centered text."""
    style = _dark_style()
    bg = ColorClip(size=size, color=style["bg_color"], duration=duration)

    clips = [bg]

    title = TextClip(
        text=topic,
        font=style["font"],
        font_size=72,
        color=style["title_color"],
        duration=duration,
    )
    title = title.with_position("center")
    clips.append(title)

    if subtitle:
        sub = TextClip(
            text=subtitle,
            font=style["font"],
            font_size=36,
            color=style["subtitle_color"],
            duration=duration,
        )
        sub = sub.with_position(("center", 620))
        clips.append(sub)

    # Fade in title over first 0.5s
    title = title.with_effects([vfx.FadeIn(0.5)])

    return CompositeVideoClip(clips, size=size).with_fps(fps)


def make_end_screen(
    text: str = "Thanks for watching",
    subtext: str = "Subscribe for more",
    duration: float = 3.0,
    size: tuple = (1920, 1080),
    fps: int = 30,
) -> VideoFileClip:
    """Generate an end screen clip."""
    style = _dark_style()
    bg = ColorClip(size=size, color=style["bg_color"], duration=duration)

    clips = [bg]

    main = TextClip(
        text=text,
        font=style["font"],
        font_size=64,
        color=style["title_color"],
        duration=duration,
    )
    main = main.with_position("center")
    clips.append(main)

    if subtext:
        sub = TextClip(
            text=subtext,
            font=style["font"],
            font_size=32,
            color=style["accent_color"],
            duration=duration,
        )
        sub = sub.with_position(("center", 620))
        clips.append(sub)

    return CompositeVideoClip(clips, size=size).with_fps(fps)


def assemble_final_video(
    scene_paths: List[str],
    output_path: str,
    topic: str = "",
    audio_path: Optional[str] = None,
    video_settings: Optional[dict] = None,
    fps: int = 30,
) -> str:
    """Assemble scenes into a final video with optional title, transitions, end screen, and audio.

    Args:
        scene_paths: Ordered list of rendered scene MP4 paths.
        output_path: Where to write the final MP4.
        topic: Video topic (used for title card).
        audio_path: Path to TTS audio MP3 (optional).
        video_settings: Dict with assembly options.
        fps: Target frame rate.

    Returns:
        The output_path on success.

    Raises:
        ValueError: If no scene paths are provided.
        RuntimeError: If assembly fails.
    """
    if not scene_paths:
        raise ValueError("No scene paths provided")

    video_settings = video_settings or {}

    # Extract assembly options
    enable_title = bool(video_settings.get("enable_title_card", True))
    title_duration = float(video_settings.get("title_card_duration", 2.5))
    enable_end = bool(video_settings.get("enable_end_screen", True))
    end_duration = float(video_settings.get("end_screen_duration", 3.0))
    transition_type = str(video_settings.get("transition_type", "crossfade")).lower()
    transition_duration = float(video_settings.get("transition_duration", 0.3))
    audio_fade = float(video_settings.get("audio_fade_duration", 0.5))

    # Determine target resolution from first scene
    first_clip = VideoFileClip(scene_paths[0])
    target_size = first_clip.size
    target_fps = first_clip.fps or fps
    first_clip.close()

    clips: List[VideoFileClip] = []

    # Title card
    if enable_title and topic:
        title = make_title_card(
            topic=topic,
            duration=title_duration,
            size=target_size,
            fps=target_fps,
        )
        clips.append(title)

    # Load scene clips
    for path in scene_paths:
        if not os.path.exists(path):
            raise RuntimeError(f"Scene file not found: {path}")
        clip = VideoFileClip(path)
        # Ensure all clips match target resolution and fps
        if clip.size != target_size:
            clip = clip.resized(new_size=target_size)
        if clip.fps != target_fps:
            clip = clip.with_fps(target_fps)
        clips.append(clip)

    # End screen
    if enable_end:
        end = make_end_screen(
            duration=end_duration,
            size=target_size,
            fps=target_fps,
        )
        clips.append(end)

    # Apply transitions
    if transition_type != "none" and transition_duration > 0 and len(clips) > 1:
        transitioned = []
        for i, clip in enumerate(clips):
            if i == 0:
                transitioned.append(clip)
            else:
                if transition_type == "crossfade":
                    clip = clip.with_effects([vfx.CrossFadeIn(transition_duration)])
                    prev = transitioned[-1].with_effects([vfx.CrossFadeOut(transition_duration)])
                    transitioned[-1] = prev
                elif transition_type == "fade":
                    clip = clip.with_effects([vfx.FadeIn(transition_duration)])
                    prev = transitioned[-1].with_effects([vfx.FadeOut(transition_duration)])
                    transitioned[-1] = prev
                transitioned.append(clip)
        clips = transitioned

    # Concatenate
    final_video = concatenate_videoclips(clips, method="compose")

    # Add audio if provided
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)

        # Fade audio in/out
        if audio_fade > 0:
            from moviepy import afx

            audio = audio.with_effects([afx.AudioFadeIn(audio_fade)])
            audio = audio.with_effects([afx.AudioFadeOut(min(audio_fade, audio.duration / 2))])

        # If audio is longer than video, trim; if shorter, loop/pad (just trim for now)
        if audio.duration > final_video.duration:
            audio = audio.subclipped(0, final_video.duration)
        elif audio.duration < final_video.duration:
            # Pad with silence
            silence_duration = final_video.duration - audio.duration
            from moviepy import AudioClip

            silence = AudioClip(lambda t: 0, duration=silence_duration, fps=44100)
            audio = concatenate_audioclips([audio, silence])

        final_video = final_video.with_audio(audio)

    # Write output
    final_video.write_videofile(
        output_path,
        fps=target_fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(os.path.dirname(output_path) or ".", "temp_audio.m4a"),
        remove_temp=True,
        threads=4,
        logger=None,
    )

    # Cleanup
    final_video.close()
    for clip in clips:
        clip.close()

    return output_path
