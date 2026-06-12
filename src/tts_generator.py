import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from openai import OpenAI

from env_loader import load_app_env, get_env

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _safe_project_path(path: str, label: str = "path") -> str:
    """Validate that a path is within the project root (prevents traversal attacks)."""
    if not path or not isinstance(path, str):
        raise ValueError(f"Invalid {label}: must be a non-empty string")
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(_PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Invalid {label}: must be inside project directory")
    if "\x00" in path:
        raise ValueError(f"Invalid {label}: contains null bytes")
    return str(resolved)


ELEVENLABS_MAX_CHARS = 4500
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
TTS_PROVIDER_IDS = ("openai", "elevenlabs")

OPENAI_VOICES = [
    {"voice_id": "alloy", "name": "Alloy", "labels": {"gender": "neutral"}},
    {"voice_id": "echo", "name": "Echo", "labels": {"gender": "male"}},
    {"voice_id": "fable", "name": "Fable", "labels": {"gender": "neutral"}},
    {"voice_id": "onyx", "name": "Onyx", "labels": {"gender": "male"}},
    {"voice_id": "nova", "name": "Nova", "labels": {"gender": "female"}},
    {"voice_id": "shimmer", "name": "Shimmer", "labels": {"gender": "female"}},
]


def get_audio_duration(audio_path):
    """Gets the duration of an audio file using ffprobe."""
    try:
        audio_path = _safe_project_path(audio_path, "audio_path")
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return float(result.stdout.strip())
        print(f"  [WARNING] Could not get duration for {audio_path}")
        return None
    except Exception as exc:
        print(f"  [WARNING] Error getting audio duration: {exc}")
        return None


def _has_openai_tts_credentials():
    return bool(get_env("OPENAI_API_KEY"))


def _has_elevenlabs_tts_credentials():
    return bool(get_env("ELEVENLABS_API_KEY"))


def _default_elevenlabs_voice_id():
    return get_env("ELEVENLABS_VOICE_ID")


def get_default_tts_voices():
    return {
        "openai": get_env("VOICE", "alloy"),
        "elevenlabs": _default_elevenlabs_voice_id(),
    }


def _is_displayable_voice_name(name: str) -> bool:
    """Hide obvious test/junk voice names from the picker."""
    cleaned = (name or "").strip()
    if len(cleaned) < 2:
        return False
    if cleaned.lower() in {"test", "default", "voice"}:
        return False
    letters = re.sub(r"[^A-Za-z]", "", cleaned)
    if len(letters) >= 6 and letters.isupper() and " " not in cleaned:
        vowels = sum(1 for ch in letters if ch.lower() in "aeiou")
        if vowels / max(len(letters), 1) < 0.2:
            return False
    if re.fullmatch(r"(.)\1{3,}", cleaned):
        return False
    return True


def list_elevenlabs_voices():
    """Fetch available voices from the ElevenLabs API."""
    api_key = get_env("ELEVENLABS_API_KEY")
    if not api_key:
        return []

    request = urllib.request.Request(
        ELEVENLABS_VOICES_URL,
        headers={"xi-api-key": api_key},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        print(f"[WARNING] Could not fetch ElevenLabs voices: {exc}")
        return []

    voices = []
    for item in body.get("voices", []):
        voice_id = item.get("voice_id")
        name = item.get("name") or voice_id
        if not voice_id or not _is_displayable_voice_name(name):
            continue
        labels = item.get("labels") or {}
        voices.append(
            {
                "voice_id": voice_id,
                "name": name,
                "labels": labels,
                "preview_url": item.get("preview_url"),
            }
        )

    return sorted(voices, key=lambda voice: voice["name"].lower())


def list_provider_voices(provider_id):
    """Return selectable voices for a TTS provider."""
    provider_id = (provider_id or "").lower().strip()
    if provider_id == "elevenlabs":
        return list_elevenlabs_voices()
    if provider_id == "openai":
        return [
            {
                "voice_id": voice["voice_id"],
                "name": voice["name"],
                "labels": voice.get("labels", {}),
            }
            for voice in OPENAI_VOICES
        ]
    return []


def get_all_tts_providers():
    return list(TTS_PROVIDER_IDS)


def get_available_tts_providers():
    """Returns TTS providers that have the required credentials configured."""
    providers = []
    if _has_openai_tts_credentials():
        providers.append("openai")
    if _has_elevenlabs_tts_credentials():
        providers.append("elevenlabs")
    return providers


def _build_openai_config(voice_override=None):
    return {
        "provider": "openai",
        "client": OpenAI(api_key=get_env("OPENAI_API_KEY")),
        "model": get_env("TTS_MODEL", "tts-1"),
        "voice": voice_override or get_env("VOICE", "alloy"),
    }


def _build_elevenlabs_config(voice_override=None):
    stability = float(get_env("ELEVENLABS_STABILITY", "0.5"))
    similarity_boost = float(get_env("ELEVENLABS_SIMILARITY_BOOST", "0.75"))
    voice_id = voice_override or _default_elevenlabs_voice_id()
    if not voice_id:
        raise ValueError(
            "ElevenLabs voice not selected. Choose a voice in the UI or set "
            "ELEVENLABS_VOICE_ID in .env"
        )

    return {
        "provider": "elevenlabs",
        "api_key": get_env("ELEVENLABS_API_KEY"),
        "voice_id": voice_id,
        "model_id": get_env("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "output_format": get_env("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        },
    }


def setup_tts_config(preference="auto", voice_override=None):
    """
    Resolve TTS provider configuration.

    preference: auto | openai | elevenlabs

    Returns a provider config dict, or None when preference is auto and no provider
    is configured. Raises ValueError when a specific provider is requested but
    credentials are missing.
    """
    load_app_env()
    preference = (preference or "auto").lower().strip()
    env_default = os.getenv("TTS_PROVIDER", "auto").lower().strip()
    effective_preference = preference if preference != "auto" else env_default

    if effective_preference == "elevenlabs":
        if not _has_elevenlabs_tts_credentials():
            raise ValueError("ElevenLabs TTS selected but ELEVENLABS_API_KEY is not configured")
        return _build_elevenlabs_config(voice_override)

    if effective_preference == "openai":
        if not _has_openai_tts_credentials():
            raise ValueError("OpenAI TTS selected but OPENAI_API_KEY is not configured")
        return _build_openai_config(voice_override)

    # Auto: use whichever provider is configured.
    has_openai = _has_openai_tts_credentials()
    has_elevenlabs = _has_elevenlabs_tts_credentials()

    if has_openai and not has_elevenlabs:
        return _build_openai_config(voice_override)
    if has_elevenlabs and not has_openai:
        return _build_elevenlabs_config(voice_override)
    if has_openai and has_elevenlabs:
        if env_default == "elevenlabs":
            return _build_elevenlabs_config(voice_override)
        return _build_openai_config(voice_override)

    return None


def _split_text_for_tts(text, max_chars=ELEVENLABS_MAX_CHARS):
    """Split long narration into chunks that fit provider limits."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""

    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        part = part.strip()
        if not part:
            continue

        candidate = f"{current} {part}".strip() if current else part
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        if len(part) <= max_chars:
            current = part
        else:
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks or [text[:max_chars]]


def concatenate_audio_fragments(audio_paths, output_path="media/audio.mp3"):
    """Concatenate multiple audio fragments into a single MP3 file using ffmpeg."""
    safe_paths = []
    for p in audio_paths:
        try:
            safe_paths.append(_safe_project_path(p, "audio_path"))
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            continue

    valid_paths = [path for path in safe_paths if os.path.exists(path)]
    if not valid_paths:
        print("[ERROR] No audio fragments to concatenate")
        return False

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    list_file = f"{output_path}.list.txt"
    with open(list_file, "w", encoding="utf-8") as handle:
        for audio_path in valid_paths:
            abs_path = os.path.abspath(audio_path).replace("\\", "/")
            handle.write(f"file '{abs_path}'\n")

    try:
        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            output_path,
            "-y",
        ]
        print(f"\n  Concatenating {len(valid_paths)} audio fragments...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print(f"  [OK] Final audio created: {output_path}")
            return True

        print("  [ERROR] Error concatenating audio:")
        print(result.stderr)
        return False
    except Exception as exc:
        print(f"  [ERROR] Error: {exc}")
        return False
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def _generate_openai_fragment(client, text, audio_path, tts_model, voice):
    response = client.audio.speech.create(
        model=tts_model,
        voice=voice,
        input=text,
    )
    response.stream_to_file(audio_path)


def _generate_elevenlabs_fragment(
    api_key, voice_id, text, audio_path, model_id, output_format, voice_settings
):
    url = f"{ELEVENLABS_API_URL}/{voice_id}?output_format={output_format}"
    payload = json.dumps(
        {
            "text": text,
            "model_id": model_id,
            "voice_settings": voice_settings,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        audio_bytes = response.read()

    with open(audio_path, "wb") as handle:
        handle.write(audio_bytes)


def generate_audio_fragment(tts_config, text, index, output_dir="media/audio_fragments"):
    """
    Generate one scene's audio fragment using the configured TTS provider.

    Returns (audio_path, duration) or (None, None) on failure.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        provider = tts_config["provider"]
        audio_path = os.path.join(output_dir, f"fragment_{index}.mp3")

        print(f"  Generating audio fragment {index} ({provider})...")
        print(f"    Text preview: {text[:80]}...")

        if provider == "openai":
            _generate_openai_fragment(
                client=tts_config["client"],
                text=text,
                audio_path=audio_path,
                tts_model=tts_config["model"],
                voice=tts_config["voice"],
            )
        elif provider == "elevenlabs":
            chunks = _split_text_for_tts(text)
            if len(chunks) == 1:
                _generate_elevenlabs_fragment(
                    api_key=tts_config["api_key"],
                    voice_id=tts_config["voice_id"],
                    text=chunks[0],
                    audio_path=audio_path,
                    model_id=tts_config["model_id"],
                    output_format=tts_config["output_format"],
                    voice_settings=tts_config["voice_settings"],
                )
            else:
                chunk_paths = []
                with tempfile.TemporaryDirectory(prefix="tts_chunks_") as temp_dir:
                    for chunk_index, chunk in enumerate(chunks, 1):
                        chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index}.mp3")
                        _generate_elevenlabs_fragment(
                            api_key=tts_config["api_key"],
                            voice_id=tts_config["voice_id"],
                            text=chunk,
                            audio_path=chunk_path,
                            model_id=tts_config["model_id"],
                            output_format=tts_config["output_format"],
                            voice_settings=tts_config["voice_settings"],
                        )
                        chunk_paths.append(chunk_path)

                    if not concatenate_audio_fragments(chunk_paths, audio_path):
                        return None, None
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

        duration = get_audio_duration(audio_path)
        if duration:
            print(f"  [OK] Audio fragment saved: {audio_path} (duration: {duration:.2f}s)")
        else:
            print(f"  [OK] Audio fragment saved: {audio_path} (duration: unknown)")

        return audio_path, duration

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"  [ERROR] ElevenLabs HTTP {exc.code} for fragment {index}: {error_body}")
        return None, None
    except Exception as exc:
        print(f"  [ERROR] Error generating audio fragment {index}: {exc}")
        return None, None


def generate_complete_audio(video_data, tts_config):
    """
    Generate complete narration audio for all scenes.

    Returns (audio_path, durations_dict) where durations_dict maps scene index to duration.
    """
    if not tts_config:
        return None, {}

    provider = tts_config["provider"]
    print(f"\n{'=' * 80}")
    print("GENERATING AUDIO WITH TTS")
    print(f"{'=' * 80}")
    print(f"Provider: {provider}")

    if provider == "openai":
        print(f"Model: {tts_config['model']}")
        print(f"Voice: {tts_config['voice']}")
    else:
        voice_name = tts_config.get("voice_name") or tts_config["voice_id"]
        print(f"Model: {tts_config['model_id']}")
        print(f"Voice: {voice_name} ({tts_config['voice_id']})")

    print(f"Scenes: {len(video_data)}\n")

    audio_fragments = []
    audio_durations = {}

    for index, scene_data in enumerate(video_data, 1):
        text = scene_data.get("text", "")
        if not text:
            print(f"  [WARNING] Scene {index} has no text, skipping...")
            continue

        audio_path, duration = generate_audio_fragment(
            tts_config=tts_config,
            text=text,
            index=index,
        )

        if audio_path and os.path.exists(audio_path):
            audio_fragments.append(audio_path)
            if duration:
                audio_durations[index] = duration
        else:
            print(f"  [WARNING] Could not generate audio for scene {index}")

    if not audio_fragments:
        print("\n[ERROR] No audio fragments were generated\n")
        return None, {}

    print(f"\n{'=' * 80}")
    print(f"CONCATENATING {len(audio_fragments)} AUDIO FRAGMENTS")
    print(f"{'=' * 80}")

    output_path = "media/audio.mp3"
    if concatenate_audio_fragments(audio_fragments, output_path):
        print(f"\n[OK] Complete audio generated: {output_path}\n")
        return output_path, audio_durations

    print("\n[ERROR] Failed to concatenate audio fragments\n")
    return None, {}
