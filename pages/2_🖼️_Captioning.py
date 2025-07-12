import os
import streamlit as st
import tempfile
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from caption_images import caption_uploaded_image
import json
from send_to_troweb import insert_all
from auth import login_page, logout

# Page config
st.set_page_config(
    page_title="Image Captioning - Troweb Assistant", page_icon="🖼️", layout="wide"
)

# Check authentication
authenticated, username = login_page()

if authenticated:
    # Add logout button to sidebar
    with st.sidebar:
        st.write(f"👤 Logged in as: {username}")
        if st.button("🚪 Logout"):
            logout()

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Troweb Settings
        st.subheader("Troweb Settings")
        troweb_url = st.text_input(
            "Troweb Base URL",
            value="https://lernito-ai-tutor.troweb.app",
            help="The base URL of your Troweb instance",
        )
        collection_id = st.text_input(
            "Collection ID",
            value="6872250292388b780cdaa45e",
            help="The ID of the collection to add content to",
        )

        # S3 Configuration
        st.subheader("Amazon S3 Settings")
        bucket_name = st.text_input("S3 Bucket Name", value="content-vidoes")
        s3_folder = st.text_input(
            "S3 Folder Path (optional)", help="Example: 'folder/subfolder'"
        )

        # Authentication mode
        auth_mode = st.radio(
            "S3 Authentication Mode",
            ["Anonymous (Public Bucket)", "AWS Credentials"],
            help="Choose how to authenticate with S3",
        )

        if auth_mode == "AWS Credentials":
            aws_access_key = st.text_input("AWS Access Key ID", type="password")
            aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
            aws_region = st.text_input("AWS Region", value="us-east-1")

        # Initialize S3 client
        if auth_mode == "Anonymous (Public Bucket)":
            s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
        else:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
            )

        # Show stored IDs
        if "caption_ids" in st.session_state and st.session_state.caption_ids:
            st.subheader("🖼️ Stored Captions")
            st.info("Previously processed items")
            for file_name, item_id in st.session_state.caption_ids.items():
                st.code(f"{file_name}: {item_id}")
            if st.button("Clear Stored Captions"):
                st.session_state.caption_ids = {}
                st.rerun()

    # Initialize session state for caption IDs if not exists
    if "caption_ids" not in st.session_state:
        st.session_state.caption_ids = {}

    st.title("🖼️ Image Captioning")
    st.info("Upload images or select from S3 to generate AI-powered captions.")

    def send_to_troweb(items, collection_id):
        """Send processed items to Troweb and store their IDs"""
        try:
            with st.spinner("Creating Troweb job..."):
                result = insert_all(items, collection_id)

                # Store IDs in session state
                if result and "data" in result:
                    for item in items:
                        file_name = item.get("title", "")
                        if file_name:
                            st.session_state.caption_ids[file_name] = result[
                                "data"
                            ].get("_id")

                st.success("Successfully sent to Troweb!")

                # Save processed files for reference
                with open("caption_info.json", "w") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)

                return True
        except Exception as e:
            st.error(f"Error sending to Troweb: {str(e)}")
            return False

    def list_s3_files(client, bucket, prefix="", extensions=()):
        """List files in S3 bucket with given extensions"""
        files = []
        prefix = prefix.rstrip("/") + "/" if prefix else ""

        try:
            response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if "Contents" in response:
                for obj in response["Contents"]:
                    if obj["Key"].lower().endswith(extensions):
                        files.append(obj["Key"])
        except Exception as e:
            st.error(f"Error listing S3 files: {str(e)}")

        return files

    # Source selection
    source = st.radio(
        "Select Source", ["Upload Files", "Load from S3"], key="image_source"
    )

    processed_items = []

    if source == "Upload Files":
        image_files = st.file_uploader(
            "Upload images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )

        if image_files:
            for image_file in image_files:
                col1, col2 = st.columns([1, 1])

                with col1:
                    st.image(
                        image_file, caption=image_file.name, use_container_width=True
                    )

                with col2:
                    with st.spinner("Generating caption..."):
                        try:
                            caption = caption_uploaded_image(image_file.getvalue())

                            # Add to processed items
                            processed_items.append(
                                {
                                    "title": os.path.splitext(image_file.name)[0],
                                    "caption": caption,
                                    "url": None,  # Local file
                                }
                            )

                            st.success("Caption generated!")
                            st.text_area(
                                "Generated Caption",
                                value=caption,
                                height=100,
                                key=f"caption_{image_file.name}",
                            )
                        except Exception as e:
                            st.error(f"Error processing {image_file.name}: {str(e)}")

                st.divider()

    else:  # Load from S3
        s3_files = list_s3_files(
            s3_client,
            bucket_name,
            s3_folder,
            (".jpg", ".jpeg", ".png", ".webp"),
        )

        if not s3_files:
            st.warning("No image files found in the specified S3 location.")
        else:
            selected_files = st.multiselect(
                "Select images to caption",
                s3_files,
                format_func=lambda x: os.path.basename(x),
            )

            if selected_files:
                for s3_key in selected_files:
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        # Generate presigned URL for image display
                        try:
                            if auth_mode == "AWS Credentials":
                                url = s3_client.generate_presigned_url(
                                    "get_object",
                                    Params={"Bucket": bucket_name, "Key": s3_key},
                                    ExpiresIn=3600,
                                )
                            else:
                                url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
                                st.image(
                                    url,
                                    caption=os.path.basename(s3_key),
                                    use_container_width=True,
                                )
                        except Exception as e:
                            st.error(f"Error displaying image {s3_key}: {str(e)}")

                    with col2:
                        with st.spinner("Generating caption..."):
                            try:
                                # For public buckets, use the direct URL
                                if auth_mode == "Anonymous (Public Bucket)":
                                    url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
                                    caption = caption_uploaded_image(url)
                                else:
                                    # For private buckets, download and process
                                    with tempfile.NamedTemporaryFile(
                                        delete=False, suffix=os.path.splitext(s3_key)[1]
                                    ) as tmp_file:
                                        s3_client.download_fileobj(
                                            bucket_name, s3_key, tmp_file
                                        )
                                        caption = caption_uploaded_image(tmp_file.name)
                                        os.unlink(tmp_file.name)

                                # Add to processed items
                                processed_items.append(
                                    {
                                        "title": os.path.splitext(
                                            os.path.basename(s3_key)
                                        )[0],
                                        "caption": caption,
                                        "url": url,
                                    }
                                )

                                st.success("Caption generated!")
                                st.text_area(
                                    "Generated Caption",
                                    value=caption,
                                    height=100,
                                    key=f"caption_{s3_key}",
                                )
                            except Exception as e:
                                st.error(f"Error processing {s3_key}: {str(e)}")

                    st.divider()

    # Send to Troweb button
    if processed_items:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Send Captioned Images to Troweb", key="send_captions"):
                if send_to_troweb(processed_items, collection_id):
                    st.rerun()  # Clear the page after successful send
