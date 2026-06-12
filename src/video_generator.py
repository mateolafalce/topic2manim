import os
import uuid
import threading
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from llm_providers import setup_llm_client, get_configured_llm_providers
from animations import generate_script_json
from tts_generator import generate_complete_audio, setup_tts_config, generate_audio_fragment
from render_pipeline import (
    render_scenes_with_pipeline,
    render_single_scene,
    load_checkpoint,
    is_job_cancelled,
    JobCancelledError,
    generate_scene_code,
    compile_scene_from_code,
)
from concat_video import concatenate_videos, sanitize_filename, merge_video_and_audio
from video_assembler import assemble_final_video
from video_html_wrapper import generate_video_html
from script_import import parse_import_script
from vector_snippets import extract_snippets_from_job
from chapter_segmentation import auto_segment_chapters
from captions import generate_and_burn_captions
from audio_mixer import mix_audio_with_music, add_sound_effects, map_visual_events_to_sfx
from quality_metrics import analyze_full_script
from thumbnails import generate_scene_thumbnails, generate_composite_timeline

load_dotenv()


# Global state (in production, use Redis or a database)
jobs = {}
jobs_lock = threading.RLock()
_job_threads = {}

# Import db after load_dotenv so env vars are available
import db


def get_available_llm_providers():
    """Return LLM providers that are currently configured (have API keys)."""
    return get_configured_llm_providers()


def _persist_job(job_id, checkpoint=None):
    with jobs_lock:
        data = dict(jobs.get(job_id, {}))
    if checkpoint is not None:
        data["render_checkpoint"] = checkpoint
    db.persist_job(job_id, data)


def _load_job_from_disk(job_id):
    return db.load_job(job_id)


def get_job(job_id):
    with jobs_lock:
        return jobs.get(job_id)


def _ensure_job_record(job_id):
    with jobs_lock:
        if job_id not in jobs:
            loaded = db.load_job(job_id)
            if loaded:
                jobs[job_id] = loaded


# On startup, sync recent jobs from Supabase/local disk into memory
db.sync_jobs_dict_on_startup(jobs, jobs_lock)

def update_job_status(
    job_id,
    status=None,
    progress=None,
    current_step=None,
    message=None,
    error=None,
    video_url=None,
    html_url=None,
    scenes_total=None,
    scenes_done=None,
    scene_result=None,
):
    with jobs_lock:
        if job_id not in jobs:
            jobs[job_id] = {}
        job = jobs[job_id]
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"] = progress
        if current_step is not None:
            job["current_step"] = current_step
        if message is not None:
            job["message"] = message
        if error is not None:
            job["error"] = error
        if video_url is not None:
            job["video_url"] = video_url
        if html_url is not None:
            job["html_url"] = html_url
        if scenes_total is not None:
            job["scenes_total"] = scenes_total
        if scenes_done is not None:
            job["scenes_done"] = scenes_done
        if scene_result is not None:
            job.setdefault("scene_results", []).append(scene_result)
        job["updated_at"] = datetime.now().isoformat()


def _render_video_phase(
    job_id,
    topic,
    video_data,
    enable_tts,
    llm_config,
    tts_provider,
    video_settings,
    tts_voice,
    content_dir,
    media_dir,
):
    """Render scenes, concatenate, and merge audio."""
    checkpoint = load_checkpoint(jobs.get(job_id, {}))

    # TTS
    audio_path = None
    audio_durations = {}
    if enable_tts:
        update_job_status(
            job_id,
            progress=30,
            current_step="tts",
            message="Generating audio with TTS...",
        )
        tts_config = None
        try:
            tts_config = setup_tts_config(tts_provider, tts_voice)
        except ValueError as exc:
            update_job_status(
                job_id,
                message=f"Skipping TTS ({exc})",
            )
        audio_path, audio_durations = generate_complete_audio(video_data, tts_config)
        if audio_path:
            update_job_status(
                job_id,
                progress=40,
                current_step="tts",
                message="Audio generated successfully",
            )
        else:
            update_job_status(
                job_id,
                progress=40,
                current_step="tts",
                message="Skipping TTS (no provider configured)",
            )
    else:
        update_job_status(
            job_id,
            progress=40,
            current_step="code",
            message="Skipping TTS (disabled)",
        )

    if is_job_cancelled(jobs, job_id, jobs_lock):
        raise JobCancelledError("Render cancelled by user")

    # Render scenes
    update_job_status(
        job_id,
        progress=45,
        current_step="code",
        message="Rendering scenes...",
    )

    topic_slug = sanitize_filename(topic.lower().replace(" ", "_"))
    quality = (video_settings or {}).get("quality", "standard")

    def persist_fn(jid, chk):
        _persist_job(jid, chk)

    def update_status_fn(
        progress=None, message=None, scenes_done=None, scene_result=None, **kwargs
    ):
        update_job_status(
            job_id,
            progress=progress,
            message=message,
            scenes_done=scenes_done,
            scene_result=scene_result,
        )

    generated_videos = render_scenes_with_pipeline(
        job_id=job_id,
        video_data=video_data,
        topic_slug=topic_slug,
        content_dir=content_dir,
        llm_client=llm_config["client"],
        provider=llm_config["provider"],
        model=llm_config["model"],
        video_settings=video_settings,
        quality=quality,
        audio_durations=audio_durations,
        checkpoint=checkpoint,
        jobs=jobs,
        persist_fn=persist_fn,
        update_status_fn=update_status_fn,
        jobs_lock=jobs_lock,
    )

    if not generated_videos:
        raise Exception("No videos were generated")

    if is_job_cancelled(jobs, job_id, jobs_lock):
        raise JobCancelledError("Render cancelled by user")

    # Assemble final video (title card + scenes + transitions + end screen + audio)
    update_job_status(
        job_id,
        progress=80,
        current_step="video",
        message="Assembling final video with MoviePy...",
    )
    final_output_path = str(media_dir / f"output_{job_id}.mp4")
    try:
        assemble_final_video(
            scene_paths=generated_videos,
            output_path=final_output_path,
            topic=topic,
            audio_path=audio_path,
            video_settings=video_settings,
        )
    except Exception as exc:
        print(f"[WARN] MoviePy assembly failed ({exc}), falling back to ffmpeg...")
        update_job_status(
            job_id,
            progress=80,
            current_step="video",
            message="MoviePy failed, falling back to ffmpeg...",
        )
        silent_video_path = str(media_dir / f"output_silent_{job_id}.mp4")
        transition_duration = float(
            (video_settings or {}).get(
                "transition_duration", os.getenv("SCENE_TRANSITION_DURATION", "0.3")
            )
        )
        success = concatenate_videos(
            generated_videos, silent_video_path, transition_duration=transition_duration
        )
        if not success:
            raise Exception("Failed to concatenate videos")
        if audio_path:
            merge_success = merge_video_and_audio(
                video_path=silent_video_path,
                audio_path=audio_path,
                output_path=final_output_path,
            )
            if not merge_success:
                final_output_path = silent_video_path
        else:
            if os.path.exists(silent_video_path):
                os.rename(silent_video_path, final_output_path)

    # Background music mixing
    music_enabled = (video_settings or {}).get("music_enabled", False)
    mixed_audio_path = audio_path
    if music_enabled and audio_path and os.path.exists(audio_path):
        update_job_status(
            job_id,
            progress=82,
            current_step="audio",
            message="Mixing background music...",
        )
        music_output = str(media_dir / f"audio_mixed_{job_id}.mp3")
        music_track = (video_settings or {}).get("music_track")
        music_volume = float((video_settings or {}).get("music_volume_db", -22))
        ok = mix_audio_with_music(
            narration_path=audio_path,
            output_path=music_output,
            topic=topic,
            music_volume_db=music_volume,
            music_track=music_track,
        )
        if ok:
            mixed_audio_path = music_output

    # Sound effects
    sfx_enabled = (video_settings or {}).get("sfx_enabled", False)
    if sfx_enabled and mixed_audio_path and os.path.exists(mixed_audio_path):
        update_job_status(
            job_id,
            progress=84,
            current_step="audio",
            message="Adding sound effects...",
        )
        sfx_output = str(media_dir / f"audio_sfx_{job_id}.mp3")
        # Build SFX events from visual events in scenes
        sfx_events = []
        for i, scene in enumerate(video_data):
            events = scene.get("visual_events", [])
            scene_start = sum(audio_durations.get(str(j), 0) for j in range(1, i + 1))
            scene_sfx = map_visual_events_to_sfx(events, scene_start)
            sfx_events.extend(scene_sfx)
        if sfx_events:
            ok = add_sound_effects(mixed_audio_path, sfx_output, sfx_events)
            if ok:
                mixed_audio_path = sfx_output

    # Replace audio in final video if mixing was done
    if mixed_audio_path != audio_path and mixed_audio_path and os.path.exists(mixed_audio_path):
        update_job_status(
            job_id,
            progress=86,
            current_step="audio",
            message="Replacing audio track...",
        )
        final_with_audio = str(media_dir / f"output_audio_{job_id}.mp4")
        try:
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-i", final_output_path,
                "-i", mixed_audio_path,
                "-c:v", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                final_with_audio,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(final_with_audio):
                os.replace(final_with_audio, final_output_path)
        except Exception as exc:
            print(f"[WARN] Audio replacement failed: {exc}")

    # Auto-captions
    captions_enabled = (video_settings or {}).get("captions_enabled", False)
    if captions_enabled:
        update_job_status(
            job_id,
            progress=88,
            current_step="captions",
            message="Burning captions into video...",
        )
        captioned_output = str(media_dir / f"output_captions_{job_id}.mp4")
        # Estimate scene durations from audio
        scene_durs = []
        for i in range(len(video_data)):
            dur = audio_durations.get(str(i + 1), 0)
            if dur == 0:
                word_count = len(video_data[i].get("text", "").split())
                dur = max((word_count / 140) * 60, 3.0)
            scene_durs.append(dur)
        ok = generate_and_burn_captions(
            video_path=final_output_path,
            scenes=video_data,
            output_path=captioned_output,
            scene_durations=scene_durs,
            style=(video_settings or {}).get("caption_style"),
            temp_dir=str(media_dir),
        )
        if ok and os.path.exists(captioned_output):
            os.replace(captioned_output, final_output_path)

    # Scene thumbnails
    thumbnails_enabled = (video_settings or {}).get("thumbnails_enabled", True)
    thumbnail_paths = []
    if thumbnails_enabled and generated_videos:
        update_job_status(
            job_id,
            progress=92,
            current_step="thumbnails",
            message="Generating scene thumbnails...",
        )
        thumb_dir = str(media_dir / f"thumbnails_{job_id}")
        scene_durs = []
        for i in range(len(video_data)):
            dur = audio_durations.get(str(i + 1), 0)
            scene_durs.append(dur)
        thumbnail_paths = generate_scene_thumbnails(
            scene_videos=generated_videos,
            output_dir=thumb_dir,
            scene_durations=scene_durs,
            width=320,
        )
        # Composite timeline
        timeline_path = str(media_dir / f"timeline_{job_id}.png")
        generate_composite_timeline(
            thumbnails=thumbnail_paths,
            output_path=timeline_path,
            columns=4,
        )
        if os.path.exists(timeline_path):
            with jobs_lock:
                jobs[job_id]["timeline_image"] = f"/media/{os.path.basename(timeline_path)}"

    # Quality metrics
    metrics_enabled = (video_settings or {}).get("quality_metrics_enabled", True)
    if metrics_enabled and video_data:
        update_job_status(
            job_id,
            progress=96,
            current_step="metrics",
            message="Computing quality metrics...",
        )
        scene_durs = []
        for i in range(len(video_data)):
            dur = audio_durations.get(str(i + 1), 0)
            if dur == 0:
                dur = len(video_data[i].get("text", "").split()) / 140 * 60
            scene_durs.append(dur)
        try:
            metrics = analyze_full_script(video_data, scene_durs, topic=topic)
            with jobs_lock:
                jobs[job_id]["quality_metrics"] = metrics
            _persist_job(job_id)
        except Exception as exc:
            print(f"[WARN] Quality metrics failed: {exc}")

    # Auto-segment chapters for the interactive player
    chapters = None
    try:
        chapters = auto_segment_chapters(
            video_data,
            client=llm_config.get("client"),
            provider=llm_config.get("provider", "openai"),
            model=llm_config.get("model"),
            use_llm=bool(llm_config.get("client")),
        )
        if chapters:
            with jobs_lock:
                jobs[job_id]["chapters"] = chapters
    except Exception as exc:
        print(f"[WARN] Chapter segmentation failed: {exc}")

    # Generate interactive HTML wrapper
    html_path = str(media_dir / f"output_{job_id}.html")
    try:
        title_dur = float(video_settings.get("title_card_duration", 0)) if video_settings else 0
        end_dur = float(video_settings.get("end_screen_duration", 0)) if video_settings else 0
        generate_video_html(
            video_path=final_output_path,
            output_html_path=html_path,
            topic=topic,
            scenes=video_data,
            title_duration=title_dur,
            end_duration=end_dur,
            scene_video_paths=generated_videos,
            chapters=chapters,
        )
    except Exception as exc:
        print(f"[WARN] HTML wrapper generation failed: {exc}")
        html_path = ""

    video_url = f"/media/{os.path.basename(final_output_path)}"
    html_url = f"/media/{os.path.basename(html_path)}" if html_path else ""
    update_job_status(
        job_id,
        status="completed",
        progress=100,
        current_step="video",
        message="Video generation completed!",
        video_url=video_url,
        html_url=html_url,
    )

    # Extract and store Manim code snippets for future reuse
    try:
        snippet_ids = extract_snippets_from_job(
            {
                "job_id": job_id,
                "topic": topic,
                "script": video_data,
            },
            client=llm_config.get("client"),
            provider=llm_config.get("provider", "openai"),
            model=llm_config.get("model"),
        )
        if snippet_ids:
            print(f"[OK] Stored {len(snippet_ids)} code snippets for reuse")
            with jobs_lock:
                jobs[job_id]["snippet_ids"] = snippet_ids
            _persist_job(job_id)
    except Exception as exc:
        print(f"[WARN] Snippet extraction failed: {exc}")


def generate_video_workflow(
    job_id,
    topic,
    enable_tts,
    llm_provider,
    tts_provider="auto",
    llm_model=None,
    video_settings=None,
    tts_voice=None,
    input_mode="topic",
    import_script=None,
    script=None,
    import_format="auto",
    enrich_animations=False,
):
    """Background worker for video generation."""
    try:
        project_root = Path(__file__).parent.parent
        content_dir = project_root / "content"
        media_dir = project_root / "media"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        if is_job_cancelled(jobs, job_id, jobs_lock):
            return

        # Setup LLM
        update_job_status(
            job_id,
            status="running",
            progress=5,
            current_step="script",
            message="Setting up LLM client...",
        )
        llm_config = setup_llm_client(llm_provider, llm_model)
        client = llm_config["client"]
        provider = llm_config["provider"]
        model = llm_config["model"]

        # Generate script
        update_job_status(
            job_id,
            progress=10,
            current_step="script",
            message=f"Generating script with {provider}...",
        )

        if input_mode == "import" and import_script:
            parsed = parse_import_script(
                str(import_script),
                format_hint=import_format,
                title=topic,
            )
            video_data = parsed.get("scenes")
            if not video_data:
                raise ValueError("Could not parse import script")
        elif input_mode == "script" and script:
            if not isinstance(script, list):
                raise ValueError("Script must be a list of scene objects")
            video_data = script
        else:
            json_file = str(content_dir / f"video-output-{job_id}.json")

            # Generate narrative arc plan first (improves script coherence)
            narrative_plan = None
            try:
                from narrative_planner import generate_narrative_plan

                length_sec = video_settings.get("length_preset", {}).get("duration_sec", 180) if video_settings else 180
                narrative_plan = generate_narrative_plan(
                    client=client,
                    topic=topic,
                    provider=provider,
                    model=model,
                    length_seconds=length_sec,
                )
                if narrative_plan:
                    print(f"[OK] Narrative plan: {narrative_plan.get('title', topic)}")
                    print(f"       Hook: {narrative_plan.get('hook', '')}")
                    print(f"       Aha:  {narrative_plan.get('aha_moment', '')}")
                    # Persist plan alongside job
                    with jobs_lock:
                        jobs[job_id]["narrative_plan"] = narrative_plan
                    _persist_job(job_id)
            except Exception as exc:
                print(f"[WARN] Narrative planning failed: {exc}")

            video_data, script_error = generate_script_json(
                client, topic, json_file, provider, model, video_settings=video_settings, narrative_plan=narrative_plan
            )
            if script_error or not video_data:
                raise ValueError(script_error or "Could not generate script")

        update_job_status(
            job_id,
            progress=25,
            current_step="script",
            message=f"Script generated with {len(video_data)} scenes",
            scenes_total=len(video_data),
        )

        # If review is enabled, pause for user review
        review_enabled = (video_settings or {}).get("review_script", False)
        if review_enabled:
            with jobs_lock:
                jobs[job_id]["script"] = video_data
                jobs[job_id]["status"] = "awaiting_review"
                jobs[job_id]["message"] = "Script awaiting review"
                jobs[job_id]["updated_at"] = datetime.now().isoformat()
            _persist_job(job_id)
            return

        # Render phase
        _render_video_phase(
            job_id,
            topic,
            video_data,
            enable_tts,
            llm_config,
            tts_provider,
            video_settings,
            tts_voice,
            content_dir,
            media_dir,
        )

    except JobCancelledError:
        update_job_status(job_id, status="cancelled", message="Cancelled by user")
    except Exception as e:
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            message=f"Error: {str(e)}",
        )


def start_video_generation(
    topic,
    enable_tts=True,
    llm_provider="auto",
    tts_provider="auto",
    llm_model=None,
    video_settings=None,
    tts_voice=None,
    input_mode="topic",
    import_script=None,
    script=None,
    import_format="auto",
    enrich_animations=False,
):
    """Start video generation in background thread."""
    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "topic": topic,
            "status": "queued",
            "progress": 0,
            "current_step": "script",
            "message": "Job queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "enable_tts": enable_tts,
            "llm_provider": llm_provider,
            "tts_provider": tts_provider,
            "llm_model": llm_model,
            "video_settings": video_settings,
            "tts_voice": tts_voice,
            "input_mode": input_mode,
            "import_script": import_script,
            "script": script,
            "import_format": import_format,
            "enrich_animations": enrich_animations,
        }
    _persist_job(job_id)

    thread = threading.Thread(
        target=generate_video_workflow,
        args=(job_id, topic, enable_tts, llm_provider),
        kwargs={
            "tts_provider": tts_provider,
            "llm_model": llm_model,
            "video_settings": video_settings,
            "tts_voice": tts_voice,
            "input_mode": input_mode,
            "import_script": import_script,
            "script": script,
            "import_format": import_format,
            "enrich_animations": enrich_animations,
        },
        daemon=True,
    )
    thread.start()
    with jobs_lock:
        _job_threads[job_id] = thread
    return job_id


def get_job_status(job_id):
    """Get current status of a job."""
    with jobs_lock:
        return jobs.get(job_id)


def cancel_video_generation(job_id):
    """Cancel a running or queued job."""
    with jobs_lock:
        if job_id not in jobs:
            raise ValueError("Job not found")
        jobs[job_id]["cancel_requested"] = True
        jobs[job_id]["status"] = "cancelled"
        jobs[job_id]["message"] = "Cancelled by user"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
    _persist_job(job_id)


def update_job_script(job_id, script):
    """Save edited script while job awaits review."""
    with jobs_lock:
        if job_id not in jobs:
            raise ValueError("Job not found")
        job = jobs[job_id]
        if job.get("status") != "awaiting_review":
            raise ValueError("Job is not awaiting script review")
        if not isinstance(script, list):
            raise ValueError("Script must be a list of scene objects")
        job["script"] = script
        job["updated_at"] = datetime.now().isoformat()
    _persist_job(job_id)
    return script


def continue_video_generation(job_id, script_override=None):
    """Approve script and continue rendering."""
    _ensure_job_record(job_id)
    with jobs_lock:
        if job_id not in jobs:
            raise ValueError("Job not found")
        job = jobs[job_id]
        if job.get("status") != "awaiting_review":
            raise ValueError("Job is not awaiting script review")
        job["status"] = "running"
        job["updated_at"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_continue_render_worker,
        args=(job_id, script_override),
        daemon=True,
    )
    thread.start()


def _continue_render_worker(job_id, script_override=None):
    try:
        _ensure_job_record(job_id)
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                return
            video_data = script_override if script_override is not None else job.get("script", [])
            topic = job.get("topic", "")
            enable_tts = job.get("enable_tts", True)
            llm_provider = job.get("llm_provider", "auto")
            llm_model = job.get("llm_model")
            tts_provider = job.get("tts_provider", "auto")
            video_settings = job.get("video_settings")
            tts_voice = job.get("tts_voice")

        project_root = Path(__file__).parent.parent
        content_dir = project_root / "content"
        media_dir = project_root / "media"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        llm_config = setup_llm_client(llm_provider, llm_model)
        _render_video_phase(
            job_id,
            topic,
            video_data,
            enable_tts,
            llm_config,
            tts_provider,
            video_settings,
            tts_voice,
            content_dir,
            media_dir,
        )
    except JobCancelledError:
        update_job_status(job_id, status="cancelled", message="Cancelled by user")
    except Exception as e:
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            message=f"Error: {str(e)}",
        )


def resume_video_generation(job_id):
    """Resume an interrupted render from the last checkpoint."""
    _ensure_job_record(job_id)
    with jobs_lock:
        if job_id not in jobs:
            raise ValueError("Job not found")
        job = jobs[job_id]
        if job.get("status") not in ("failed", "interrupted", "cancelled"):
            raise ValueError("Job cannot be resumed")
        job["status"] = "running"
        job["cancel_requested"] = False
        job["error"] = None
        job["updated_at"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_resume_worker,
        args=(job_id,),
        daemon=True,
    )
    thread.start()


def _resume_worker(job_id):
    try:
        with jobs_lock:
            job = jobs.get(job_id, {})
            topic = job.get("topic", "")
            enable_tts = job.get("enable_tts", True)
            llm_provider = job.get("llm_provider", "auto")
            llm_model = job.get("llm_model")
            tts_provider = job.get("tts_provider", "auto")
            video_settings = job.get("video_settings")
            tts_voice = job.get("tts_voice")
            video_data = job.get("script", [])

        project_root = Path(__file__).parent.parent
        content_dir = project_root / "content"
        media_dir = project_root / "media"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        llm_config = setup_llm_client(llm_provider, llm_model)
        _render_video_phase(
            job_id,
            topic,
            video_data,
            enable_tts,
            llm_config,
            tts_provider,
            video_settings,
            tts_voice,
            content_dir,
            media_dir,
        )
    except JobCancelledError:
        update_job_status(job_id, status="cancelled", message="Cancelled by user")
    except Exception as e:
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            message=f"Error: {str(e)}",
        )


def list_jobs(limit=20):
    """List recent jobs for resume/history UI."""
    recent = db.list_recent_jobs(limit=limit)
    return [
        {
            "job_id": j.get("job_id"),
            "topic": j.get("topic"),
            "status": j.get("status"),
            "progress": j.get("progress"),
            "created_at": j.get("created_at"),
            "updated_at": j.get("updated_at"),
        }
        for j in recent
    ]


def retry_scene_render(job_id, scene_index, regen_code=False):
    """Retry rendering a specific scene."""
    _ensure_job_record(job_id)
    with jobs_lock:
        if job_id not in jobs:
            raise ValueError("Job not found")
        job = jobs[job_id]
        if job.get("status") not in ("failed", "completed", "running"):
            raise ValueError("Job must be failed, completed, or running to retry a scene")
        job["status"] = "running"
        job["updated_at"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_retry_scene_worker,
        args=(job_id, scene_index, regen_code),
        daemon=True,
    )
    thread.start()


def _retry_scene_worker(job_id, scene_index, regen_code):
    try:
        _ensure_job_record(job_id)
        with jobs_lock:
            job = jobs.get(job_id, {})
            topic = job.get("topic", "")
            llm_provider = job.get("llm_provider", "auto")
            llm_model = job.get("llm_model")
            video_settings = job.get("video_settings")
            video_data = job.get("script", [])

        project_root = Path(__file__).parent.parent
        content_dir = project_root / "content"
        media_dir = project_root / "media"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        llm_config = setup_llm_client(llm_provider, llm_model)
        topic_slug = sanitize_filename(topic.lower().replace(" ", "_"))
        quality = (video_settings or {}).get("quality", "standard")
        checkpoint = load_checkpoint(job)

        audio_durations = checkpoint.get("audio_durations") or {}

        def persist_fn(jid, chk):
            _persist_job(jid, chk)

        video_path = render_single_scene(
            jobs=jobs,
            job_id=job_id,
            video_data=video_data,
            scene_index=scene_index,
            topic_slug=topic_slug,
            content_dir=content_dir,
            llm_client=llm_config["client"],
            provider=llm_config["provider"],
            model=llm_config["model"],
            video_settings=video_settings,
            quality=quality,
            audio_durations=audio_durations,
            checkpoint=checkpoint,
            persist_fn=persist_fn,
            regen_code=regen_code,
            jobs_lock=jobs_lock,
        )

        if video_path:
            update_job_status(
                job_id,
                message=f"Scene {scene_index} retried successfully",
            )
        else:
            update_job_status(
                job_id,
                message=f"Scene {scene_index} retry failed",
            )
    except JobCancelledError:
        update_job_status(job_id, status="cancelled", message="Cancelled by user")
    except Exception as e:
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            message=f"Error: {str(e)}",
        )


def start_scene_preview(
    topic,
    script,
    scene_index=1,
    enable_tts=True,
    llm_provider="auto",
    tts_provider="auto",
    llm_model=None,
    tts_voice=None,
    video_settings=None,
):
    """Render a single scene at preview quality before a full run."""
    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "topic": topic,
            "status": "queued",
            "progress": 0,
            "current_step": "preview",
            "message": "Preview queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    thread = threading.Thread(
        target=_preview_scene_worker,
        args=(
            job_id,
            topic,
            script,
            scene_index,
            enable_tts,
            llm_provider,
            tts_provider,
            llm_model,
            tts_voice,
            video_settings,
        ),
        daemon=True,
    )
    thread.start()
    return job_id


def _preview_scene_worker(
    job_id,
    topic,
    script,
    scene_index,
    enable_tts,
    llm_provider,
    tts_provider,
    llm_model,
    tts_voice,
    video_settings,
):
    try:
        project_root = Path(__file__).parent.parent
        content_dir = project_root / "content"
        media_dir = project_root / "media"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        update_job_status(
            job_id,
            status="running",
            progress=5,
            message="Setting up LLM for preview...",
        )

        llm_config = setup_llm_client(llm_provider, llm_model)
        topic_slug = sanitize_filename(topic.lower().replace(" ", "_"))
        quality = (video_settings or {}).get("quality", "standard")

        scene_data = script[scene_index - 1] if scene_index <= len(script) else {}

        # TTS for preview
        audio_duration = None
        if enable_tts:
            tts_config = None
            try:
                tts_config = setup_tts_config(tts_provider, tts_voice)
            except ValueError:
                pass
            if tts_config and scene_data:
                audio_path = str(media_dir / f"preview_audio_{job_id}.mp3")
                result = generate_audio_fragment(
                    tts_config,
                    scene_data.get("text", ""),
                    scene_index,
                    output_dir=str(media_dir),
                )
                if result:
                    audio_path, audio_duration = result

        # Generate and compile scene code
        manim_code = generate_scene_code(
            llm_config["client"],
            llm_config["provider"],
            llm_config["model"],
            scene_data,
            scene_index,
            None,
            None,
            audio_duration,
            video_settings,
        )

        if not manim_code:
            raise Exception("Could not generate scene code")

        video_path, final_code, critique = compile_scene_from_code(
            llm_config["client"],
            llm_config["provider"],
            llm_config["model"],
            scene_data,
            scene_index,
            manim_code,
            topic_slug,
            job_id,
            content_dir,
            quality,
        )

        if not video_path:
            raise Exception("Could not compile preview scene")

        # Copy to preview location
        preview_path = str(media_dir / f"preview_{job_id}.mp4")
        shutil.copy2(video_path, preview_path)

        video_url = f"/media/{os.path.basename(preview_path)}"
        update_job_status(
            job_id,
            status="completed",
            progress=100,
            message="Preview completed",
            video_url=video_url,
        )
    except Exception as e:
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            message=f"Error: {str(e)}",
        )
