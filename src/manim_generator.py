import json
import time

from env_loader import load_app_env
from json_utils import extract_json_from_llm_response
from llm_chat import complete_llm

load_app_env()


def generate_manim_code(
    client,
    text,
    animation,
    index,
    previous_context=None,
    provider="openai",
    model="gpt-4o",
    audio_duration=None,
    video_settings=None,
    visual_events=None,
    max_retries=3,
    scene_style=None,
):
    """Generates Manim code using the LLM with style registry, visual events, and retries."""
    from video_settings import normalize_video_settings
    from visual_events import format_events_for_prompt, normalize_visual_events

    video_settings = normalize_video_settings(video_settings)
    style_guide = video_settings["style_preset"]["visual_style"]
    scene_duration = video_settings["length_preset"]["scene_duration_sec"]

    events = normalize_visual_events(visual_events)
    if not events and previous_context:
        events = normalize_visual_events(previous_context.get("visual_events"))
    events_section = f"""
REQUIRED VISUAL EVENTS (implement ALL of these in the animation):
{format_events_for_prompt(events)}
"""

    # Build context section if it exists
    context_section = ""
    snippet_block = previous_context.get("similar_snippets", "") if previous_context else ""
    if previous_context:
        registry_block = previous_context.get("style_registry") or ""
        context_section = f"""
PREVIOUS SCENE CONTEXT (maintain continuity):
- Previous text: {previous_context.get('text', 'N/A')}
- Previous animation: {previous_context.get('animation', 'N/A')}
{registry_block}
- Previous generated code (reference for style continuity):
```python
{previous_context.get('code', 'N/A')}
```
{snippet_block}
"""
    else:
        context_section = f"""
CONTEXT: This is the FIRST scene of the video.
{snippet_block}
"""

    # Add audio duration information if available
    duration_section = ""
    if audio_duration:
        duration_section = f"""
CRITICAL AUDIO SYNCHRONIZATION:
- This scene has an audio narration that lasts EXACTLY {audio_duration:.2f} seconds
- Your animation MUST last EXACTLY {audio_duration:.2f} seconds (not more, not less)
- TIMING STRATEGY (beat-based, not naive division):
  1. Read the narration text carefully. Identify the KEY BEATS (moments where a new concept, term, or visual element is introduced).
  2. Time each animation so the visual element appears AT or JUST BEFORE its corresponding narrative beat — NOT spread evenly.
  3. Use self.wait() at NATURAL PAUSES in the narration (after a key reveal, before a transition).
  4. Important reveals should use run_time=1.5-2.5s so the viewer can absorb them.
  5. Quick transitions between related elements should use run_time=0.6-1.0s.
  6. The total of all animation run_times + wait times MUST equal {audio_duration:.2f}s.
  7. BREATHING ROOM IS MANDATORY: after every key visual reveal, add self.wait(1.0). After the aha moment, self.wait(2.0).
- Example timing for a 10s narration with 3 beats:
  * Beat 1 (0s): "The derivative tells us the slope" -> Show title + equation (run_time=2s)
  * Wait 1.0s
  * Beat 2 (3.5s): "At this point, the slope is zero" -> Highlight the point (run_time=1.5s)
  * Wait 1.0s
  * Beat 3 (6s): "So we have a maximum" -> Show result label (run_time=1.5s)
  * Wait 2.0s at the end for the viewer to absorb
"""
    else:
        duration_section = f"""
TIMING GUIDANCE:
- This scene should last approximately {scene_duration} seconds
- Use beat-based timing: match animation moments to narrative beats
- Important reveals: run_time=1.5-2.5s; quick transitions: run_time=0.6-1.0s
- BREATHING ROOM IS MANDATORY: after every key visual reveal, add self.wait(1.0). After the aha moment, self.wait(2.0).
- Total animation time should match ~{scene_duration}s
"""

    quality_guidance = video_settings.get("quality_preset", {}).get("prompt_guidance", "")
    quality_block = f"\nQUALITY GUIDANCE:\n{quality_guidance}\n" if quality_guidance else ""

    # Scene style overrides
    style_override_section = ""
    if scene_style:
        palette = scene_style.get("palette")
        speed = scene_style.get("speed")
        font_size = scene_style.get("font_size")
        overrides = []
        if palette == "warm":
            overrides.append("Use a WARM palette: #FF6B6B (coral), #FFD93D (yellow), #F4A261 (orange), #E76F51 (terracotta). Background stays #1a1a2e.")
        elif palette == "cool":
            overrides.append("Use a COOL palette: #58C4DD (cyan), #4ECDC4 (teal), #45B7D1 (sky), #96CEB4 (sage). Background stays #1a1a2e.")
        elif palette == "monochrome":
            overrides.append("Use a MONOCHROME palette: #E2E8F0 (white), #94A3B8 (light gray), #475569 (medium gray), #1E293B (dark gray). Background stays #1a1a2e.")
        elif palette == "vibrant":
            overrides.append("Use a VIBRANT high-contrast palette: #FF006E (magenta), #FB5607 (orange), #8338EC (purple), #06FFB4 (neon green). Background stays #1a1a2e.")
        elif palette == "pastel":
            overrides.append("Use a PASTEL palette: #FFB3BA (pink), #FFDFBA (peach), #FFFFBA (lemon), #BAFFC9 (mint), #BAE1FF (baby blue). Background stays #1a1a2e.")
        if speed == "slow":
            overrides.append("ANIMATION SPEED: Use 2× longer run_time values. Reveals: 3.0-4.0s. Transitions: 1.0-1.5s. Add extra self.wait(1.5) after key moments.")
        elif speed == "fast":
            overrides.append("ANIMATION SPEED: Use 0.5× shorter run_time values. Reveals: 0.8-1.2s. Transitions: 0.3-0.5s. Keep waits minimal (0.5s).")
        if font_size:
            overrides.append(f"FONT SIZE OVERRIDE: Base all text sizes around {font_size}px. Titles: {font_size + 12}px, Headers: {font_size + 6}px, Body: {font_size}px, Labels: {font_size - 6}px.")
        if overrides:
            style_override_section = "\nSCENE STYLE OVERRIDES (apply these to THIS scene only):\n" + "\n".join(f"- {o}" for o in overrides) + "\n"

    style_section = f"""
VISUAL STYLE GUIDE (maintain consistency with other scenes):
{style_guide}
- Use self.camera.background_color = "#1a1a2e" at the start of construct()
- Match fonts, colors, and layout from previous scenes when context is provided
{quality_block}
{style_override_section}

COLOR PALETTE SYSTEM (use ONLY these 4-5 colors per video):
- Background: "#1a1a2e" (very dark blue-purple)
- Primary:    "#58C4DD" (3Blue1Blue cyan) or "#6366f1" (indigo)
- Secondary:  "#83C167" (green) or "#FFD93D" (warm yellow)
- Accent:     "#FFFF00" (yellow) or "#FF6B6B" (coral)
- Text:       "#E2E8F0" (soft white)
- NEVER use more than 5 distinct colors in one scene
- NEVER use raw RED/GREEN/BLUE as primary element colors (use the palette hexes above)

OPACITY & VISUAL SALIENCE (direct the viewer's eye):
- PRIMARY element (the thing being explained): opacity 1.0, full brightness
- SECONDARY elements (supporting labels, context): opacity 0.5-0.7
- STRUCTURAL elements (axes, grids, backgrounds): opacity 0.15-0.25
- Example: axis lines at 0.2, the curve at 1.0, annotations at 0.6

TYPOGRAPHY HIERARCHY (consistent sizing):
- Scene title: font_size=48, weight=BOLD
- Section header: font_size=36
- Body explanation: font_size=30
- Label/annotation: font_size=24
- Minimum readable size: font_size=20
- Use monospace font when possible: Text("...", font="Monospace")

BREATHING ROOM (critical for comprehension):
- After EVERY key reveal: self.wait(1.0) minimum
- After an "aha" equation or transformation: self.wait(2.0)
- After scene title appears: self.wait(1.5)
- Never chain animations without a pause between concepts
- The viewer needs time to absorb; pauses are NEVER wasted

EASING & MOTION (make it feel alive, not robotic):
- Default: rate_func=smooth for ALL movements and fades
- Mechanical processes only: rate_func=linear
- Playful emphasis: rate_func=rate_functions.ease_out_bounce (rarely)
- Important reveals: run_time=2.0-2.5s
- Quick transitions: run_time=0.6-1.0s
- Text writes: run_time=1.5-2.0s
"""

    prompt = f"""{context_section}
{events_section}
{style_section}

Generate Python code for Manim that implements this educational animation.

CURRENT CONTENT:
- Narrative text: {text}
- Animation description: {animation}

{duration_section}

IMPORTANT TECHNICAL RESTRICTIONS:
1. The class MUST inherit from Scene (not MovingCameraScene, not ThreeDScene)
2. DO NOT use self.camera.frame (doesn't exist in Scene)
3. For zoom, use: object.animate.scale(factor) instead of camera.frame
4. Keep animations SIMPLE and FUNCTIONAL
5. Use only basic animations: Write, Create, FadeIn, FadeOut, Transform, ReplacementTransform
6. Avoid complex 3D animations
7. If you need camera movement, use self.play(self.camera.animate.move_to(...)) but WITHOUT .frame
8. NEVER create empty Text or Paragraph objects (Text('') or Paragraph(''))
9. NEVER use positioning methods (.move_to(), .align_to(), .next_to()) on empty Text/Paragraph objects
10. If you need placeholder text, use actual text like Text("Placeholder") instead of Text('')

CRITICAL COLOR USAGE RULES:
1. ONLY use these basic colors that are always available: WHITE, BLACK, RED, GREEN, BLUE, YELLOW, PURPLE, ORANGE, PINK, GRAY
2. DO NOT use color variants like RED_A, RED_B, ORANGE_D, BLUE_E, etc. (they may not be imported)
3. If you need custom colors, use hex codes: color="#FF5733" or RGB: rgb_to_color([1, 0.5, 0.2])
4. For gradients or multiple colors, stick to the basic colors listed above
5. Example CORRECT usage: Circle(color=RED), Text("Hello", color=BLUE)
6. Example INCORRECT usage: Circle(color=ORANGE_D), Text("Hello", color=RED_A)

CRITICAL RULES TO AVOID TEXT OVERLAP:
VERY IMPORTANT - SCREEN SPACE MANAGEMENT:
1. ALWAYS use FadeOut() to remove old elements BEFORE showing new ones
2. If showing multiple texts/objects, position them in DIFFERENT places (UP, DOWN, LEFT, RIGHT)
3. Use self.clear() if you need to clear the entire scene
4. DO NOT write new text over existing text without removing it first
5. Keep a maximum of 2-3 text elements on screen simultaneously
6. Use .to_edge(UP/DOWN) or .shift(UP/DOWN) to separate elements vertically

GOOD PRACTICE EXAMPLE:
```python
# Show first text
text1 = Text("First concept")
self.play(Write(text1))
self.wait(1)

# REMOVE before showing the next one
self.play(FadeOut(text1))  # CORRECT

# Now show second text
text2 = Text("Second concept")
self.play(Write(text2))
self.wait(1)
```

BAD PRACTICE EXAMPLE (DON'T DO THIS):
```python
text1 = Text("First concept")
self.play(Write(text1))
text2 = Text("Second concept")  # INCORRECT - overlaps
self.play(Write(text2))
```

RULES TO CONTROL TEXT WIDTH:
CRITICAL - TEXT MUST NOT GO OFF SCREEN:
1. For LONG texts (>80 characters), use Paragraph() instead of Text()
2. Use the width parameter to limit width: Text("...", width=10) or Paragraph("...", width=11)
3. Appropriate font size: font_size=24-36 for long texts, 40-48 for short titles
4. If the text is VERY long, divide it into multiple Text/Paragraph objects
5. Use line_spacing in Paragraph for better readability
6. Maximum recommended width is width=12 (to leave margins)

EXAMPLE FOR LONG TEXTS:
```python
# CORRECT - Long text with Paragraph
long_text = Paragraph(
    'This is a very long text that needs to be displayed on screen without going off the edges.',
    width=11,  # Limit width
    font_size=28,
    line_spacing=1.2
)
self.play(Write(long_text))
self.wait(2)
self.play(FadeOut(long_text))
```

EXAMPLE FOR SHORT TEXTS:
```python
# CORRECT - Short text with Text
short_text = Text("Short title", font_size=48)
self.play(Write(short_text))
```

EXAMPLE DIVIDING LONG TEXT:
```python
# CORRECT - Divide into parts
part1 = Paragraph("First part of long text...", width=11, font_size=30).to_edge(UP)
self.play(Write(part1))
self.wait(2)
self.play(FadeOut(part1))

part2 = Paragraph("Second part of text...", width=11, font_size=30).to_edge(UP)
self.play(Write(part2))
```

RECOMMENDED ANIMATIONS:
- Text: Write(), FadeIn(), AddTextLetterByLetter()
- Shapes: Create(), DrawBorderThenFill(), GrowFromCenter()
- Transformations: Transform(), ReplacementTransform(), TransformFromCopy(), TransformMatchingShapes()
- Emphasis & attention: Circumscribe(), Indicate(), Flash(), Wiggle(), ShowPassingFlash()
- Movement: obj.animate.shift(), obj.animate.move_to(), obj.animate.scale()
- Cleanup: FadeOut(), self.clear(), self.remove()
- Groups: VGroup to group objects

EASING & TIMING (make motion feel alive, not robotic):
- Use rate_func=smooth for natural acceleration/deceleration
- Use rate_func=run_time=2 for important reveals, rate_func=run_time=0.5 for quick transitions
- Animate elements in sequence using lagged_start or successive self.play() calls
- Let important concepts linger on screen; don't rush everything equally

CODE STRUCTURE:
```python
from manim import *

class ClassName(Scene):
    def construct(self):
        # Your code here
        # Simple example:
        text = Text("Hello")
        self.play(Write(text))
        self.wait(1)
        # Clean before next element
        self.play(FadeOut(text))
```

RESPONSE FORMAT (JSON):
{{
  "content": "complete Python code here (use single quotes inside the code)",
  "class_name": "ClassName"
}}

IMPORTANT: 
- The code must be executable without errors
- Escape quotes correctly in the JSON
- Keep the animation simple but effective
- ALWAYS clean old elements before showing new ones
"""

    # Retry loop for handling API failures
    for attempt in range(max_retries):
        try:
            print(f"[Scene {index}] Generating Manim code... (Attempt {attempt + 1}/{max_retries})")

            system_prompt = (
                "You are an expert in Manim Community Edition (v0.19.1). You generate simple, "
                "functional Python code without errors. NEVER use self.camera.frame in Scene. "
                "Always respond in valid JSON format."
            )
            response_text = complete_llm(
                client=client,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt,
            )

            # Check for empty response
            if len(response_text) == 0:
                print(f"[ERROR] Empty response from {provider} API for scene {index}")
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(f"[RETRY] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Max retries reached for scene {index}. Giving up.")
                    return None

            try:
                result = extract_json_from_llm_response(response_text)
                print(f"[OK] Manim code generated for scene {index}")
                return result
            except ValueError as json_err:
                print(f"[ERROR] Failed to parse JSON for scene {index}: {json_err}")

                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(f"[RETRY] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Max retries reached for scene {index}. Giving up.")
                    return None

        except Exception as e:
            print(f"[ERROR] Error generating code for scene {index}: {e}")

            if attempt < max_retries - 1:
                wait_time = 2**attempt
                print(f"[RETRY] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                print(f"[ERROR] Max retries reached for scene {index}. Giving up.")
                return None

    # Should never reach here
    return None


def fix_manim_code(
    client,
    original_code,
    error_message,
    class_name,
    provider="openai",
    model="gpt-4o",
    max_fix_attempts=3,
):
    """
    REPL-style function to fix Manim code based on compilation errors.
    Sends the error to the LLM and gets corrected code.

    Args:
        client: LLM client (OpenAI or Anthropic)
        original_code: The Python code that failed to compile
        error_message: The error message from Manim compilation
        class_name: The class name in the code
        provider: 'openai' or 'claude'
        model: Model name
        max_fix_attempts: Maximum number of fix attempts

    Returns:
        dict: {'content': fixed_code, 'class_name': class_name} or None if all attempts fail
    """

    current_code = original_code

    for attempt in range(max_fix_attempts):
        print(f"\n[REPL] Fixing code... (Attempt {attempt + 1}/{max_fix_attempts})")

        fix_prompt = f"""The following Manim code failed to compile with an error. Please fix the code.

CURRENT CODE:
```python
{current_code}
```

ERROR MESSAGE:
```
{error_message}
```

IMPORTANT RULES:
1. Fix ONLY the error mentioned - don't change working parts
2. The class MUST inherit from Scene (not MovingCameraScene, not ThreeDScene)
3. DO NOT use self.camera.frame (doesn't exist in Scene)
4. ONLY use basic colors: WHITE, BLACK, RED, GREEN, BLUE, YELLOW, PURPLE, ORANGE, PINK, GRAY
5. DO NOT use color variants like RED_A, RED_B, ORANGE_D, BLUE_E, etc.
6. For custom colors, use hex codes: color="#FF5733"
7. NEVER create empty Text or Paragraph objects
8. Use only basic animations: Write, Create, FadeIn, FadeOut, Transform, ReplacementTransform

RESPONSE FORMAT (JSON):
{{
  "content": "complete fixed Python code here",
  "class_name": "{class_name}",
  "fix_explanation": "brief explanation of what was fixed"
}}

Respond ONLY with valid JSON."""

        try:
            system_prompt = (
                "You are an expert debugger for Manim Community Edition (v0.19.1). You fix Python "
                "code errors. Always respond in valid JSON format."
            )
            response_text = complete_llm(
                client=client,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_prompt=fix_prompt,
            )

            if len(response_text) == 0:
                print("[REPL] Empty response from LLM")
                continue

            result = extract_json_from_llm_response(response_text)

            fix_explanation = result.get("fix_explanation", "No explanation provided")
            print(f"[REPL] Fix applied: {fix_explanation}")

            return {
                "content": result.get("content", ""),
                "class_name": result.get("class_name", class_name),
            }

        except json.JSONDecodeError as json_err:
            print(f"[REPL] Failed to parse fix response: {json_err}")
            continue
        except Exception as e:
            print(f"[REPL] Error during fix attempt: {e}")
            continue

    print("[REPL] Max fix attempts reached. Giving up.")
    return None
