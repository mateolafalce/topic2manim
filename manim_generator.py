import json
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_manim_code(client, text, animation, index, previous_context=None, provider='openai', model='gpt-4o', audio_duration=None):
    """Generates Manim code using the LLM with previous scene context and audio duration"""
    
    # Build context section if it exists
    context_section = ""
    if previous_context:
        context_section = f"""
PREVIOUS SCENE CONTEXT (to maintain continuity):
- Previous text: {previous_context.get('text', 'N/A')}
- Previous animation: {previous_context.get('animation', 'N/A')}
- Previous generated code:
```python
{previous_context.get('code', 'N/A')}
```

IMPORTANT: Maintain visual and narrative coherence with the previous scene.
If the previous scene ended with certain elements or style, consider that when designing this scene.
"""
    else:
        context_section = """
CONTEXT: This is the FIRST scene of the video.
"""
    
    # Add audio duration information if available
    duration_section = ""
    if audio_duration:
        duration_section = f"""
CRITICAL AUDIO SYNCHRONIZATION:
- This scene has an audio narration that lasts EXACTLY {audio_duration:.2f} seconds
- Your animation MUST last EXACTLY {audio_duration:.2f} seconds (not more, not less)
- Calculate your animation timings to match this duration:
  * Use self.wait() strategically to fill the time
  * Adjust run_time parameters in animations to fit within {audio_duration:.2f}s
  * The total of all animation run_times + wait times MUST equal {audio_duration:.2f}s
- Example timing breakdown for {audio_duration:.2f}s:
  * If you have 3 animations, each could be ~{audio_duration/3:.2f}s
  * Include small waits between animations for better pacing
"""
    else:
        duration_section = """
TIMING GUIDANCE:
- This scene should last approximately 6-8 seconds
- Use short run_time in animations (0.5-1.5 seconds)
- Minimize use of self.wait() (maximum 0.5-1 second)
"""
    
    prompt = f"""{context_section}

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
- Transformations: Transform(), ReplacementTransform(), TransformFromCopy()
- Movement: obj.animate.shift(), obj.animate.move_to(), obj.animate.scale()
- Cleanup: FadeOut(), self.clear(), self.remove()
- Groups: VGroup to group objects

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
    
    try:
        if provider == 'openai':
            # OpenAI API call
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert in Manim Community Edition (v0.19.1). You generate simple, functional Python code without errors. NEVER use self.camera.frame in Scene. Always respond in valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5  # Reduced for more consistency
            )
            response_text = response.choices[0].message.content.strip()
            
        elif provider == 'claude':
            # Claude API call
            response = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.5,
                system="You are an expert in Manim Community Edition (v0.19.1). You generate simple, functional Python code without errors. NEVER use self.camera.frame in Scene. Always respond in valid JSON format.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = response.content[0].text.strip()
        
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Try to extract JSON if wrapped in markdown
        if "```json" in response_text:
            response_text = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        elif "```" in response_text:
            response_text = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        
        result = json.loads(response_text)
        return result
        
    except Exception as e:
        print(f"Error generating code for scene {index}: {e}")
        return None
