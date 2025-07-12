import streamlit as st
import os
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()


def check_password(username: str, password: str) -> bool:
    """Check if username/password combination is correct."""
    # In a real application, you would want to use environment variables
    # and a secure password hashing mechanism
    correct_username = os.getenv("ADMIN_USERNAME")
    correct_password = os.getenv("ADMIN_PASSWORD")

    return username == correct_username and password == correct_password


def login_page() -> Tuple[bool, str]:
    """Show the login page and handle login."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = ""

    if not st.session_state.authenticated:
        st.title("🔐 Login Required")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")

            if submit_button:
                if check_password(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    return st.session_state.authenticated, st.session_state.username


def logout():
    """Log out the user."""
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()
