import os
import json
import uuid
import threading
from datetime import datetime
from dotenv import load_dotenv
import openai
import anthropic
from animations import generate_script_json
from manim_generator import generate_manim_code
from concat_video import compile_video, concatenate_videos, sanitize_filename, merge_video_and_audio
from tts_generator import generate_complete_audio

load_dotenv()

# Global job storage (in production, use Redis or a database)
jobs = {}

def setup_llm_client(provider_preference='auto'):
    """Sets up the LLM client based on preference and available API keys"""
    
    openai_api_key = os.getenv('OPENAI_API_KEY')
    claude_api_key = os.getenv('CLAUDE_API_KEY')
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4")
    claude_model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    
    # If specific provider requested
    if provider_preference == 'claude' and claude_api_key:
        client = anthropic.Anthropic(api_key=claude_api_key)
        return {
            'client': client,
            'provider': 'claude',
            'model': claude_model
        }
    
    if provider_preference == 'openai' and openai_api_key:
        client = openai.OpenAI(api_key=openai_api_key)
        return {
            'client': client,
            'provider': 'openai',
            'model': openai_model
        }
    
    # Auto mode: Priority 1 Claude, Priority 2 OpenAI
    if claude_api_key:
        client = anthropic.Anthropic(api_key=claude_api_key)
        return {
            'client': client,
            'provider': 'claude',
            'model': claude_model
        }
    
    if openai_api_key:
        client = openai.OpenAI(api_key=openai_api_key)
        return {
            'client': client,
            'provider': 'openai',
            'model': openai_model
        }
    
    raise ValueError(
        "No API key found! Please configure either CLAUDE_API_KEY or OPENAI_API_KEY in your .env file"
    )


def update_job_status(job_id, status=None, progress=None, current_step=None, message=None, error=None, video_url=None):
    """Update job status in storage"""
    if job_id not in jobs:
        jobs[job_id] = {}
    
    if status:
        jobs[job_id]['status'] = status
    if progress is not None:
        jobs[job_id]['progress'] = progress
    if current_step:
        jobs[job_id]['current_step'] = current_step
    if message:
        jobs[job_id]['message'] = message
    if error:
        jobs[job_id]['error'] = error
    if video_url:
        jobs[job_id]['video_url'] = video_url
    
    jobs[job_id]['updated_at'] = datetime.now().isoformat()


def generate_video_workflow(job_id, topic, enable_tts, llm_provider):
    """Background worker for video generation"""
    
    try:
        # Create necessary directories
        content_dir = "content"
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs('media', exist_ok=True)
        
        # Step 1: Setup LLM
        update_job_status(job_id, status='running', progress=5, current_step='script', 
                         message='Setting up LLM client...')
        
        llm_config = setup_llm_client(llm_provider)
        client = llm_config['client']
        provider = llm_config['provider']
        model = llm_config['model']
        
        # Step 2: Generate Script
        update_job_status(job_id, progress=10, current_step='script', 
                         message=f'Generating script with {provider}...')
        
        json_file = f"video-output-{job_id}.json"
        video_data = generate_script_json(client, topic, json_file, provider, model)
        
        if not video_data:
            raise Exception("Could not generate script")
        
        update_job_status(job_id, progress=25, current_step='script', 
                         message=f'Script generated with {len(video_data)} scenes')
        
        # Step 3: Generate TTS Audio (if enabled)
        audio_path = None
        audio_durations = {}
        
        if enable_tts:
            update_job_status(job_id, progress=30, current_step='tts', 
                             message='Generating audio with TTS...')
            
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                tts_client = openai.OpenAI(api_key=openai_api_key)
                tts_model = os.getenv("TTS_MODEL", "tts-1")
                voice = os.getenv("VOICE", "alloy")
                
                audio_path, audio_durations = generate_complete_audio(
                    client=tts_client,
                    video_data=video_data,
                    tts_model=tts_model,
                    voice=voice
                )
                
                update_job_status(job_id, progress=40, current_step='tts', 
                                 message='Audio generated successfully')
            else:
                update_job_status(job_id, progress=40, current_step='tts', 
                                 message='Skipping TTS (no OpenAI key)')
        else:
            update_job_status(job_id, progress=40, current_step='code', 
                             message='Skipping TTS (disabled)')
        
        # Step 4: Generate Manim Code and Compile Videos
        update_job_status(job_id, progress=45, current_step='code', 
                         message='Generating Manim code...')
        
        topic_slug = sanitize_filename(topic.lower().replace(" ", "_"))
        generated_videos = []
        previous_context = None
        
        for index, scene_data in enumerate(video_data, 1):
            scene_progress = 45 + (index / len(video_data)) * 30  # 45% to 75%
            
            update_job_status(job_id, progress=scene_progress, current_step='code', 
                             message=f'Processing scene {index}/{len(video_data)}...')
            
            text = scene_data.get('text', '')
            animation = scene_data.get('animation', '')
            audio_duration = audio_durations.get(index, None)
            
            manim_code = generate_manim_code(
                client, text, animation, index, 
                previous_context, provider, model, 
                audio_duration=audio_duration
            )
            
            if not manim_code:
                continue
            
            code_content = manim_code.get('content', '')
            class_name = manim_code.get('class_name', f'Scene{index}')
            
            filename = f"{topic_slug}-{job_id}-{index}.py"
            filepath = os.path.join(content_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            # Compile video
            video_path = compile_video(filepath, class_name, topic_slug, index)
            
            if video_path and os.path.exists(video_path):
                generated_videos.append(video_path)
                previous_context = {
                    'text': text,
                    'animation': animation,
                    'code': code_content
                }
        
        if not generated_videos:
            raise Exception("No videos were generated")
        
        # Step 5: Concatenate Videos
        update_job_status(job_id, progress=80, current_step='video', 
                         message='Concatenating video scenes...')
        
        silent_video_path = f"media/output_silent_{job_id}.mp4"
        success = concatenate_videos(generated_videos, silent_video_path)
        
        if not success:
            raise Exception("Failed to concatenate videos")
        
        # Step 6: Merge Audio (if available)
        final_output_path = f"media/output_{job_id}.mp4"
        
        if audio_path and os.path.exists(audio_path):
            update_job_status(job_id, progress=90, current_step='video', 
                             message='Merging audio with video...')
            
            merge_success = merge_video_and_audio(
                video_path=silent_video_path,
                audio_path=audio_path,
                output_path=final_output_path
            )
            
            if not merge_success:
                # If merge fails, use silent video
                final_output_path = silent_video_path
        else:
            # No audio, use silent video
            os.rename(silent_video_path, final_output_path)
        
        # Complete!
        video_url = f"/media/{os.path.basename(final_output_path)}"
        update_job_status(job_id, status='completed', progress=100, current_step='video', 
                         message='Video generation completed!', video_url=video_url)
        
        # Cleanup
        if os.path.exists(json_file):
            os.remove(json_file)
        
    except Exception as e:
        update_job_status(job_id, status='failed', error=str(e), 
                         message=f'Error: {str(e)}')


def start_video_generation(topic, enable_tts=True, llm_provider='auto'):
    """Start video generation in background thread"""
    
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        'job_id': job_id,
        'topic': topic,
        'status': 'queued',
        'progress': 0,
        'current_step': 'script',
        'message': 'Job queued',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    # Start background thread
    thread = threading.Thread(
        target=generate_video_workflow,
        args=(job_id, topic, enable_tts, llm_provider),
        daemon=True
    )
    thread.start()
    
    return job_id


def get_job_status(job_id):
    """Get current status of a job"""
    return jobs.get(job_id)
