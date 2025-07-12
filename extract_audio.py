import os
import subprocess


def extract_audio_from_mp4_ffmpeg(video_file):
    try:
        # Construct paths
        video_path = os.path.join("files", video_file)
        audio_filename = os.path.splitext(video_file)[0] + ".mp3"
        audio_path = os.path.join("audio", audio_filename)

        # Check if audio file already exists
        if os.path.exists(audio_path):
            print(f"Audio already extracted for {video_file}. Skipping.")
            return

        # Construct FFmpeg command
        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-map",
            "a",
            "-c:a",
            "mp3",
            "-b:a",
            "128k",
            "-ac",
            "1",  # Mono
            audio_path,
        ]

        # Run FFmpeg command, capture stderr
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr
            text=True,  # Output as text instead of bytes
        )
        print(f"Extracted audio from {video_file}")

    except subprocess.CalledProcessError as e:
        # Print FFmpeg's error message from stderr
        print(
            f"Error processing {video_file}: FFmpeg returned non-zero exit status {e.returncode}"
        )
        print(f"FFmpeg error message: {e.stderr.strip()}")
    except Exception as e:
        print(f"Error processing {video_file}: {str(e)}")


def process_mp4_files_for_audio_extraction(source_dir: str):
    # Create 'audio' directory if it doesn't exist
    if not os.path.exists("audio"):
        os.makedirs("audio")

    # Get all mp4 files from the 'files' directory
    mp4_files = [f for f in os.listdir(source_dir) if f.endswith(".mp4")]

    print(f"Found {len(mp4_files)} MP4 files to process.")

    # Process files sequentially
    for video_file in mp4_files:
        extract_audio_from_mp4_ffmpeg(video_file)

    print("Audio extraction completed.")
