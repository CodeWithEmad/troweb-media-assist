import threading
import os
from openai import OpenAI
from queue import Queue


def transcribe_audio(client, file_path):
    """Transcribe an audio file using OpenAI's Whisper model."""
    with open(file_path, "rb") as audio_file:
        return client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="text",
            prompt="Keep the natural language spoken",
        )


def process_single_audio_file(client, file_path):
    """Process a single audio file: transcribe and generate corrected transcript."""
    try:
        file_name = os.path.basename(file_path)
        print("File:", file_name)
        output_file = os.path.join(
            "transcription", f"{os.path.splitext(file_name)[0]}.md"
        )

        if os.path.exists(output_file):
            print(f"Transcription for {file_name} already exists. Skipping.")
            return

        transcript = transcribe_audio(client, file_path)

        with open(output_file, "w") as f:
            f.write(transcript)

    except Exception as e:
        print(f"Error processing {file_path}: {e}")


def worker(queue, client):
    """Worker function for thread pool."""
    while True:
        file_path = queue.get()
        if file_path is None:
            break
        process_single_audio_file(client, file_path)
        queue.task_done()


def process_all_audio_files(num_threads=4):
    """Process all audio files in the 'audio' folder using multiple threads."""
    client = OpenAI()
    queue = Queue()

    # Start worker threads
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(queue, client))
        t.start()
        threads.append(t)

    # Enqueue audio files
    for file_name in os.listdir("audio"):
        if file_name.endswith((".mp3", ".m4a", ".wav")):
            queue.put(os.path.join("audio", file_name))

    # Block until all tasks are done
    queue.join()

    # Stop workers
    for _ in range(num_threads):
        queue.put(None)
    for t in threads:
        t.join()
