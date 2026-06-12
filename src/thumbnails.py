"""Scene preview thumbnail generation for the video editor.

Generates PNG thumbnails from rendered scene videos or Manim frames.
Uses ffmpeg for frame extraction, PIL for overlay composition.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def extract_frame_ffmpeg(video_path: str, timestamp: float, output_path: str, width: int = 320) -> bool:
    """Extract a single frame from a video at a given timestamp.

    Args:
        video_path: Path to MP4.
        timestamp: Time in seconds.
        output_path: Where to save PNG.
        width: Target width (height auto).

    Returns:
        True if successful.
    """
    if not os.path.exists(video_path):
        return False

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale={width}:-1",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


def find_font_path(name: str = "arial") -> Optional[str]:
    """Find a system font path."""
    if not PIL_AVAILABLE:
        return None

    # Windows font paths
    windows_paths = [
        f"C:/Windows/Fonts/{name}.ttf",
        f"C:/Windows/Fonts/{name}.TTF",
        "C:/Windows/Fonts/Calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for p in windows_paths:
        if os.path.exists(p):
            return p

    # Common Linux paths
    linux_paths = [
        f"/usr/share/fonts/truetype/{name}/{name}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in linux_paths:
        if os.path.exists(p):
            return p

    # macOS
    mac_paths = [
        f"/Library/Fonts/{name}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
    ]
    for p in mac_paths:
        if os.path.exists(p):
            return p

    return None


def add_thumbnail_overlay(
    image_path: str,
    output_path: str,
    scene_number: int,
    duration: float = 0.0,
    style: Optional[Dict] = None,
) -> bool:
    """Add scene number and duration overlay to a thumbnail.

    Args:
        image_path: Source PNG.
        output_path: Destination PNG.
        scene_number: Scene index + 1.
        duration: Scene duration in seconds.
        style: Optional dict with colors/sizes.

    Returns:
        True if successful.
    """
    if not PIL_AVAILABLE:
        return False

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        style = style or {}
        font_path = find_font_path(style.get("font", "arial"))
        font_size = style.get("font_size", 16)
        try:
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Top-left: scene number badge
        badge_text = f"#{scene_number}"
        if duration > 0:
            badge_text += f" ({duration:.1f}s)"

        # Measure text
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding = 6
        badge_w = tw + padding * 2
        badge_h = th + padding * 2
        badge_x = 8
        badge_y = 8

        # Draw semi-transparent badge background
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=4,
            fill=(0, 0, 0, 180),
        )
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # Draw text
        draw.text(
            (badge_x + padding, badge_y + padding - 2),
            badge_text,
            font=font,
            fill=(255, 255, 255, 255),
        )

        img.save(output_path, "PNG")
        return True

    except Exception as exc:
        print(f"[WARN] Thumbnail overlay failed: {exc}")
        return False


def generate_scene_thumbnails(
    scene_videos: List[str],
    output_dir: str,
    scene_durations: Optional[List[float]] = None,
    timestamps: Optional[List[float]] = None,
    width: int = 320,
) -> List[str]:
    """Generate thumbnails for a list of scene videos.

    Args:
        scene_videos: List of MP4 paths.
        output_dir: Directory to save PNGs.
        scene_durations: Optional durations for overlay.
        timestamps: Optional frame timestamps. Defaults to 1s in.
        width: Thumbnail width.

    Returns:
        List of generated thumbnail paths.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for i, video in enumerate(scene_videos):
        if not os.path.exists(video):
            results.append(None)
            continue

        ts = timestamps[i] if timestamps and i < len(timestamps) else 1.0
        raw_path = os.path.join(output_dir, f"scene_{i}_raw.png")
        final_path = os.path.join(output_dir, f"scene_{i}.png")

        ok = extract_frame_ffmpeg(video, ts, raw_path, width)
        if not ok:
            results.append(None)
            continue

        duration = scene_durations[i] if scene_durations and i < len(scene_durations) else 0.0
        add_thumbnail_overlay(raw_path, final_path, i + 1, duration)

        # Clean up raw
        try:
            os.remove(raw_path)
        except Exception:
            pass

        results.append(final_path if os.path.exists(final_path) else None)

    return results


def generate_composite_timeline(
    thumbnails: List[str],
    output_path: str,
    columns: int = 4,
    thumb_width: int = 320,
    gap: int = 8,
    bg_color: tuple = (30, 30, 30),
) -> bool:
    """Generate a composite timeline image from scene thumbnails.

    Args:
        thumbnails: List of PNG paths (may contain None).
        output_path: Where to save composite PNG.
        columns: Number of thumbnails per row.
        thumb_width: Width of each thumbnail.
        gap: Pixel gap between thumbnails.
        bg_color: RGB background color.

    Returns:
        True if successful.
    """
    if not PIL_AVAILABLE:
        return False

    valid = [p for p in thumbnails if p and os.path.exists(p)]
    if not valid:
        return False

    try:
        # Load first to determine height
        first = Image.open(valid[0])
        aspect = first.height / first.width
        thumb_height = int(thumb_width * aspect)

        rows = (len(valid) + columns - 1) // columns
        total_w = columns * thumb_width + (columns + 1) * gap
        total_h = rows * thumb_height + (rows + 1) * gap

        composite = Image.new("RGB", (total_w, total_h), bg_color)

        for idx, path in enumerate(valid):
            row = idx // columns
            col = idx % columns
            x = gap + col * (thumb_width + gap)
            y = gap + row * (thumb_height + gap)

            thumb = Image.open(path).convert("RGB")
            thumb = thumb.resize((thumb_width, thumb_height), Image.LANCZOS)
            composite.paste(thumb, (x, y))

        composite.save(output_path, "PNG")
        return True

    except Exception as exc:
        print(f"[WARN] Timeline composite failed: {exc}")
        return False
