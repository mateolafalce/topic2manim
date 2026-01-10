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
            # Sanitize the topic_slug to match how Manim creates directories
            sanitized_slug = sanitize_filename(topic_slug)
            # Video will be in media/videos/{filename_without_extension}/480p15/{class_name}.mp4
            video_path = f"media/videos/{sanitized_slug}-{index}/480p15/{class_name}.mp4"
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
