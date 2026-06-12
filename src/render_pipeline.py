"""Scene rendering: compile, critic, checkpointing, parallel compilation."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any, Callable, Dict, Optional, Tuple

from concat_video import compile_video
from frame_critic import (
    build_critic_fix_prompt,
    critic_max_retries,
    critique_scene_frames,
    extract_video_frames,
    is_critic_enabled,
)
from json_utils import extract_json_from_llm_response
from llm_chat import complete_llm
from manim_generator import fix_manim_code, generate_manim_code
from vector_snippets import search_snippets_by_text, format_snippets_for_prompt
from style_registry import create_style_registry, format_registry_for_prompt, update_style_registry
from visual_events import enrich_scene_events, format_events_for_prompt


# ISS-0001: added optional jobs_lock parameter to prevent race conditions
class JobCancelledError(Exception):
    """Raised when the user cancels a running render job."""


def is_job_cancelled(jobs: dict, job_id: str, jobs_lock=None) -> bool:
    if jobs_lock:
        with jobs_lock:
            return bool(jobs.get(job_id, {}).get("cancel_requested"))
    return bool(jobs.get(job_id, {}).get("cancel_requested"))


def ensure_not_cancelled(jobs: dict, job_id: str, jobs_lock=None):
    if is_job_cancelled(jobs, job_id, jobs_lock=jobs_lock):
        raise JobCancelledError("Render cancelled by user")


def parallel_workers() -> int:
    try:
        return max(1, min(int(os.getenv("RENDER_PARALLEL_WORKERS", "2")), 6))
    except ValueError:
        return 2


def empty_checkpoint() -> Dict[str, Any]:
    return {
        "audio_path": None,
        "audio_durations": {},
        "scene_codes": {},
        "scene_videos": {},
        "scene_results": {},
        "style_registry": create_style_registry(),
    }


def load_checkpoint(job: dict) -> Dict[str, Any]:
    checkpoint = deepcopy(job.get("render_checkpoint") or empty_checkpoint())
    if not checkpoint.get("style_registry"):
        checkpoint["style_registry"] = create_style_registry(job.get("video_settings"))
    return checkpoint


def save_checkpoint_to_job(
    jobs: dict, job_id: str, checkpoint: Dict[str, Any], persist_fn: Callable, jobs_lock=None
):
    if jobs_lock:
        with jobs_lock:
            jobs[job_id]["render_checkpoint"] = checkpoint
            persist_fn(job_id, checkpoint)
    else:
        jobs[job_id]["render_checkpoint"] = checkpoint
        persist_fn(job_id, checkpoint)


def _compile_with_repl(
    llm_client,
    provider,
    model,
    filepath,
    code,
    class_name,
    topic_slug,
    index,
    quality,
    max_repl=3,
    on_fix_message=None,
) -> Tuple[Optional[str], str, str]:
    current_code = code
    current_class_name = class_name
    video_path = None

    for repl_iteration in range(max_repl):
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(current_code)

        video_path, compile_error = compile_video(
            filepath, current_class_name, topic_slug, index, quality=quality
        )
        if video_path and os.path.exists(video_path):
            return video_path, current_code, current_class_name

        if compile_error and repl_iteration < max_repl - 1:
            if on_fix_message:
                on_fix_message(repl_iteration + 2, max_repl)
            fixed = fix_manim_code(
                client=llm_client,
                original_code=current_code,
                error_message=compile_error,
                class_name=current_class_name,
                provider=provider,
                model=model,
            )
            if fixed:
                current_code = fixed.get("content", current_code)
                current_class_name = fixed.get("class_name", current_class_name)
            else:
                break

    return (
        video_path if video_path and os.path.exists(video_path) else None,
        current_code,
        current_class_name,
    )


def _run_critic_loop(
    llm_client,
    provider,
    model,
    video_path,
    scene_data,
    filepath,
    code,
    class_name,
    topic_slug,
    index,
    quality,
    video_settings=None,
) -> Tuple[Optional[str], str, Dict[str, Any]]:
    critique_result = {"ok": True, "skipped": not is_critic_enabled(), "score": None, "issues": []}
    if not is_critic_enabled():
        return video_path, code, critique_result

    narration = scene_data.get("text", "")
    animation = scene_data.get("animation", "")
    events = scene_data.get("visual_events") or []

    critic_min = None
    critic_retries = None
    if video_settings:
        critic_min = video_settings.get("critic_min_score")
        critic_retries = video_settings.get("critic_max_retries")

    for attempt in range(critic_max_retries(override=critic_retries)):
        frames = extract_video_frames(video_path)
        critique = critique_scene_frames(
            llm_client,
            provider,
            model,
            frames,
            narration,
            animation,
            events,
            override_min_score=critic_min,
        )
        critique_result = critique
        if critique.get("ok") or critique.get("skipped"):
            return video_path, code, critique_result

        print(f"[CRITIC] Scene {index} score {critique.get('score')} — fixing visuals...")
        fix_prompt = build_critic_fix_prompt(
            code,
            critique,
            narration,
            animation=scene_data.get("animation", ""),
            visual_events=events,
        )
        try:
            response = complete_llm(
                client=llm_client,
                provider=provider,
                model=model,
                system_prompt="You fix Manim code based on visual critique feedback. Respond in JSON only.",
                user_prompt=fix_prompt,
            )
            result = extract_json_from_llm_response(response)
            fixed_code = result.get("content", code)
            fixed_class = result.get("class_name", class_name)
            new_path, final_code, _ = _compile_with_repl(
                llm_client,
                provider,
                model,
                filepath,
                fixed_code,
                fixed_class,
                topic_slug,
                index,
                quality,
                max_repl=2,
            )
            if new_path:
                video_path = new_path
                code = final_code
            else:
                break
        except Exception as exc:
            print(f"[CRITIC] Fix attempt failed: {exc}")
            break

    return video_path, code, critique_result


def generate_scene_code(
    llm_client,
    provider,
    model,
    scene_data,
    index,
    style_registry,
    previous_context,
    audio_duration,
    video_settings,
):
    scene_data = enrich_scene_events(scene_data)

    # Use custom Manim code if user provided it in the script editor
    custom_code = scene_data.get("code", "").strip()
    custom_class = scene_data.get("code_class", "").strip()
    if custom_code and custom_class:
        print(f"[Scene {index}] Using custom Manim code from script editor")
        return {"content": custom_code, "class_name": custom_class}

    registry_prompt = format_registry_for_prompt(style_registry)
    events_prompt = format_events_for_prompt(scene_data.get("visual_events"))

    # Search for similar code snippets
    snippet_context = ""
    try:
        query = f"{scene_data.get('text', '')}\n{scene_data.get('animation', '')}"
        similar = search_snippets_by_text(query, llm_client, provider, model, top_k=2)
        if similar:
            snippet_context = format_snippets_for_prompt(similar)
            print(f"[Scene {index}] Found {len(similar)} similar snippet(s)")
    except Exception as exc:
        print(f"[WARN] Snippet search failed: {exc}")

    enriched_context = dict(previous_context or {})
    enriched_context["style_registry"] = registry_prompt
    enriched_context["visual_events"] = events_prompt
    if snippet_context:
        enriched_context["similar_snippets"] = snippet_context

    return generate_manim_code(
        llm_client,
        scene_data.get("text", ""),
        scene_data.get("animation", ""),
        index,
        enriched_context,
        provider,
        model,
        audio_duration=audio_duration,
        video_settings=video_settings,
        visual_events=scene_data.get("visual_events"),
        scene_style=scene_data.get("style"),
    )


def compile_scene_from_code(
    llm_client,
    provider,
    model,
    scene_data,
    index,
    code_bundle,
    topic_slug,
    job_id,
    content_dir,
    quality,
    on_fix_message=None,
    video_settings=None,
) -> Tuple[Optional[str], str, Dict[str, Any]]:
    code_content = code_bundle.get("content", "")
    class_name = code_bundle.get("class_name", f"Scene{index}")
    filename = f"{topic_slug}-{job_id}-{index}.py"
    filepath = str(content_dir / filename)

    video_path, final_code, final_class = _compile_with_repl(
        llm_client,
        provider,
        model,
        filepath,
        code_content,
        class_name,
        topic_slug,
        index,
        quality,
        on_fix_message=on_fix_message,
    )
    if not video_path:
        return None, final_code, {"ok": False, "error": "compile_failed"}

    video_path, final_code, critique = _run_critic_loop(
        llm_client,
        provider,
        model,
        video_path,
        scene_data,
        filepath,
        final_code,
        final_class,
        topic_slug,
        index,
        quality,
        video_settings=video_settings,
    )
    return video_path, final_code, critique


def render_scenes_with_pipeline(
    job_id,
    video_data,
    topic_slug,
    content_dir,
    llm_client,
    provider,
    model,
    video_settings,
    quality,
    audio_durations,
    checkpoint,
    jobs,
    persist_fn,
    update_status_fn,
    start_index=1,
    jobs_lock=None,
):
    """
    Generate code sequentially (continuity), compile in parallel batches, checkpoint each scene.
    Returns ordered list of video paths.
    """
    total_scenes = len(video_data)
    style_registry = checkpoint.get("style_registry") or create_style_registry(video_settings)
    scene_codes = checkpoint.get("scene_codes") or {}
    scene_videos = checkpoint.get("scene_videos") or {}
    scene_results = checkpoint.get("scene_results") or {}
    previous_context = None

    ensure_not_cancelled(jobs, job_id, jobs_lock=jobs_lock)

    for idx in range(1, total_scenes + 1):
        key = str(idx)
        if key not in scene_codes:
            break
        scene_data = enrich_scene_events(video_data[idx - 1])
        code = scene_codes[key].get("content", "") if isinstance(scene_codes[key], dict) else ""
        previous_context = _build_context_from_checkpoint(scene_data, code)
        style_registry = update_style_registry(style_registry, scene_data, code)

    # Phase 1: sequential code generation (skip scenes that already have code)
    for index in range(1, total_scenes + 1):
        ensure_not_cancelled(jobs, job_id, jobs_lock=jobs_lock)
        key = str(index)
        scene_data = enrich_scene_events(video_data[index - 1])

        if key in scene_codes and scene_codes[key].get("content"):
            continue

        update_status_fn(
            progress=45 + ((index - 1) / total_scenes) * 15,
            message=f"Generating code for scene {index}/{total_scenes}...",
            scenes_done=index - 1,
        )

        audio_duration = audio_durations.get(index)
        manim_code = generate_scene_code(
            llm_client,
            provider,
            model,
            scene_data,
            index,
            style_registry,
            previous_context,
            audio_duration,
            video_settings,
        )
        if not manim_code:
            continue

        scene_codes[key] = manim_code
        checkpoint["scene_codes"] = scene_codes
        checkpoint["style_registry"] = style_registry
        save_checkpoint_to_job(jobs, job_id, checkpoint, persist_fn, jobs_lock=jobs_lock)

        code_content = manim_code.get("content", "")
        previous_context = _build_context_from_checkpoint(scene_data, code_content)
        style_registry = update_style_registry(style_registry, scene_data, code_content)
        checkpoint["style_registry"] = style_registry

    # Phase 2: parallel compilation for scenes missing video
    pending = [
        index
        for index in range(1, total_scenes + 1)
        if str(index) in scene_codes and str(index) not in scene_videos
    ]

    workers = parallel_workers()

    def compile_worker(index):
        key = str(index)
        scene_data = enrich_scene_events(video_data[index - 1])

        def on_fix(attempt, max_attempts):
            update_status_fn(
                message=f"Fixing scene {index} compile error (attempt {attempt}/{max_attempts})...",
            )

        return index, compile_scene_from_code(
            llm_client,
            provider,
            model,
            scene_data,
            index,
            scene_codes[key],
            topic_slug,
            job_id,
            content_dir,
            quality,
            on_fix_message=on_fix,
            video_settings=video_settings,
        )

    completed = 0
    if pending:
        ensure_not_cancelled(jobs, job_id, jobs_lock=jobs_lock)
        update_status_fn(
            progress=60,
            message=f"Rendering {len(pending)} scenes ({workers} parallel workers)...",
        )

        if workers == 1 or len(pending) == 1:
            results = []
            for scene_index in pending:
                ensure_not_cancelled(jobs, job_id, jobs_lock=jobs_lock)
                results.append(compile_worker(scene_index))
        else:
            results = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(compile_worker, i): i for i in pending}
                for future in as_completed(futures):
                    ensure_not_cancelled(jobs, job_id, jobs_lock=jobs_lock)
                    results.append(future.result())

        for index, compile_result in results:
            if len(compile_result) == 3:
                video_path, final_code, critique = compile_result
            else:
                video_path, final_code = compile_result
                critique = {}
            key = str(index)
            completed += 1
            score = critique.get("score")
            critic_msg = f" (critic: {score}/10)" if score is not None else ""
            scene_progress = 60 + (completed / max(len(pending), 1)) * 25
            update_status_fn(
                progress=scene_progress,
                message=f"Scene {index}/{total_scenes} rendered{critic_msg}",
                scenes_done=index,
                scene_result={"index": index, "critic": critique},
            )
            if video_path:
                scene_videos[key] = video_path
                scene_codes[key]["content"] = final_code
                scene_results[key] = critique
                checkpoint["scene_videos"] = scene_videos
                checkpoint["scene_codes"] = scene_codes
                checkpoint["scene_results"] = scene_results
                save_checkpoint_to_job(jobs, job_id, checkpoint, persist_fn, jobs_lock=jobs_lock)

    ordered_paths = []
    for index in range(1, total_scenes + 1):
        path = scene_videos.get(str(index))
        if path and os.path.exists(path):
            ordered_paths.append(path)

    return ordered_paths


def render_single_scene(
    jobs,
    job_id,
    video_data,
    scene_index,
    topic_slug,
    content_dir,
    llm_client,
    provider,
    model,
    video_settings,
    quality,
    audio_durations,
    checkpoint,
    persist_fn,
    regen_code=False,
    jobs_lock=None,
):
    """Re-render one scene (optionally regenerate code). Returns video path or None."""
    key = str(scene_index)
    scene_data = enrich_scene_events(video_data[scene_index - 1])
    scene_codes = checkpoint.get("scene_codes") or {}
    style_registry = checkpoint.get("style_registry") or create_style_registry(video_settings)

    if regen_code or key not in scene_codes:
        previous_context = None
        if scene_index > 1:
            prev_key = str(scene_index - 1)
            if prev_key in scene_codes:
                prev_scene = enrich_scene_events(video_data[scene_index - 2])
                previous_context = _build_context_from_checkpoint(
                    prev_scene, scene_codes[prev_key].get("content", "")
                )
        manim_code = generate_scene_code(
            llm_client,
            provider,
            model,
            scene_data,
            scene_index,
            style_registry,
            previous_context,
            audio_durations.get(scene_index),
            video_settings,
        )
        if not manim_code:
            return None
        scene_codes[key] = manim_code
        checkpoint["scene_codes"] = scene_codes

    video_path, final_code, critique = compile_scene_from_code(
        llm_client,
        provider,
        model,
        scene_data,
        scene_index,
        scene_codes[key],
        topic_slug,
        job_id,
        content_dir,
        quality,
        video_settings=video_settings,
    )
    if video_path:
        checkpoint.setdefault("scene_videos", {})[key] = video_path
        checkpoint.setdefault("scene_results", {})[key] = critique
        scene_codes[key]["content"] = final_code
        save_checkpoint_to_job(jobs, job_id, checkpoint, persist_fn, jobs_lock=jobs_lock)
    return video_path


def _build_context_from_checkpoint(scene_data, code):
    return {
        "text": scene_data.get("text", ""),
        "animation": scene_data.get("animation", ""),
        "code": code if isinstance(code, str) else code.get("content", ""),
        "chapter": scene_data.get("chapter"),
        "title": scene_data.get("title"),
        "visual_events": scene_data.get("visual_events"),
    }
