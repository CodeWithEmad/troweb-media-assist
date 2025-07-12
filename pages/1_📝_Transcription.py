import os
import streamlit as st
import tempfile
from openai import OpenAI
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from extract_transcript import transcribe_audio
import json
from send_to_troweb import insert_all
import asyncio
import aiohttp
from auth import login_page, logout

# Initialize OpenAI client
client = OpenAI()

# Constants for concurrency
MAX_CONCURRENT_DOWNLOADS = 5
MAX_CONCURRENT_TRANSCRIPTIONS = 3  # OpenAI API has rate limits

# Page config
st.set_page_config(
    page_title="Transcription - Troweb Assistant", page_icon="📝", layout="wide"
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
        if "transcript_ids" in st.session_state and st.session_state.transcript_ids:
            st.subheader("📝 Stored Transcripts")
            st.info("Previously processed items")
            for file_name, item_id in st.session_state.transcript_ids.items():
                st.code(f"{file_name}: {item_id}")
            if st.button("Clear Stored Transcripts"):
                st.session_state.transcript_ids = {}
                st.rerun()

    # Initialize session states
    if "transcript_ids" not in st.session_state:
        st.session_state.transcript_ids = {}
    if "transcripts" not in st.session_state:
        st.session_state.transcripts = {}
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    if "processed_items" not in st.session_state:
        st.session_state.processed_items = []
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = None
    if "selected_s3_files" not in st.session_state:
        st.session_state.selected_s3_files = None
    if "file_statuses" not in st.session_state:
        st.session_state.file_statuses = {}

    st.title("📝 Audio/Video Transcription")
    st.info(
        "Upload audio/video files or select from S3 to extract their transcripts using OpenAI's Whisper model."
    )

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
                            st.session_state.transcript_ids[file_name] = result[
                                "data"
                            ].get("_id")

                st.success("Successfully sent to Troweb!")

                # Save processed files for reference
                with open("transcript_info.json", "w") as f:
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

    async def download_s3_file(session, s3_key, bucket_name):
        """Download a single file from S3 asynchronously"""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(s3_key)[1]
        )
        try:
            # Generate presigned URL for the S3 object
            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": s3_key},
                ExpiresIn=3600,
            )

            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    temp_file.write(content)
                    temp_file.close()
                    return temp_file.name
                else:
                    raise Exception(
                        f"Failed to download {s3_key}: HTTP {response.status}"
                    )
        except Exception as e:
            temp_file.close()
            os.unlink(temp_file.name)
            raise e

    async def process_file_async(s3_key, bucket_name, progress_bar, progress_text):
        """Process a single file asynchronously"""
        file_key = os.path.splitext(os.path.basename(s3_key))[0]

        if file_key in st.session_state.processed_files:
            return True

        # Initialize status for this file
        st.session_state.file_statuses[file_key] = {
            "status": "pending",
            "download": "pending",
            "transcription": "pending",
            "error": None,
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Update download status
                st.session_state.file_statuses[file_key]["status"] = "downloading"
                st.session_state.file_statuses[file_key]["download"] = "in_progress"
                progress_text.text(f"Downloading {os.path.basename(s3_key)}...")

                try:
                    temp_path = await download_s3_file(session, s3_key, bucket_name)
                    st.session_state.file_statuses[file_key]["download"] = "completed"
                except Exception as e:
                    st.session_state.file_statuses[file_key]["download"] = "failed"
                    st.session_state.file_statuses[file_key]["error"] = str(e)
                    raise e

                try:
                    # Update transcription status
                    st.session_state.file_statuses[file_key]["status"] = "transcribing"
                    st.session_state.file_statuses[file_key]["transcription"] = (
                        "in_progress"
                    )
                    progress_text.text(f"Transcribing {os.path.basename(s3_key)}...")

                    transcript = transcribe_audio(client, temp_path)

                    # Store results
                    st.session_state.transcripts[file_key] = transcript
                    st.session_state.processed_files.add(file_key)
                    st.session_state.processed_items.append(
                        {
                            "title": file_key,
                            "transcription": transcript,
                            "url": f"https://{bucket_name}.s3.amazonaws.com/{s3_key}",
                        }
                    )

                    st.session_state.file_statuses[file_key]["status"] = "completed"
                    st.session_state.file_statuses[file_key]["transcription"] = (
                        "completed"
                    )

                    progress_bar.progress(
                        (len(st.session_state.processed_files))
                        / len(st.session_state.selected_s3_files)
                    )
                    return True

                except Exception as e:
                    st.session_state.file_statuses[file_key]["transcription"] = "failed"
                    st.session_state.file_statuses[file_key]["error"] = str(e)
                    raise e
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

        except Exception as e:
            st.session_state.file_statuses[file_key]["status"] = "failed"
            st.error(f"Error processing {s3_key}: {str(e)}")
            return False

    async def process_files_async(s3_keys, bucket_name):
        """Process multiple files concurrently"""
        # Clear previous statuses
        st.session_state.file_statuses = {}

        progress_bar = st.progress(0)
        progress_text = st.empty()

        # Create status display columns
        status_container = st.container()

        # Create semaphores for rate limiting
        download_sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        transcribe_sem = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

        async def process_with_semaphores(s3_key):
            async with download_sem:
                async with transcribe_sem:
                    result = await process_file_async(
                        s3_key, bucket_name, progress_bar, progress_text
                    )
                    # Update status display after each file
                    with status_container:
                        display_status_table()
                    return result

        # Process files concurrently
        tasks = [process_with_semaphores(s3_key) for s3_key in s3_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Clear progress indicators but keep status table
        progress_bar.empty()
        progress_text.empty()

        # Final status update
        with status_container:
            display_status_table()

        return all(isinstance(r, bool) and r for r in results)

    def display_status_table():
        """Display the status table for all files"""
        if not st.session_state.file_statuses:
            return

        # Create a dataframe for better display
        rows = []
        for file_key, status in st.session_state.file_statuses.items():
            # Define status emojis
            status_emojis = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
            }

            # Create row with emojis
            row = {
                "File": file_key,
                "Status": f"{status_emojis[status['status']]} {status['status'].title()}",
                "Download": f"{status_emojis[status['download']]} {status['download'].title()}",
                "Transcription": f"{status_emojis[status['transcription']]} {status['transcription'].title()}",
            }

            # Add error message if present
            if status["error"]:
                row["Error"] = status["error"]

            rows.append(row)

        # Display as a table
        st.table(rows)

    def process_uploaded_file(audio_file):
        """Process a single uploaded file"""
        file_key = os.path.splitext(audio_file.name)[0]
        if file_key not in st.session_state.processed_files:
            with st.spinner(f"Transcribing {audio_file.name}..."):
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(audio_file.name)[1]
                ) as tmp_file:
                    tmp_file.write(audio_file.getvalue())
                    temp_path = tmp_file.name

                try:
                    transcript = transcribe_audio(client, temp_path)
                    st.session_state.transcripts[file_key] = transcript
                    st.session_state.processed_files.add(file_key)
                    st.session_state.processed_items.append(
                        {
                            "title": file_key,
                            "transcription": transcript,
                            "url": None,  # Local file
                        }
                    )
                    return True
                except Exception as e:
                    st.error(f"Error processing {audio_file.name}: {str(e)}")
                    return False
                finally:
                    os.unlink(temp_path)
        return True

    def on_upload_submit():
        """Handle file upload submission"""
        if st.session_state.uploaded_files:
            all_success = True
            for audio_file in st.session_state.uploaded_files:
                if not process_uploaded_file(audio_file):
                    all_success = False
            if all_success:
                st.success("All files processed successfully!")

    def on_s3_submit():
        """Handle S3 file selection submission"""
        if st.session_state.selected_s3_files:
            # Run async processing in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                all_success = loop.run_until_complete(
                    process_files_async(st.session_state.selected_s3_files, bucket_name)
                )
                if all_success:
                    st.success("All files processed successfully!")
                    # Auto-send to Troweb if enabled
                    if st.session_state.get("auto_send_troweb", False):
                        if send_to_troweb(
                            st.session_state.processed_items, collection_id
                        ):
                            st.success("Successfully sent to Troweb!")
                            # Clear processed items after successful send
                            st.session_state.processed_items = []
                            st.session_state.processed_files = set()
                            st.session_state.transcripts = {}
                            st.session_state.file_statuses = {}  # Clear statuses too
                            st.rerun()
            finally:
                loop.close()

    # Source selection
    source = st.radio("Select Source", ["Upload Files", "Load from S3"])

    if source == "Upload Files":
        with st.form("upload_form"):
            st.session_state.uploaded_files = st.file_uploader(
                "Upload audio/video files",
                type=["mp3", "m4a", "wav", "mp4", "avi", "mov"],
                accept_multiple_files=True,
            )
            submit_button = st.form_submit_button(
                "Process Files", on_click=on_upload_submit
            )

    else:  # Load from S3
        s3_files = list_s3_files(
            s3_client,
            bucket_name,
            s3_folder,
            (".mp3", ".m4a", ".wav", ".mp4", ".avi", ".mov"),
        )

        if not s3_files:
            st.warning("No audio/video files found in the specified S3 location.")
        else:
            with st.form("s3_form"):
                # Add select all checkbox
                select_all = st.checkbox("Select All Files", value=True)

                # Auto-send to Troweb option
                st.session_state.auto_send_troweb = st.checkbox(
                    "Automatically send to Troweb after processing", value=True
                )

                # If select all is True, pre-select all files
                default_selection = s3_files if select_all else []
                st.session_state.selected_s3_files = st.multiselect(
                    "Select files to transcribe",
                    s3_files,
                    default=default_selection,
                    format_func=lambda x: os.path.basename(x),
                )

                total_files = len(st.session_state.selected_s3_files)
                if total_files > 0:
                    st.info(f"Selected {total_files} files for processing")

                submit_button = st.form_submit_button(
                    "Process Files", on_click=on_s3_submit
                )

    # Display processed transcripts
    for file_key, transcript in st.session_state.transcripts.items():
        with st.expander(f"Transcript for {file_key}"):
            st.text_area(
                "",
                value=transcript,
                height=200,
                key=f"transcript_{file_key}",
            )
            st.download_button(
                "Download Transcript",
                transcript,
                file_name=f"{file_key}_transcript.txt",
                mime="text/plain",
            )

    # Send to Troweb button
    if st.session_state.processed_items:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Send Transcribed Files to Troweb", key="send_transcripts"):
                if send_to_troweb(st.session_state.processed_items, collection_id):
                    # Clear processed items after successful send
                    st.session_state.processed_items = []
                    st.session_state.processed_files = set()
                    st.session_state.transcripts = {}
                    st.rerun()  # Clear the page after successful send
