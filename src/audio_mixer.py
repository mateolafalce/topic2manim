"""Audio mixing: background music and sound effects for educational videos.

Uses MoviePy to mix narration with background tracks and optional SFX.
"""

import os
import random
from typing import Dict, List, Optional

try:
    from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    from moviepy.audio.fx import MultiplyVolume
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


# Mood-to-music mapping (placeholder paths - user should populate with actual files)
MUSIC_LIBRARY = {
    "calm": [
        "media/audio/music/calm_1.mp3",
        "media/audio/music/calm_2.mp3",
    ],
    "upbeat": [
        "media/audio/music/upbeat_1.mp3",
        "media/audio/music/upbeat_2.mp3",
    ],
    "dramatic": [
        "media/audio/music/dramatic_1.mp3",
        "media/audio/music/dramatic_2.mp3",
    ],
    "mysterious": [
        "media/audio/music/mysterious_1.mp3",
    ],
    "playful": [
        "media/audio/music/playful_1.mp3",
    ],
}

# Sound effect library
SFX_LIBRARY = {
    "pop": "media/audio/sfx/pop.mp3",
    "whoosh": "media/audio/sfx/whoosh.mp3",
    "ding": "media/audio/sfx/ding.mp3",
    "click": "media/audio/sfx/click.mp3",
    "swoosh": "media/audio/sfx/swoosh.mp3",
    "thud": "media/audio/sfx/thud.mp3",
}

# Topic-to-mood mapping (simple heuristic)
def infer_mood(topic: str, visual_events: Optional[List[str]] = None) -> str:
    """Infer background music mood from topic and visual events."""
    topic_lower = topic.lower()
    events = set(v.lower() for v in (visual_events or []))

    # Check visual events first
    if any(e in events for e in ("show_explosion", "show_collision", "show_break")):
        return "dramatic"
    if any(e in events for e in ("show_game", "show_play", "show_animation")):
        return "playful"
    if any(e in events for e in ("show_mystery", "show_question", "show_puzzle")):
        return "mysterious"

    # Check topic keywords
    dramatic_keywords = ("crisis", "disaster", "war", "death", "danger", "emergency")
    if any(k in topic_lower for k in dramatic_keywords):
        return "dramatic"

    playful_keywords = ("game", "puzzle", "fun", "play", "joke", "cartoon")
    if any(k in topic_lower for k in playful_keywords):
        return "playful"

    mysterious_keywords = ("mystery", "unknown", "secret", "quantum", "black hole", "infinity")
    if any(k in topic_lower for k in mysterious_keywords):
        return "mysterious"

    upbeat_keywords = ("success", "growth", "innovation", "breakthrough", "discovery")
    if any(k in topic_lower for k in upbeat_keywords):
        return "upbeat"

    return "calm"


def pick_music_track(mood: str) -> Optional[str]:
    """Pick a random music track for the given mood."""
    tracks = MUSIC_LIBRARY.get(mood, [])
    available = [t for t in tracks if os.path.exists(t)]
    if available:
        return random.choice(available)
    return None


def mix_audio_with_music(
    narration_path: str,
    output_path: str,
    topic: str = "",
    visual_events: Optional[List[str]] = None,
    music_volume_db: float = -22,
    music_track: Optional[str] = None,
    duration: Optional[float] = None,
) -> bool:
    """Mix narration with background music.

    Args:
        narration_path: Path to narration MP3.
        output_path: Where to write mixed MP3.
        topic: Used to infer mood if music_track not provided.
        visual_events: Additional mood signals.
        music_volume_db: Background music volume (negative dB).
        music_track: Specific track path, or None to auto-pick.
        duration: Target duration. If music is shorter, it loops.

    Returns:
        True if successful.
    """
    if not MOVIEPY_AVAILABLE:
        print("[WARN] MoviePy not available for audio mixing")
        return False

    if not os.path.exists(narration_path):
        print(f"[WARN] Narration not found: {narration_path}")
        return False

    try:
        narration = AudioFileClip(narration_path)
        target_duration = duration or narration.duration

        # Pick music
        if not music_track:
            mood = infer_mood(topic, visual_events)
            music_track = pick_music_track(mood)

        if not music_track or not os.path.exists(music_track):
            # No music available, just copy narration
            narration.write_audiofile(output_path, fps=44100, nbytes=2, codec="libmp3lame")
            narration.close()
            return True

        music = AudioFileClip(music_track)

        # Loop music if shorter than target
        if music.duration < target_duration:
            loops = int(target_duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops).subclipped(0, target_duration)
        else:
            music = music.subclipped(0, target_duration)

        # Fade music in/out
        music = music.with_effects([
            MultiplyVolume(music_volume_db),
        ])

        # Mix
        mixed = CompositeAudioClip([narration, music])
        mixed.write_audiofile(output_path, fps=44100, nbytes=2, codec="libmp3lame")

        narration.close()
        music.close()
        mixed.close()
        return True

    except Exception as exc:
        print(f"[WARN] Audio mixing failed: {exc}")
        # Fallback: copy narration
        try:
            import shutil
            shutil.copy(narration_path, output_path)
            return True
        except Exception:
            return False


def add_sound_effects(
    base_audio_path: str,
    output_path: str,
    sfx_events: List[Dict],
) -> bool:
    """Add sound effects at specific timestamps.

    Args:
        base_audio_path: Path to existing audio (narration + music).
        output_path: Where to write mixed audio.
        sfx_events: List of dicts with keys:
            - sfx_id: key from SFX_LIBRARY
            - timestamp: when to play (seconds)
            - volume_db: optional volume adjustment (default -8)

    Returns:
        True if successful.
    """
    if not MOVIEPY_AVAILABLE:
        return False

    if not os.path.exists(base_audio_path):
        return False

    try:
        base = AudioFileClip(base_audio_path)
        clips = [base]

        for event in sfx_events:
            sfx_id = event.get("sfx_id", "")
            sfx_path = SFX_LIBRARY.get(sfx_id)
            if not sfx_path or not os.path.exists(sfx_path):
                continue

            timestamp = float(event.get("timestamp", 0))
            volume_db = float(event.get("volume_db", -8))

            sfx = AudioFileClip(sfx_path)
            sfx = sfx.with_effects([MultiplyVolume(volume_db)])
            # Position at timestamp
            sfx = sfx.with_start(timestamp)
            clips.append(sfx)

        mixed = CompositeAudioClip(clips)
        mixed.write_audiofile(output_path, fps=44100, nbytes=2, codec="libmp3lame")

        base.close()
        mixed.close()
        return True

    except Exception as exc:
        print(f"[WARN] SFX mixing failed: {exc}")
        try:
            import shutil
            shutil.copy(base_audio_path, output_path)
            return True
        except Exception:
            return False


def map_visual_events_to_sfx(visual_events: List[str], scene_start_time: float) -> List[Dict]:
    """Map visual event IDs to sound effects with estimated timestamps."""
    sfx_events = []
    event_sfx_map = {
        "show_title": ("whoosh", 0.5),
        "show_equation": ("pop", 0.3),
        "highlight_term": ("ding", 0.0),
        "transform_shape": ("swoosh", 0.0),
        "step_reveal": ("click", 0.1),
        "show_graph": ("pop", 0.2),
    }

    current_time = scene_start_time
    for event in visual_events:
        if event.lower() in event_sfx_map:
            sfx_id, delay = event_sfx_map[event.lower()]
            sfx_events.append(
                {
                    "sfx_id": sfx_id,
                    "timestamp": current_time + delay,
                    "volume_db": -10,
                }
            )
        # Advance time roughly
        current_time += 1.5

    return sfx_events
