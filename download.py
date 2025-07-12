import os
import boto3
from botocore import UNSIGNED
from botocore.config import Config

video_extensions = (".mp4", ".mov", ".mkv", ".avi")


def prepare_application():
    os.makedirs("files", exist_ok=True)
    os.makedirs("audio", exist_ok=True)
    os.makedirs("transcription", exist_ok=True)


def download_videos_from_s3(bucket_name: str, local_dir: str, s3_path: str = None):
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    # List objects in bucket and filter for video extensions
    prefix = s3_path.rstrip("/") + "/" if s3_path else ""
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if "Contents" in response:
        for obj in response["Contents"]:
            key = obj["Key"]
            # Check if file is a video and it is not downloaded yet
            if key.lower().endswith(video_extensions) and not os.path.exists(
                os.path.join(local_dir, key.replace("/", "_"))
            ):
                local_path = os.path.join(
                    local_dir, key.replace("/", "_")
                )  # Avoid subfolder issues
                print(f"Downloading {key} to {local_path}")
                s3_client.download_file(bucket_name, key, local_path)
