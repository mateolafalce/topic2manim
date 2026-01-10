import os
import subprocess
from pathlib import Path
from openai import OpenAI


def get_audio_duration(audio_path):
    """
    Gets the duration of an audio file using ffprobe
    
    Args:
        audio_path: Path to the audio file
    
    Returns:
        Duration in seconds (float) or None if error
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            return duration
        else:
            print(f"  [WARNING] Could not get duration for {audio_path}")
            return None
    except Exception as e:
        print(f"  [WARNING] Error getting audio duration: {e}")
        return None


def generate_audio_fragment(client, text, index, output_dir="media/audio_fragments", tts_model="tts-1", voice="alloy"):
    """
    Generates an audio fragment from text using OpenAI TTS
    
    Args:
        client: OpenAI client instance
        text: Text to convert to speech
        index: Fragment index number
        output_dir: Directory to save audio fragments
        tts_model: TTS model to use (tts-1 or tts-1-hd)
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
    
    Returns:
        Tuple of (audio_path, duration) or (None, None) if error
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate audio file path
        audio_path = os.path.join(output_dir, f"fragment_{index}.mp3")
        
        print(f"  Generating audio fragment {index}...")
        print(f"    Text preview: {text[:80]}...")
        
        # Call OpenAI TTS API
        response = client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=text
        )
        
        # Save audio to file
        response.stream_to_file(audio_path)
        
        # Get audio duration
        duration = get_audio_duration(audio_path)
        
        if duration:
            print(f"  [OK] Audio fragment saved: {audio_path} (duration: {duration:.2f}s)")
        else:
            print(f"  [OK] Audio fragment saved: {audio_path} (duration: unknown)")
        
        return audio_path, duration
        
    except Exception as e:
        print(f"  [ERROR] Error generating audio fragment {index}: {e}")
        return None, None


def concatenate_audio_fragments(audio_paths, output_path="media/audio.mp3"):
    """
    Concatenates multiple audio fragments into a single MP3 file using ffmpeg
    
    Args:
        audio_paths: List of paths to audio fragments
        output_path: Path for the final concatenated audio file
    
    Returns:
        True if successful, False otherwise
    """
    if not audio_paths:
        print("[ERROR] No audio fragments to concatenate")
        return False
    
    # Create media folder if it doesn't exist
    os.makedirs("media", exist_ok=True)
    
    # Create list file for ffmpeg
    list_file = "media/audio_list.txt"
    with open(list_file, 'w') as f:
        for audio_path in audio_paths:
            if os.path.exists(audio_path):
                # Use absolute path to avoid issues
                abs_path = os.path.abspath(audio_path)
                f.write(f"file '{abs_path}'\n")
    
    try:
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
            "-y"  # Overwrite if exists
        ]
        
        print(f"\n  Concatenating {len(audio_paths)} audio fragments...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  [OK] Final audio created: {output_path}")
            # Clean up temporary file
            os.remove(list_file)
            return True
        else:
            print(f"  [ERROR] Error concatenating audio:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False


def generate_complete_audio(client, video_data, tts_model="tts-1", voice="alloy"):
    """
    Generates complete audio for all scenes
    
    Returns:
        Tuple of (audio_path, durations_dict) where durations_dict maps scene index to duration
    """
    print(f"\n{'='*80}")
    print(f"GENERATING AUDIO WITH TTS")
    print(f"{'='*80}")
    print(f"Model: {tts_model}")
    print(f"Voice: {voice}")
    print(f"Scenes: {len(video_data)}\n")
    
    audio_fragments = []
    audio_durations = {}  # Map scene index to duration
    
    # Generate audio for each scene
    for index, scene_data in enumerate(video_data, 1):
        text = scene_data.get('text', '')
        
        if not text:
            print(f"  [WARNING] Scene {index} has no text, skipping...")
            continue
        
        audio_path, duration = generate_audio_fragment(
            client=client,
            text=text,
            index=index,
            tts_model=tts_model,
            voice=voice
        )
        
        if audio_path and os.path.exists(audio_path):
            audio_fragments.append(audio_path)
            if duration:
                audio_durations[index] = duration
        else:
            print(f"  [WARNING] Could not generate audio for scene {index}")
    
    # Concatenate all audio fragments
    if audio_fragments:
        print(f"\n{'='*80}")
        print(f"CONCATENATING {len(audio_fragments)} AUDIO FRAGMENTS")
        print(f"{'='*80}")
        
        output_path = "media/audio.mp3"
        success = concatenate_audio_fragments(audio_fragments, output_path)
        
        if success:
            print(f"\n[OK] Complete audio generated: {output_path}\n")
            return output_path, audio_durations
        else:
            print(f"\n[ERROR] Failed to concatenate audio fragments\n")
            return None, {}
    else:
        print(f"\n[ERROR] No audio fragments were generated\n")
        return None, {}

