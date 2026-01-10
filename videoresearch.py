#!/usr/bin/env python3
import os
import json
import subprocess
import re
import openai
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration variables
api_key = os.getenv('OPENAI_API_KEY')
model = os.getenv("OPENAI_MODEL", "gpt-4o")
topic = os.getenv("TOPIC", "how_chat_gpt_works")


def setup_openai():
    """Sets up the OpenAI client using the API key from environment"""
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured in environment variables")
    
    client = openai.OpenAI(api_key=api_key)
    return client


def generate_script_json(client, topic_name, output_file="video-output.json"):
    """Generates the JSON file with script and animations using the LLM"""
    prompt = f"""Develop an educational script for this topic: {topic_name}

INSTRUCTIONS:
- Create an engaging and educational script about the topic
- Divide the script into logical scenes/fragments (between 6-8 scenes)
- For each scene, provide:
  1. The script text (narration) - BRIEF and CONCISE
  2. A detailed description of the Manim animation that should accompany that text
- Avoid using commercial logos (like ChatGPT, OpenAI, etc.)
- I DON'T want Python Manim code, just the description of what you want to visualize
- Animations should be specific and detailed so they can be implemented in Manim

LANGUAGE REQUIREMENT:
- The script and animations MUST be in the SAME LANGUAGE as the topic
- If the topic is in Spanish, write everything in Spanish
- If the topic is in English, write everything in English
- Match the language exactly

CRITICAL TIME RESTRICTION:
- The COMPLETE video must last MAXIMUM 60 seconds (1 minute)
- Each scene should last approximately 6-8 seconds
- The text of each scene must be SHORT (maximum 2-3 sentences)
- Animations must be SIMPLE and FAST

OUTPUT FORMAT (JSON):
Respond ONLY with a valid JSON array, where each element has this structure:
{{
  "text": "script text for this scene (BRIEF, 2-3 sentences maximum)",
  "animation": "detailed description of the specific animation for this fragment"
}}

Example of a scene:
{{
  "text": "Language models process text by converting it into numbers.",
  "animation": "Show the word 'Hello' in the center. Then, divide it into visual tokens with colored boxes. Finally, transform each token into a number (ID) with a morphing animation."
}}

IMPORTANT: Respond ONLY with the JSON array, without any additional text before or after."""

    try:
        print(f"Generating script for: {topic_name}...")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert in creating educational video scripts. You always respond in valid JSON format without additional text. IMPORTANT: Match the language of the topic exactly - if the topic is in Spanish, write in Spanish; if in English, write in English."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_completion_tokens=4000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Intentar extraer JSON si está envuelto en markdown
        if "```json" in response_text:
            response_text = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        elif "```" in response_text:
            response_text = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        
        # Parse JSON
        script_data = json.loads(response_text)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Script generated successfully: {output_file}")
        print(f"Total scenes: {len(script_data)}")
        
        return script_data
        
    except Exception as e:
        print(f"[ERROR] Error generating script: {e}")
        return None


def generate_manim_code(client, text, animation, index, previous_context=None):
    """Generates Manim code using the LLM with previous scene context"""
    
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
    
    prompt = f"""{context_section}

Generate Python code for Manim that implements this educational animation.

CURRENT CONTENT:
- Narrative text: {text}
- Animation description: {animation}

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

CRITICAL TIME RESTRICTION:
- This scene must last MAXIMUM 6-8 seconds
- Use short run_time in animations (0.5-1.5 seconds)
- Minimize use of self.wait() (maximum 0.5-1 second)
- Keep animations FAST and DYNAMIC
- The complete video will be ~60 seconds, so each scene must be BRIEF

IMPORTANT: 
- The code must be executable without errors
- Escape quotes correctly in the JSON
- Keep the animation simple but effective
- Total duration: depends on text length
- ALWAYS clean old elements before showing new ones
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert in Manim Community Edition (v0.19.1). You generate simple, functional Python code without errors. NEVER use self.camera.frame in Scene. Always respond in valid JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5  # Reduced for more consistency
        )
        
        response_text = response.choices[0].message.content.strip()
        
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


def compile_video(file_path, class_name, topic_slug, index):
    """Compiles the video using Manim"""
    try:
        cmd = ["manim", "-pql", file_path, class_name]
        print(f"\nCompiling: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            print(f"[OK] Video compiled successfully")
            # Video will be in media/videos/{filename_without_extension}/480p15/{class_name}.mp4
            video_path = f"media/videos/{topic_slug}-{index}/480p15/{class_name}.mp4"
            return video_path
        else:
            print(f"[ERROR] Error compiling video:")
            print(result.stderr)
            return None
            
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout compiling video")
        return None
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return None


def concatenate_videos(video_paths, output_path):
    """Joins all videos into one using ffmpeg"""
    if not video_paths:
        print("[ERROR] No videos to concatenate")
        return False
    
    # Create media folder if it doesn't exist
    os.makedirs("media", exist_ok=True)
    
    # Create list file for ffmpeg
    list_file = "media/video_list.txt"
    with open(list_file, 'w') as f:
        for video_path in video_paths:
            if os.path.exists(video_path):
                f.write(f"file '../{video_path}'\n")
    
    try:
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
            "-y"  # Overwrite if exists
        ]
        
        print(f"\n  Concatenating videos...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"[OK] Final video created: {output_path}")
            # Clean up temporary file
            os.remove(list_file)
            return True
        else:
            print(f"[ERROR] Error concatenating videos:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False


def main():
    
    content_dir = "content"
    if not os.path.exists(content_dir):
        os.makedirs(content_dir)
        print(f"Folder '{content_dir}' created successfully\n")
    else:
        print(f"Folder '{content_dir}' already exists\n")
    
    # Path to JSON file
    json_file = "video-output.json"
    
    # Configure OpenAI
    try:
        client = setup_openai()
        print("[OK] OpenAI client configured\n")
    except Exception as e:
        print(f"[ERROR] Error configuring OpenAI: {e}")
        return
    
    # Generate new script ALWAYS (every execution)
    print(f"Generating new script for: {topic}...\n")
    video_data = generate_script_json(client, topic, json_file)
    
    if not video_data:
        print(f"[ERROR] Could not generate script. Aborting.")
        return
    
    print(f"\n{'='*80}")
    print(f"SCRIPT GENERATED")
    print(f"{'='*80}\n")
    
    # Show script preview
    for i, scene in enumerate(video_data[:3], 1):  # Show only first 3
        print(f"Scene {i}:")
        print(f"  Text: {scene.get('text', '')[:80]}...")
        print(f"  Animation: {scene.get('animation', '')[:80]}...")
        print()
    
    if len(video_data) > 3:
        print(f"... and {len(video_data) - 3} more scenes\n")
    
    # Read JSON file (just generated)
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            video_data = json.load(f)
        print(f"Loaded {len(video_data)} scenes from {json_file}\n")
    except FileNotFoundError:
        print(f"[ERROR] Error: File '{json_file}' not found")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Error decoding JSON: {e}")
        return
    
    # Create topic slug (no spaces, lowercase)
    topic_slug = topic.lower().replace(" ", "_")
    
    # List to save generated video paths
    generated_videos = []
    
    # Variable to save previous scene context
    previous_context = None
    
    # Iterate over each scene
    for index, scene_data in enumerate(video_data, 1):
        print(f"\n{'='*80}")
        print(f"PROCESSING SCENE {index}/{len(video_data)}")
        print(f"{'='*80}")
        
        text = scene_data.get('text', '')
        animation = scene_data.get('animation', '')
        
        print(f"Text: {text[:100]}...")
        print(f"Animation: {animation[:100]}...")
        
        # Generate code with LLM (passing previous scene context)
        print(f"\nGenerating Manim code with LLM...")
        if previous_context:
            print(f"   Using previous scene context")
        manim_code = generate_manim_code(client, text, animation, index, previous_context)
        
        if not manim_code:
            print(f"[WARNING] Skipping scene {index}")
            continue
        
        code_content = manim_code.get('content', '')
        class_name = manim_code.get('class_name', f'Scene{index}')
        
        # Create Python file
        filename = f"{topic_slug}-{index}.py"
        filepath = os.path.join(content_dir, filename)
        
        print(f"Saving code to: {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code_content)
        
        # Compile video
        video_path = compile_video(filepath, class_name, topic_slug, index)
        
        if video_path and os.path.exists(video_path):
            generated_videos.append(video_path)
            print(f"[OK] Video {index} generated: {video_path}")
            
            # Update context for next scene
            previous_context = {
                'text': text,
                'animation': animation,
                'code': code_content
            }
        else:
            print(f"[WARNING] Could not generate video {index}")
    
    # Concatenate all videos
    if generated_videos:
        print(f"\n{'='*80}")
        print(f"CONCATENATING {len(generated_videos)} VIDEOS")
        print(f"{'='*80}")
        
        output_path = "media/output.mp4"
        success = concatenate_videos(generated_videos, output_path)
        
        if success:
            print(f"\nPROCESS COMPLETED!")
            print(f"Final video: {output_path}")
        else:
            print(f"\n[WARNING] Process completed with errors in concatenation")
    else:
        print(f"\n[ERROR] No videos were generated")


if __name__ == "__main__":
    main()