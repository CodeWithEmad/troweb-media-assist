import streamlit as st
from auth import login_page, logout

# Page config
st.set_page_config(page_title="Troweb Media Assistant", page_icon="🎥", layout="wide")

# Check authentication
authenticated, username = login_page()

if authenticated:
    # Add logout button to sidebar
    with st.sidebar:
        st.write(f"👤 Logged in as: {username}")
        if st.button("🚪 Logout"):
            logout()

    # Title and welcome message
    st.title("🎥 Welcome to Troweb Media Assistant")

    st.markdown("""
    This tool helps you prepare content for Troweb by:
    - 📝 Extracting transcripts from audio/video files using OpenAI's Whisper
    - 🖼️ Generating captions for images using AI
    - 🚀 Sending content directly to Troweb

    ### Getting Started

    1. Use the sidebar navigation to switch between:
       - 📝 **Transcription**: Process audio/video files
       - 🖼️ **Captioning**: Process images

    2. Each page allows you to:
       - Upload files directly or select from S3
       - Process content using AI
       - Send results to Troweb
       - Track processed items

    3. Configure your settings:
       - Troweb connection details
       - S3 bucket information
       - Authentication options

    ### Tips

    - You can process multiple files at once
    - Previously processed items are stored in your browser
    - Each page maintains its own history of processed items
    - Settings are shared across all pages
    """)

    # Add footer
    st.markdown("---")
    st.markdown("Made with ❤️ for Troweb")
