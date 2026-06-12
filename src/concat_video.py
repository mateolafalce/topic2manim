# ISS-0001: sanitize subprocess inputs, use tempfile for concurrency safety
import subprocess
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _safe_project_path(path: str, label: str = "path") -> str:
    """Validate that a path is within the project root (prevents traversal attacks)."""
    if not path or not isinstance(path, str):
        raise ValueError(f"Invalid {label}: must be a non-empty string")
    resolved = Path(path).resolve()
    # Block absolute paths outside project and traversal sequences
    try:
        resolved.relative_to(_PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Invalid {label}: must be inside project directory")
    # Reject paths with null bytes or control chars
    if "\x00" in path:
        raise ValueError(f"Invalid {label}: contains null bytes")
    return str(resolved)


def _get_video_duration(path: str) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def sanitize_filename(filename):
    """Remove or replace problematic characters from filenames"""
    # Remove apostrophes, question marks, and other special characters
    # Replace with underscores or remove them
    sanitized = re.sub(r"['\"\?!:;,\(\)\[\]\{\}]", "", filename)
    # Replace multiple underscores with single underscore
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized


def compile_video(file_path, class_name, topic_slug, index, quality="standard"):
    """Compiles the video using Manim

    Returns:
        tuple: (video_path, error_message) - video_path is None if failed, error_message is None if success
    """
    from video_settings import normalize_video_settings

    quality_preset = normalize_video_settings({"quality": quality})["quality_preset"]
    manim_flag = quality_preset["manim_flag"]
    output_subdir = quality_preset["output_subdir"]

    try:
        file_path = _safe_project_path(file_path, "file_path")
    except ValueError as exc:
        return None, str(exc)

    if not os.path.exists(file_path):
        return None, f"Source file not found: {file_path}"
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", class_name):
        return None, f"Invalid class name: {class_name}"

    try:
        cmd = ["manim", manim_flag, file_path, class_name]
        print(f"\nCompiling: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minutes timeout
        )

        if result.returncode == 0:
            print("[OK] Video compiled successfully")
            # Manim creates directory based on the Python filename (without extension)
            # Extract filename without extension from file_path
            filename_without_ext = os.path.splitext(os.path.basename(file_path))[0]
            video_path = f"media/videos/{filename_without_ext}/{output_subdir}/{class_name}.mp4"
            return video_path, None
        else:
            error_msg = result.stderr
            print("[ERROR] Error compiling video:")
            print(error_msg)
            return None, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "Timeout: Compilation took more than 5 minutes"
        print(f"[ERROR] {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Error: {error_msg}")
        return None, error_msg


def _concatenate_simple(video_paths, output_path):
    """Fallback: join videos with hard cuts using ffmpeg concat demuxer."""
    list_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            list_file = f.name
            for video_path in video_paths:
                if os.path.exists(video_path):
                    f.write(f"file '../{video_path}'\n")

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
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    finally:
        if list_file and os.path.exists(list_file):
            os.remove(list_file)


def concatenate_videos(video_paths, output_path, transition_duration=0.3):
    """Joins all videos into one using ffmpeg with fade transitions between scenes.

    Args:
        video_paths: List of video file paths.
        output_path: Output file path.
        transition_duration: Duration of fade in/out at scene boundaries (seconds).
                             Set to 0 for hard cuts (fallback behaviour).
    """
    if not video_paths:
        print("[ERROR] No videos to concatenate")
        return False

    # Validate all input paths
    safe_paths = []
    for vp in video_paths:
        try:
            safe_paths.append(_safe_project_path(vp, "video_path"))
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return False

    # Create media folder if it doesn't exist
    os.makedirs("media", exist_ok=True)

    if transition_duration <= 0 or len(safe_paths) == 1:
        print("\n  Concatenating videos (simple)...")
        ok = _concatenate_simple(safe_paths, output_path)
        if ok:
            print(f"[OK] Final video created: {output_path}")
        else:
            print("[ERROR] Error concatenating videos")
        return ok

    # Get durations for each video
    durations = []
    for path in safe_paths:
        d = _get_video_duration(path)
        if d is None:
            print(f"[WARN] Could not get duration for {path}, falling back to simple concat")
            return _concatenate_simple(safe_paths, output_path)
        durations.append(d)

    # Build filter_complex for fade transitions
    # Each video gets fade-out at end (except last) and fade-in at start (except first)
    filters = []
    inputs = []
    for i, (path, d) in enumerate(zip(safe_paths, durations)):
        fade_filters = []
        # Fade in at start (except first scene)
        if i > 0:
            fade_filters.append(f"fade=t=in:st=0:d={transition_duration}")
        # Fade out at end (except last scene)
        if i < len(safe_paths) - 1:
            fade_out_start = max(0.1, d - transition_duration)
            fade_filters.append(f"fade=t=out:st={fade_out_start}:d={transition_duration}")

        if fade_filters:
            filters.append(f"[{i}:v]{','.join(fade_filters)}[v{i}]")
            inputs.append(f"[v{i}]")
        else:
            inputs.append(f"[{i}:v]")

    n = len(safe_paths)
    filters.append(f"{''.join(inputs)}concat=n={n}:v=1:a=0[outv]")
    filter_complex = ";".join(filters)

    # Build input args
    input_args = []
    for path in safe_paths:
        input_args.extend(["-i", path])

    cmd = [
        "ffmpeg",
        "-y",
        *input_args,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        output_path,
    ]

    print(f"\n  Concatenating videos with {transition_duration}s fade transitions...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] Final video created: {output_path}")
        return True
    else:
        print("[WARN] Transition concat failed, falling back to simple concat:")
        print(result.stderr[:500])
        ok = _concatenate_simple(safe_paths, output_path)
        if ok:
            print(f"[OK] Final video created (simple): {output_path}")
        else:
            print("[ERROR] Error concatenating videos")
        return ok


def merge_video_and_audio(video_path, audio_path, output_path):
    """
    Merges video and audio files into a single MP4 file using ffmpeg

    Args:
        video_path: Path to the video file (without audio)
        audio_path: Path to the audio file (MP3)
        output_path: Path for the final merged video

    Returns:
        True if successful, False otherwise
    """
    try:
        video_path = _safe_project_path(video_path, "video_path")
        audio_path = _safe_project_path(audio_path, "audio_path")
        output_path = _safe_project_path(output_path, "output_path")
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return False

    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        return False

    if not os.path.exists(audio_path):
        print(f"[ERROR] Audio file not found: {audio_path}")
        return False

    try:
        cmd = [
            "ffmpeg",
            "-i",
            video_path,  # Input video
            "-i",
            audio_path,  # Input audio
            "-c:v",
            "copy",  # Copy video codec (no re-encoding)
            "-c:a",
            "aac",  # Encode audio to AAC
            "-map",
            "0:v:0",  # Map video from first input
            "-map",
            "1:a:0",  # Map audio from second input
            output_path,
            "-y",  # Overwrite if exists
        ]

        print(f"\n{'='*80}")
        print("MERGING VIDEO AND AUDIO")
        print(f"{'='*80}")
        print(f"Video: {video_path}")
        print(f"Audio: {audio_path}")
        print(f"Output: {output_path}\n")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[OK] Final video with audio created: {output_path}\n")
            return True
        else:
            print("[ERROR] Error merging video and audio:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False
