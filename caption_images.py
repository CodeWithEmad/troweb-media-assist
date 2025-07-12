import io
from openai import OpenAI
import boto3
from dotenv import load_dotenv

load_dotenv()


def bytes_to_named_file(image_bytes, filename="image.png"):
    # Create a file-like object
    file_obj = io.BytesIO(image_bytes)
    # Add name attribute that OpenAI's client expects
    file_obj.name = filename
    return file_obj


def caption_uploaded_image(image: bytes):
    client = OpenAI()

    image_file = client.files.create(file=bytes_to_named_file(image), purpose="vision")

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are an expert at describing images accurately and concisely. Provide clear, detailed captions that capture the main elements and context of the image.",
                    },
                    {
                        "type": "input_image",
                        "file_id": image_file.id,
                    },
                ],
            }
        ],
    )
    return response.output_text


def caption_images_on_s3_bucket(bucket_name, folder_name):
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)
    for obj in response.get("Contents", []):
        if obj["Key"].endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")
        ):
            # Download the image from S3
            image_obj = s3.get_object(Bucket=bucket_name, Key=obj["Key"])
            image_data = image_obj["Body"].read()

            # Get the caption
            caption = caption_uploaded_image(image_data)
            print(f"Caption for {obj['Key']}: {caption}")

            # Store the caption in S3
            caption_key = obj["Key"].rsplit(".", 1)[0] + "_caption.txt"
            s3.put_object(
                Bucket=bucket_name, Key=caption_key, Body=caption.encode("utf-8")
            )
