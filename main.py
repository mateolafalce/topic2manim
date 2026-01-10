import os
import json
import subprocess
import re
import openai
import anthropic
from dotenv import load_dotenv
from animations import generate_script_json
from manim_generator import generate_manim_code
from concat_video import compile_video, concatenate_videos, sanitize_filename

load_dotenv()

openai_api_key = os.getenv('OPENAI_API_KEY')
claude_api_key = os.getenv('CLAUDE_API_KEY')

openai_model = os.getenv("OPENAI_MODEL")
claude_model = os.getenv("CLAUDE_MODEL")

topic = os.getenv("TOPIC")


def setup_llm_client():
    """Sets up the LLM client (OpenAI or Claude) based on available API keys"""
    
    # Priority 1: Try OpenAI
    if openai_api_key:
        print(f"[✓] Using OpenAI API with model: {openai_model}")
        client = openai.OpenAI(api_key=openai_api_key)
        return {
            'client': client,
            'provider': 'openai',
            'model': openai_model
        }
    
    # Priority 2: Fallback to Claude
    elif claude_api_key:
        print(f"[✓] Using Claude API with model: {claude_model}")
        client = anthropic.Anthropic(api_key=claude_api_key)
        return {
            'client': client,
            'provider': 'claude',
            'model': claude_model
        }
    
    # No API key found
    else:
        raise ValueError(
            "No API key found! Please configure either OPENAI_API_KEY or CLAUDE_API_KEY in your .env file"
        )


def main():
    
    content_dir = "content"
    if not os.path.exists(content_dir):
        os.makedirs(content_dir)
        print(f"Folder '{content_dir}' created successfully\n")
    else:
        print(f"Folder '{content_dir}' already exists\n")
    
    # Path to JSON file
    json_file = "video-output.json"
    
    # Configure LLM client (OpenAI or Gemini)
    try:
        llm_config = setup_llm_client()
        client = llm_config['client']
        provider = llm_config['provider']
        model = llm_config['model']
        print(f"[OK] LLM client configured\n")
    except Exception as e:
        print(f"[ERROR] Error configuring LLM: {e}")
        return
    
    # Generate new script ALWAYS (every execution)
    print(f"Generating new script for: {topic}...\n")
    video_data = generate_script_json(client, topic, json_file, provider, model)
    
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
    
    # Create topic slug (no spaces, lowercase, no special characters)
    topic_slug = sanitize_filename(topic.lower().replace(" ", "_"))
    
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
        manim_code = generate_manim_code(client, text, animation, index, previous_context, provider, model)
        
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