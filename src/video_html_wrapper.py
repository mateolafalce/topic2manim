"""Generate an interactive HTML wrapper for finished videos.

Produces a self-contained HTML file with chapter navigation, scene text,
and a clean player that matches the Topic2Manim dark aesthetic.
"""

import html
import os
from typing import List, Optional


def _scene_duration_seconds(scene_video_path: str) -> float:
    """Get duration of a scene video using ffprobe."""
    import subprocess

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
                scene_video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip() or "0")
    except Exception:
        return 0.0


def generate_video_html(
    video_path: str,
    output_html_path: str,
    topic: str = "",
    scenes: Optional[List[dict]] = None,
    title_duration: float = 0.0,
    end_duration: float = 0.0,
    scene_video_paths: Optional[List[str]] = None,
    chapters: Optional[List[dict]] = None,
) -> str:
    """Generate an interactive HTML player for the video.

    Args:
        video_path: Path to the final MP4 (used for relative src).
        output_html_path: Where to write the HTML file.
        topic: Video title.
        scenes: List of scene dicts with 'title', 'text', 'narration' keys.
        title_duration: Duration of title card (offset for first scene).
        end_duration: Duration of end screen (not a chapter).
        scene_video_paths: Optional list of per-scene MP4 paths to compute exact durations.
        chapters: Optional pre-computed chapters list [{title, scenes: [...]}].
            If provided, overrides per-scene chapter building.

    Returns:
        Path to the written HTML file.
    """
    scenes = scenes or []
    video_filename = os.path.basename(video_path)
    scene_video_paths = scene_video_paths or []

    # Build chapter list from actual scene durations when available
    chapter_list = []
    if chapters:
        # Use pre-computed chapter groupings
        current_time = title_duration
        for ch in chapters:
            ch_scenes = ch.get("scenes", [])
            ch_texts = []
            for si in ch_scenes:
                if 0 <= si < len(scenes):
                    txt = scenes[si].get("narration") or scenes[si].get("text", "")
                    if txt:
                        ch_texts.append(txt)
            chapter_list.append(
                {
                    "label": html.escape(ch.get("title", "Chapter")),
                    "text": html.escape(" ".join(ch_texts)[:200]),
                    "time": round(current_time, 2),
                }
            )
            # Advance time by chapter scene durations
            for si in ch_scenes:
                if si < len(scene_video_paths):
                    current_time += _scene_duration_seconds(scene_video_paths[si])
                else:
                    current_time += 8.0
    else:
        current_time = title_duration
        for idx, scene in enumerate(scenes, 1):
            scene_title = scene.get("title") or scene.get("chapter") or f"Scene {idx}"
            scene_text = scene.get("narration") or scene.get("text", "")
            chapter_list.append(
                {
                    "label": html.escape(scene_title),
                    "text": html.escape(scene_text),
                    "time": round(current_time, 2),
                }
            )
            if idx - 1 < len(scene_video_paths):
                current_time += _scene_duration_seconds(scene_video_paths[idx - 1])
            else:
                current_time += 8.0  # fallback approximate duration

    chapters_json = str(chapter_list).replace("'", '"')

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(topic or "Video")}</title>
    <style>
        :root {{
            --bg: #0f0f1a;
            --surface: #1a1a2e;
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #6366f1;
            --accent-hover: #818cf8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem 1rem;
        }}
        h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            text-align: center;
            color: var(--text);
        }}
        .player-wrap {{
            width: 100%;
            max-width: 960px;
            background: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }}
        video {{
            width: 100%;
            display: block;
            background: #000;
        }}
        .chapters {{
            padding: 1rem;
            max-height: 320px;
            overflow-y: auto;
        }}
        .chapter {{
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            padding: 0.75rem;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .chapter:hover {{
            background: rgba(99, 102, 241, 0.12);
        }}
        .chapter.active {{
            background: rgba(99, 102, 241, 0.2);
        }}
        .chapter-time {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--accent);
            min-width: 48px;
            text-align: right;
            padding-top: 2px;
        }}
        .chapter-body {{
            flex: 1;
        }}
        .chapter-title {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        .chapter-text {{
            font-size: 0.8rem;
            color: var(--muted);
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .controls {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: rgba(0,0,0,0.3);
        }}
        .btn {{
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .btn:hover {{ background: var(--accent-hover); }}
        .download {{
            margin-left: auto;
            background: transparent;
            border: 1px solid var(--accent);
            color: var(--accent);
        }}
        .download:hover {{
            background: var(--accent);
            color: #fff;
        }}
        @media (max-width: 640px) {{
            h1 {{ font-size: 1.25rem; }}
            .chapter-text {{ -webkit-line-clamp: 3; }}
        }}
    </style>
</head>
<body>
    <h1>{html.escape(topic or "Educational Video")}</h1>
    <div class="player-wrap">
        <video id="player" controls preload="metadata">
            <source src="{video_filename}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        <div class="controls">
            <button class="btn" onclick="prevChapter()">⏮ Prev</button>
            <button class="btn" onclick="nextChapter()">Next ⏭</button>
            <a class="btn download" href="{video_filename}" download>⬇ Download MP4</a>
        </div>
        <div class="chapters" id="chapters"></div>
    </div>

    <script>
        const chapters = {chapters_json};
        const video = document.getElementById('player');
        const list = document.getElementById('chapters');
        let activeIndex = -1;

        function fmt(t) {{
            const m = Math.floor(t / 60);
            const s = Math.floor(t % 60);
            return m + ':' + String(s).padStart(2, '0');
        }}

        function renderChapters() {{
            list.innerHTML = chapters.map((ch, i) => `
                <div class="chapter" data-index="${{i}}" onclick="seek(${{i}})">
                    <div class="chapter-time">${{fmt(ch.time)}}</div>
                    <div class="chapter-body">
                        <div class="chapter-title">${{ch.label}}</div>
                        <div class="chapter-text">${{ch.text}}</div>
                    </div>
                </div>
            `).join('');
        }}

        function seek(i) {{
            if (i < 0 || i >= chapters.length) return;
            video.currentTime = chapters[i].time;
            video.play();
            highlight(i);
        }}

        function highlight(i) {{
            document.querySelectorAll('.chapter').forEach((el, idx) => {{
                el.classList.toggle('active', idx === i);
            }});
            activeIndex = i;
        }}

        function prevChapter() {{
            const idx = activeIndex > 0 ? activeIndex - 1 : 0;
            seek(idx);
        }}

        function nextChapter() {{
            const idx = activeIndex < chapters.length - 1 ? activeIndex + 1 : chapters.length - 1;
            seek(idx);
        }}

        video.addEventListener('timeupdate', () => {{
            const t = video.currentTime;
            let idx = 0;
            for (let i = 0; i < chapters.length; i++) {{
                if (t >= chapters[i].time) idx = i;
            }}
            if (idx !== activeIndex) highlight(idx);
        }});

        renderChapters();
        if (chapters.length > 0) highlight(0);
    </script>
</body>
</html>"""

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_html_path
