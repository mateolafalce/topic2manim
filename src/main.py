from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path to enable imports
sys.path.insert(0, str(Path(__file__).parent))

from env_loader import load_app_env
from video_generator import (
    start_video_generation,
    get_job_status,
    get_available_llm_providers,
    continue_video_generation,
    update_job_script,
    resume_video_generation,
    cancel_video_generation,
    list_jobs,
    retry_scene_render,
    start_scene_preview,
)
from concat_video import compile_video, sanitize_filename
from tts_generator import (
    get_available_tts_providers,
    get_all_tts_providers,
    setup_tts_config,
    get_default_tts_voices,
    list_provider_voices,
)
from llm_providers import (
    get_all_llm_providers,
    setup_llm_client,
    get_default_models,
    list_provider_models,
)
from video_settings import get_settings_options, normalize_video_settings
from provider_health import check_providers
from script_import import parse_import_script
from prompt_template import build_external_script_prompt
from visual_events import get_catalog_for_api
from quality_metrics import analyze_full_script
from vector_snippets import search_snippets_by_text, get_snippet_count
from chapter_segmentation import auto_segment_chapters

load_app_env()

# Get absolute path to frontend directory
FRONTEND_DIR = Path(__file__).parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # ISS-0001: 16 MB upload limit
CORS(app)

# Ensure media directory exists (at project root level)
PROJECT_ROOT = Path(__file__).parent.parent
MEDIA_DIR = PROJECT_ROOT / "media"
os.makedirs(MEDIA_DIR, exist_ok=True)


@app.route("/")
def index():
    """Serve the main HTML page"""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/script/prompt-template", methods=["GET"])
def script_prompt_template():
    """Return a copy-paste prompt for ChatGPT / Claude."""
    topic = request.args.get("topic", "")
    length = request.args.get("length", "min_5")
    style = request.args.get("style", "balanced")
    return jsonify(
        {
            "prompt": build_external_script_prompt(topic=topic, length=length, style=style),
            "topic": topic,
            "length": length,
            "style": style,
        }
    )


@app.route("/api/script/parse", methods=["POST"])
def parse_script():
    """Parse pasted script without starting a render job."""
    try:
        data = request.get_json() or {}
        import_script = data.get("import_script") or data.get("script_text")
        if not import_script or not str(import_script).strip():
            return jsonify({"error": "import_script is required"}), 400

        result = parse_import_script(
            str(import_script),
            format_hint=data.get("import_format", "auto"),
            title=data.get("topic") or data.get("title"),
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/generate", methods=["POST"])
def generate_video():
    """Start video generation"""
    try:
        load_app_env()
        data = request.get_json()

        input_mode = data.get("input_mode", "topic")
        import_script = data.get("import_script")
        script = data.get("script")
        import_format = data.get("import_format", "auto")
        enrich_animations = bool(data.get("enrich_animations", False))

        topic = (data.get("topic") or "").strip()

        if input_mode == "import":
            if not import_script and not script:
                return (
                    jsonify({"error": "import_script or script array is required for import mode"}),
                    400,
                )
            if not topic:
                topic = "Imported Video"
        elif not topic:
            return jsonify({"error": "Topic is required"}), 400

        llm_provider = data.get("llm_provider", "auto")
        llm_model = data.get("llm_model")
        tts_provider = data.get("tts_provider", "auto")
        tts_voice = data.get("tts_voice")
        enable_tts = data.get("enable_tts", True)
        video_settings = normalize_video_settings(data.get("video_settings"))

        if enable_tts and tts_provider not in (None, "auto"):
            try:
                setup_tts_config(tts_provider, tts_voice)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        try:
            setup_llm_client(llm_provider, llm_model)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        job_id = start_video_generation(
            topic,
            enable_tts,
            llm_provider,
            tts_provider,
            llm_model,
            video_settings,
            tts_voice,
            input_mode=input_mode,
            import_script=import_script,
            script=script,
            import_format=import_format,
            enrich_animations=enrich_animations,
        )

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "queued",
                    "message": "Video generation started",
                    "input_mode": input_mode,
                }
            ),
            202,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    """Get video generation progress"""
    job = get_job_status(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job)


@app.route("/media/<path:filename>")
def serve_media(filename):
    """Serve generated media files"""
    return send_from_directory(MEDIA_DIR, filename)


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return providers available with the current server configuration."""
    load_app_env()
    env_path = Path(__file__).resolve().parent.parent / ".env"
    return jsonify(
        {
            "llm_providers": get_all_llm_providers(),
            "configured_llm_providers": get_available_llm_providers(),
            "tts_providers": get_all_tts_providers(),
            "configured_tts_providers": get_available_tts_providers(),
            "env_file_found": env_path.is_file(),
            "defaults": {
                "llm_provider": os.getenv("LLM_PROVIDER", "auto"),
                "tts_provider": os.getenv("TTS_PROVIDER", "auto"),
                "llm_models": get_default_models(),
                "tts_voices": get_default_tts_voices(),
                "video_settings": {
                    "length": "min_5",
                    "style": "balanced",
                    "quality": "standard",
                    "review_script": True,
                    "transition_duration": 0.3,
                    "critic_min_score": 8.0,
                    "critic_max_retries": 2,
                },
                "production_settings": {
                    "transition_duration": {
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "default": 0.3,
                        "label": "Scene transition (seconds)",
                    },
                    "transition_type": {
                        "type": "select",
                        "options": ["crossfade", "fade", "none"],
                        "default": "crossfade",
                        "label": "Transition style",
                    },
                    "critic_min_score": {
                        "min": 0.0,
                        "max": 10.0,
                        "step": 0.5,
                        "default": 8.0,
                        "label": "Critic pass threshold",
                    },
                    "critic_max_retries": {
                        "min": 0,
                        "max": 5,
                        "step": 1,
                        "default": 2,
                        "label": "Critic fix attempts",
                    },
                    "enable_title_card": {
                        "type": "toggle",
                        "default": True,
                        "label": "Title card",
                    },
                    "title_card_duration": {
                        "min": 0.5,
                        "max": 5.0,
                        "step": 0.5,
                        "default": 2.5,
                        "label": "Title duration (seconds)",
                    },
                    "enable_end_screen": {
                        "type": "toggle",
                        "default": True,
                        "label": "End screen",
                    },
                    "end_screen_duration": {
                        "min": 0.5,
                        "max": 5.0,
                        "step": 0.5,
                        "default": 3.0,
                        "label": "End screen duration (seconds)",
                    },
                    "audio_fade_duration": {
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "default": 0.5,
                        "label": "Audio fade (seconds)",
                    },
                    "captions_enabled": {
                        "type": "toggle",
                        "default": False,
                        "label": "Burn captions into video",
                    },
                    "caption_style": {
                        "type": "object",
                        "default": {
                            "font": "Arial",
                            "font_size": 24,
                            "color": "white",
                            "bg_color": "black@0.6",
                        },
                        "label": "Caption style",
                    },
                    "music_enabled": {
                        "type": "toggle",
                        "default": False,
                        "label": "Background music",
                    },
                    "music_volume_db": {
                        "min": -40,
                        "max": -10,
                        "step": 1,
                        "default": -22,
                        "label": "Music volume (dB)",
                    },
                    "sfx_enabled": {
                        "type": "toggle",
                        "default": False,
                        "label": "Sound effects",
                    },
                    "thumbnails_enabled": {
                        "type": "toggle",
                        "default": True,
                        "label": "Generate scene thumbnails",
                    },
                    "quality_metrics_enabled": {
                        "type": "toggle",
                        "default": True,
                        "label": "Compute quality metrics",
                    },
                },
            },
            "video_settings_options": get_settings_options(),
            "visual_events": get_catalog_for_api(),
            "features": {
                "frame_critic": os.getenv("ENABLE_FRAME_CRITIC", "true").lower()
                not in ("0", "false", "no"),
                "parallel_workers": os.getenv("RENDER_PARALLEL_WORKERS", "2"),
            },
        }
    )


@app.route("/api/llm/models", methods=["GET"])
def get_llm_models():
    """Return selectable models for a given LLM provider."""
    load_app_env()
    provider = request.args.get("provider", "ollama")
    models = list_provider_models(provider)
    default_model = get_default_models().get(provider)
    return jsonify(
        {
            "provider": provider,
            "models": models,
            "default_model": default_model,
        }
    )


@app.route("/api/tts/voices", methods=["GET"])
def get_tts_voices():
    """Return selectable voices for a TTS provider."""
    load_app_env()
    provider = request.args.get("provider", "elevenlabs")
    voices = list_provider_voices(provider)
    defaults = get_default_tts_voices()
    return jsonify(
        {
            "provider": provider,
            "voices": voices,
            "default_voice": defaults.get(provider),
        }
    )


@app.route("/api/providers/health", methods=["GET", "POST"])
def providers_health():
    """Check whether selected LLM/TTS providers are usable before generating."""
    load_app_env()
    if request.method == "POST":
        data = request.get_json() or {}
    else:
        data = request.args

    results = check_providers(
        llm_provider=data.get("llm_provider", "auto"),
        llm_model=data.get("llm_model"),
        tts_provider=data.get("tts_provider", "auto"),
        tts_voice=data.get("tts_voice"),
        enable_tts=str(data.get("enable_tts", "true")).lower() not in ("0", "false", "no"),
    )
    # Always 200 when the check ran; use JSON "ready" for provider availability.
    return jsonify(results), 200


@app.route("/api/jobs/<job_id>/script", methods=["PUT"])
def save_job_script(job_id):
    """Save edited script while job awaits review."""
    try:
        data = request.get_json() or {}
        script = data.get("script")
        if script is None:
            return jsonify({"error": "script is required"}), 400
        validated = update_job_script(job_id, script)
        return jsonify({"ok": True, "script": validated, "scenes": len(validated)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/jobs", methods=["GET"])
def list_all_jobs():
    """List recent jobs for resume/history UI."""
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify({"jobs": list_jobs(limit=limit)})


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    try:
        cancel_video_generation(job_id)
        return jsonify({"ok": True, "status": "cancelled"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/jobs/<job_id>/scenes/<int:scene_index>/retry", methods=["POST"])
def retry_scene(job_id, scene_index):
    try:
        data = request.get_json() or {}
        retry_scene_render(job_id, scene_index, regen_code=bool(data.get("regen_code")))
        return jsonify({"ok": True, "status": "running"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/jobs/<job_id>/resume", methods=["POST"])
def resume_job(job_id):
    """Resume an interrupted render from the last checkpoint."""
    try:
        resume_video_generation(job_id)
        return jsonify({"ok": True, "status": "running"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/preview-scene", methods=["POST"])
def preview_scene():
    """Render a single scene at preview quality before a full run."""
    try:
        load_app_env()
        data = request.get_json() or {}
        script = data.get("script")
        if not script or not isinstance(script, list):
            return jsonify({"error": "script array is required"}), 400

        scene_index = int(data.get("scene_index", 1))
        topic = (data.get("topic") or "").strip() or "Scene Preview"
        enable_tts = bool(data.get("enable_tts", True))
        llm_provider = data.get("llm_provider", "auto")
        llm_model = data.get("llm_model")
        tts_provider = data.get("tts_provider", "auto")
        tts_voice = data.get("tts_voice")
        video_settings = normalize_video_settings(data.get("video_settings"))

        if enable_tts and tts_provider not in (None, "auto"):
            try:
                setup_tts_config(tts_provider, tts_voice)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        try:
            setup_llm_client(llm_provider, llm_model)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        job_id = start_scene_preview(
            topic,
            script,
            scene_index=scene_index,
            enable_tts=enable_tts,
            llm_provider=llm_provider,
            tts_provider=tts_provider,
            llm_model=llm_model,
            tts_voice=tts_voice,
            video_settings=video_settings,
        )
        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "queued",
                    "message": f"Scene {scene_index} preview started",
                }
            ),
            202,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/preview-code", methods=["POST"])
def preview_code():
    """Compile raw Manim code and return the video path.

    Accepts:
        - code: str (raw Manim Python code)
        - class_name: str (scene class name)
        - topic: str (optional, used for file naming)
        - quality: str (optional, default "preview")
    Returns:
        - video_url: str (relative path to MP4)
        - Or error
    """
    try:
        data = request.get_json() or {}
        code = data.get("code", "").strip()
        class_name = data.get("class_name", "").strip()
        topic = (data.get("topic") or "preview").strip()
        quality = data.get("quality", "preview")

        if not code:
            return jsonify({"error": "code is required"}), 400
        if not class_name:
            return jsonify({"error": "class_name is required"}), 400
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", class_name):
            return jsonify({"error": f"Invalid class name: {class_name}"}), 400

        topic_slug = sanitize_filename(topic) or "preview"
        # Write to a temp file inside content/ so _safe_project_path accepts it
        content_dir = Path("content")
        content_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"preview_{topic_slug}_{uuid.uuid4().hex[:8]}.py"
        file_path = content_dir / file_name
        file_path.write_text(code, encoding="utf-8")

        video_path, error = compile_video(
            str(file_path), class_name, topic_slug, index=0, quality=quality
        )
        if error:
            return jsonify({"error": error}), 500

        return jsonify({"video_url": video_path})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/jobs/<job_id>/continue", methods=["POST"])
def continue_job(job_id):
    """Approve script and continue rendering."""
    try:
        data = request.get_json() or {}
        script_override = data.get("script")
        continue_video_generation(job_id, script_override)
        return jsonify({"ok": True, "status": "running"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------
_batches = {}
_batches_lock = threading.RLock()


def _start_batch_item(item, shared_config):
    """Start a single video generation job as part of a batch."""
    topic = item.get("topic", "").strip()
    script = item.get("script")
    input_mode = item.get("input_mode", "topic" if topic else "script")
    if script and not topic:
        topic = script[0].get("title", "Batch Video") if isinstance(script, list) else "Batch Video"

    video_settings = normalize_video_settings(item.get("video_settings"))
    return start_video_generation(
        topic=topic,
        enable_tts=shared_config.get("enable_tts", True),
        llm_provider=shared_config.get("llm_provider", "auto"),
        tts_provider=shared_config.get("tts_provider", "auto"),
        llm_model=shared_config.get("llm_model"),
        video_settings=video_settings,
        tts_voice=shared_config.get("tts_voice"),
        input_mode=input_mode,
        script=script,
    )


@app.route("/api/batch", methods=["POST"])
def create_batch():
    """Create a batch of video generation jobs.

    Expects:
        items: list of {topic, script, video_settings}
        llm_provider, tts_provider, llm_model, tts_voice, enable_tts
    Returns:
        batch_id, job_ids, status
    """
    try:
        data = request.get_json() or {}
        items = data.get("items", [])
        if not items or not isinstance(items, list):
            return jsonify({"error": "items array is required"}), 400
        if len(items) > 50:
            return jsonify({"error": "Max 50 items per batch"}), 400

        shared = {
            "llm_provider": data.get("llm_provider", "auto"),
            "llm_model": data.get("llm_model"),
            "tts_provider": data.get("tts_provider", "auto"),
            "tts_voice": data.get("tts_voice"),
            "enable_tts": bool(data.get("enable_tts", True)),
        }

        batch_id = str(uuid.uuid4())
        job_ids = []
        for item in items:
            job_id = _start_batch_item(item, shared)
            job_ids.append(job_id)

        with _batches_lock:
            _batches[batch_id] = {
                "batch_id": batch_id,
                "job_ids": job_ids,
                "status": "running",
                "created_at": datetime.now().isoformat(),
                "total": len(job_ids),
            }

        return (
            jsonify(
                {
                    "batch_id": batch_id,
                    "job_ids": job_ids,
                    "status": "running",
                    "total": len(job_ids),
                }
            ),
            202,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/batch/<batch_id>", methods=["GET"])
def get_batch_status(batch_id):
    """Get batch status with per-job details."""
    with _batches_lock:
        batch = _batches.get(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    jobs_detail = []
    completed = 0
    failed = 0
    for job_id in batch.get("job_ids", []):
        job = get_job_status(job_id)
        if job:
            jobs_detail.append(
                {
                    "job_id": job_id,
                    "topic": job.get("topic"),
                    "status": job.get("status"),
                    "progress": job.get("progress"),
                    "video_url": job.get("video_url"),
                    "error": job.get("error"),
                }
            )
            if job.get("status") == "completed":
                completed += 1
            elif job.get("status") in ("failed", "interrupted", "cancelled"):
                failed += 1

    total = batch.get("total", 0)
    status = batch["status"]
    if status == "running" and completed + failed >= total:
        status = "completed" if failed == 0 else "partial"
        with _batches_lock:
            _batches[batch_id]["status"] = status

    return jsonify(
        {
            "batch_id": batch_id,
            "status": status,
            "total": total,
            "completed": completed,
            "failed": failed,
            "jobs": jobs_detail,
        }
    )


@app.route("/api/jobs/<job_id>/metrics", methods=["GET"])
def get_job_metrics(job_id):
    """Return quality metrics for a completed job."""
    job = get_job_status(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    metrics = job.get("quality_metrics")
    if not metrics:
        # Compute on the fly if available
        script = job.get("script", [])
        if script:
            scene_durs = []
            for i, scene in enumerate(script):
                word_count = len(scene.get("text", "").split())
                scene_durs.append(max((word_count / 140) * 60, 3.0))
            metrics = analyze_full_script(script, scene_durs, topic=job.get("topic", ""))
        else:
            return jsonify({"error": "No script available for metrics"}), 404
    return jsonify(metrics)


@app.route("/api/jobs/<job_id>/thumbnails", methods=["GET"])
def get_job_thumbnails(job_id):
    """Return scene thumbnail URLs for a completed job."""
    job = get_job_status(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    thumb_dir = MEDIA_DIR / f"thumbnails_{job_id}"
    if not thumb_dir.exists():
        return jsonify({"thumbnails": [], "timeline": None})
    thumbs = sorted(
        [f"/media/thumbnails_{job_id}/{f}" for f in os.listdir(thumb_dir) if f.endswith(".png") and not f.startswith("scene_")],
        key=lambda x: int(re.search(r"scene_(\d+)", x).group(1)) if re.search(r"scene_(\d+)", x) else 0
    )
    timeline = f"/media/timeline_{job_id}.png"
    timeline_exists = (MEDIA_DIR / f"timeline_{job_id}.png").exists()
    return jsonify(
        {
            "thumbnails": thumbs,
            "timeline": timeline if timeline_exists else None,
        }
    )


@app.route("/api/metrics/analyze", methods=["POST"])
def analyze_script_metrics():
    """Analyze script quality metrics without running a job."""
    try:
        data = request.get_json() or {}
        scenes = data.get("scenes", [])
        topic = data.get("topic", "")
        durations = data.get("durations", [])
        if not scenes or not isinstance(scenes, list):
            return jsonify({"error": "scenes array is required"}), 400
        if not durations:
            durations = []
            for scene in scenes:
                word_count = len(scene.get("text", "").split())
                durations.append(max((word_count / 140) * 60, 3.0))
        metrics = analyze_full_script(scenes, durations, topic=topic)
        return jsonify(metrics)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/snippets/search", methods=["POST"])
def search_snippets():
    """Semantic search for reusable Manim code snippets."""
    try:
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        top_k = min(int(data.get("top_k", 3)), 10)
        if not query:
            return jsonify({"error": "query is required"}), 400

        provider = data.get("llm_provider", "auto")
        model = data.get("llm_model")
        from llm_providers import setup_llm_client
        llm_config = setup_llm_client(provider, model)

        results = search_snippets_by_text(
            query,
            llm_config["client"],
            llm_config["provider"],
            llm_config["model"],
            top_k=top_k,
        )
        return jsonify({
            "query": query,
            "count": get_snippet_count(),
            "results": results,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/snippets/count", methods=["GET"])
def snippet_count():
    """Return total number of stored code snippets."""
    return jsonify({"count": get_snippet_count()})


@app.route("/api/chapters/segment", methods=["POST"])
def segment_chapters():
    """Auto-segment scenes into chapters."""
    try:
        data = request.get_json() or {}
        scenes = data.get("scenes", [])
        if not scenes or not isinstance(scenes, list):
            return jsonify({"error": "scenes array is required"}), 400

        provider = data.get("llm_provider", "auto")
        model = data.get("llm_model")
        use_llm = bool(data.get("use_llm", True))

        client = None
        if use_llm:
            from llm_providers import setup_llm_client
            try:
                llm_config = setup_llm_client(provider, model)
                client = llm_config["client"]
                provider = llm_config["provider"]
                model = llm_config["model"]
            except Exception:
                use_llm = False

        chapters = auto_segment_chapters(
            scenes,
            client=client,
            provider=provider,
            model=model,
            use_llm=use_llm,
        )
        return jsonify({
            "chapters": chapters,
            "scene_count": len(scenes),
            "chapter_count": len(chapters),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Topic2Manim API", "snippets": get_snippet_count()})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("=" * 80)
    print("Topic2Manim Server")
    print("=" * 80)
    print("Starting Flask server...")
    print(f"Access the web interface at: http://localhost:{port}")
    print("=" * 80)
    print("\nNOTE: Auto-reload is disabled to prevent job state loss during video generation")
    print("      Restart the server manually if you make code changes.\n")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes"),
        use_reloader=False,  # Disable auto-reload to prevent losing job state
        threaded=True,
    )
