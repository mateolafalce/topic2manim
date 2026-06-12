import json
import time

from env_loader import load_app_env
from json_utils import extract_json_from_llm_response
from llm_chat import complete_llm
from llm_errors import format_llm_error
from video_settings import normalize_video_settings
from visual_events import enrich_scene_events, normalize_visual_events


def _build_script_prompt(topic_name, video_settings, narrative_context=""):
    length = video_settings["length_preset"]
    style = video_settings["style_preset"]
    scene_count = length["scene_count"]
    scene_min = max(scene_count - 1, 4)
    scene_max = scene_count + 1
    max_sentences = length["max_sentences"]

    narrative_section = f"\n{narrative_context}\n" if narrative_context else ""

    return f"""Develop an educational script for this topic: {topic_name}

AUDIENCE & TONE:
- Target audience: {style['audience']}
- Tone: {style['tone']}

VISUAL CONSISTENCY (apply to EVERY scene's animation description):
{style['visual_style']}
{narrative_section}
NARRATIVE STRUCTURE (follow this arc):
- Scene 1 (HOOK): Open with a question, paradox, or counter-intuitive claim. NEVER start with "Today we will learn about..."
- Scenes 2-3 (SETUP): Establish the problem or misconception. Show the intuitive but WRONG approach briefly.
- Middle scenes (BUILD): Develop the correct idea with visual intuition BEFORE formulas.
- Aha scene (REVEAL): The key insight gets extra breathing room and a dramatic visual.
- Final scenes (PAYOFF + CLOSE): Connect to real world, summarize the single takeaway.

INSTRUCTIONS:
- Create an engaging and educational script about the topic
- Divide the script into exactly {scene_count} logical scenes (acceptable range: {scene_min}-{scene_max})
- For each scene, provide:
  1. The script text (narration) — concise narration for voice-over
  2. A detailed description of the Manim animation that should accompany that text
- Avoid commercial logos (ChatGPT, OpenAI, etc.)
- I DON'T want Python Manim code, only animation descriptions
- Animations must be specific enough to implement in Manim
- Maintain the SAME visual style, color palette, and layout rules across ALL scenes
- Scene 1 should introduce the topic with a title card matching the style guide
- Final scene should summarize the key takeaway

LANGUAGE REQUIREMENT:
- The script and animations MUST be in the SAME LANGUAGE as the topic
- Match the language exactly

TIMING (CRITICAL):
- Total video duration: approximately {length['duration_sec']} seconds
- Each scene: approximately {length['scene_duration_sec']} seconds of narration
- Each scene text: maximum {max_sentences} short sentences
- Animations must be SIMPLE and paced to match narration length
- The aha-moment scene (usually the middle scene) should have the MOST detailed visual description

OUTPUT FORMAT (JSON):
Respond ONLY with a valid JSON array. Each element:
{{
  "text": "narration for this scene ({max_sentences} sentences max)",
  "animation": "detailed animation description following the visual style guide",
  "visual_events": ["show_title", "show_axes"],
  "title": "optional short scene title",
  "chapter": "optional chapter name"
}}

Available visual_events ids: show_title, show_axes, plot_function, show_equation, highlight_term, show_graph, show_geometry, show_arrow, show_label, transform_shape, step_reveal, show_table, show_number_line, compare_objects, summarize

IMPORTANT: Respond ONLY with the JSON array, no extra text."""


def _coerce_scene_field(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("description", "text", "content", "summary"):
            if value.get(key):
                return str(value[key]).strip()
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def validate_script_scenes(script_data, min_scenes=2):
    """Validate edited script structure before rendering."""
    if not isinstance(script_data, list) or len(script_data) < min_scenes:
        raise ValueError(f"Script must be a list of at least {min_scenes} scenes")

    normalized = []
    for index, scene in enumerate(script_data, 1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be an object")
        text = _coerce_scene_field(scene.get("text"))
        animation = _coerce_scene_field(scene.get("animation"))
        if not text:
            raise ValueError(f"Scene {index} is missing narration text")
        if not animation:
            raise ValueError(f"Scene {index} is missing animation description")
        entry = {"text": text, "animation": animation}
        if scene.get("title"):
            entry["title"] = str(scene["title"]).strip()
        if scene.get("chapter"):
            entry["chapter"] = str(scene["chapter"]).strip()
        events = normalize_visual_events(scene.get("visual_events"))
        if events:
            entry["visual_events"] = events
        normalized.append(enrich_scene_events(entry))

    return normalized


def generate_script_json(
    client,
    topic_name,
    output_file="video-output.json",
    provider="openai",
    model="gpt-4o",
    video_settings=None,
    max_retries=3,
    on_retry=None,
    narrative_plan=None,
):
    """Generates the JSON file with script and animations using the LLM with automatic retries."""
    load_app_env()
    video_settings = normalize_video_settings(video_settings)

    narrative_context = ""
    if narrative_plan:
        from narrative_planner import plan_to_prompt_context
        narrative_context = plan_to_prompt_context(narrative_plan)

    prompt = _build_script_prompt(topic_name, video_settings, narrative_context)

    last_error = "Unknown script generation error"
    system_prompt = (
        "You are an expert in creating educational video scripts with consistent visual "
        "design. You always respond in valid JSON format without additional text. "
        "Match the language of the topic exactly."
    )

    for attempt in range(max_retries):
        try:
            print(f"Generating script for: {topic_name}... (Attempt {attempt + 1}/{max_retries})")

            response_text = complete_llm(
                client=client,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt,
            )

            if not response_text:
                raise ValueError(f"Empty response from {provider}")

            script_data = extract_json_from_llm_response(response_text)
            script_data = validate_script_scenes(script_data)

            with open(output_file, "w", encoding="utf-8") as handle:
                json.dump(script_data, handle, ensure_ascii=False, indent=2)

            print(f"[OK] Script generated successfully: {output_file}")
            print(f"Total scenes: {len(script_data)}")
            return script_data, None

        except Exception as exc:
            last_error = format_llm_error(exc)
            print(f"[ERROR] Error generating script: {last_error}")

            if on_retry:
                on_retry(attempt + 1, max_retries, last_error)

            if attempt < max_retries - 1:
                wait_time = 2**attempt
                print(f"[RETRY] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            import traceback

            traceback.print_exc()
            return None, last_error

    return None, last_error
