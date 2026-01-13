import subprocess
import os
import re

def sanitize_filename(filename):
    """Remove or replace problematic characters from filenames"""
    # Remove apostrophes, question marks, and other special characters
    # Replace with underscores or remove them
    sanitized = re.sub(r"['\"\?!:;,\(\)\[\]\{\}]", "", filename)
    # Replace multiple underscores with single underscore
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized

def compile_video(file_path, class_name, topic_slug, index):
    """Compiles the video using Manim"""
    try:
        cmd = ["manim", "-ql", file_path, class_name]
        print(f"\nCompiling: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            print(f"[OK] Video compiled successfully")
            # Manim creates directory based on the Python filename (without extension)
            # Extract filename without extension from file_path
            filename_without_ext = os.path.splitext(os.path.basename(file_path))[0]
            # Video will be in media/videos/{filename_without_extension}/480p15/{class_name}.mp4
            video_path = f"media/videos/{filename_without_ext}/480p15/{class_name}.mp4"
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


def merge_video_and_audio(video_path, audio_path, output_path):
    """
    Merges video and audio files into a single MP4 file using ffmpeg
    
    Args:
        video_path: Path to the video file (without audio)
        audio_path: Path to the audio file (MP3)
        output_path: Path for the final merged video
    
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        return False
    
    if not os.path.exists(audio_path):
        print(f"[ERROR] Audio file not found: {audio_path}")
        return False
    
    try:
        cmd = [
            "ffmpeg",
            "-i", video_path,  # Input video
            "-i", audio_path,  # Input audio
            "-c:v", "copy",    # Copy video codec (no re-encoding)
            "-c:a", "aac",     # Encode audio to AAC
            "-map", "0:v:0",   # Map video from first input
            "-map", "1:a:0",   # Map audio from second input
            output_path,
            "-y"               # Overwrite if exists
        ]
        
        print(f"\n{'='*80}")
        print(f"MERGING VIDEO AND AUDIO")
        print(f"{'='*80}")
        print(f"Video: {video_path}")
        print(f"Audio: {audio_path}")
        print(f"Output: {output_path}\n")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"[OK] Final video with audio created: {output_path}\n")
            return True
        else:
            print(f"[ERROR] Error merging video and audio:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False
