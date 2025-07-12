import boto3
import os
from botocore import UNSIGNED
from botocore.config import Config
from urllib.parse import quote

video_extensions = (".mp4", ".mov", ".mkv", ".avi")


def create_file_info_map_from_s3(bucket_name: str, s3_path: str = None):
    """
    Creates a file info map by reading from S3 and matching with local transcripts.

    Args:
        bucket_name (str): Name of the S3 bucket

    Returns:
        dict: A dictionary with video information structure
    """
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    file_info_map = {}

    prefix = s3_path.rstrip("/") + "/" if s3_path else ""

    # List objects in bucket
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if "Contents" in response:
        for obj in response["Contents"]:
            key = obj["Key"]
            # Check if file is a video
            if key.lower().endswith(video_extensions):
                # Get base name without extension
                base_name = os.path.splitext(key)[0]
                key_name = key.replace("/", "_")
                # Check for corresponding transcription
                transcript_file = os.path.join(
                    "transcription", f"{os.path.splitext(key_name)[0]}.md"
                )

                # Read transcription if exists
                transcription = ""
                if os.path.exists(transcript_file):
                    with open(transcript_file, "r", encoding="utf-8") as tf:
                        transcription = tf.read()

                # Create the file info entry
                file_info_map[key] = {
                    "url": f"https://{bucket_name}.s3.amazonaws.com/{quote(key)}",
                    "title": base_name,
                    "transcription": transcription,
                    "transcription_file": transcript_file,
                }

    return file_info_map
