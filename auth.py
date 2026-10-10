"""
auth.py - Authentication Management for Waterford Track & Field Dashboard.
Uses streamlit-authenticator with secure bcrypt hashing for Coach/Admin access,
while maintaining frictionless open access for public / athletes.
"""

import os
import streamlit as st
import streamlit_authenticator as stauth

# Coach Account Configuration
COACH_USERNAME = os.getenv("COACH_USERNAME", "coach")
COACH_PASSWORD = os.getenv("COACH_PASSWORD", "waterford2026")
COACH_NAME = os.getenv("COACH_NAME", "Coach Waterford")
COACH_EMAIL = os.getenv("COACH_EMAIL", "coach@waterfordtrack.org")

COOKIE_NAME = "waterford_track_session"
COOKIE_KEY = os.getenv("COOKIE_SECRET_KEY", "waterford_track_and_field_secret_key_2026")
COOKIE_EXPIRY_DAYS = 30.0


@st.cache_resource
def get_authenticator_config():
    """Generates credentials dictionary with hashed password."""
    # Hash default password
    hashed_password = stauth.Hasher.hash(COACH_PASSWORD)
    credentials = {
        "usernames": {
            COACH_USERNAME: {
                "name": COACH_NAME,
                "password": hashed_password,
                "email": COACH_EMAIL,
            }
        }
    }
    return credentials


def get_authenticator():
    """Returns the Streamlit Authenticate instance."""
    credentials = get_authenticator_config()
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name=COOKIE_NAME,
        cookie_key=COOKIE_KEY,
        cookie_expiry_days=COOKIE_EXPIRY_DAYS,
    )
    return authenticator


def is_coach_authenticated() -> bool:
    """Returns True if the current user is authenticated as Coach/Admin."""
    return st.session_state.get("authentication_status") is True


def render_auth_sidebar():
    """
    Renders login/logout status in the sidebar.
    - If logged in: displays Coach badge, name, and Logout button.
    - If logged out: displays Coach Login form in an expander with testing hints.
    """
    authenticator = get_authenticator()
    
    st.sidebar.divider()
    
    if is_coach_authenticated():
        st.sidebar.success(f"🏅 Logged in as **{st.session_state.get('name', 'Coach')}**")
        st.sidebar.caption("Role: **Head Coach / Admin** (Full CRUD Access)")
        authenticator.logout(location="sidebar", button_name="Log Out", key="sidebar_logout")
    else:
        st.sidebar.info("👁️ **Public Mode** (Read-Only)")
        with st.sidebar.expander("🔐 Coach Login", expanded=False):
            st.caption("Coaches: Log in to add, edit, or delete meets and results.")
            try:
                authenticator.login(location="main", key="coach_login_form")
            except Exception as e:
                # Fallback form in case of any widget conflict
                with st.form("fallback_login_form"):
                    u = st.text_input("Username", value="")
                    p = st.text_input("Password", type="password", value="")
                    sub = st.form_submit_button("Log In")
                    if sub:
                        if u == COACH_USERNAME and (p == COACH_PASSWORD or stauth.Hasher.check_pw(p, get_authenticator_config()["usernames"][COACH_USERNAME]["password"])):
                            st.session_state["authentication_status"] = True
                            st.session_state["name"] = COACH_NAME
                            st.session_state["username"] = COACH_USERNAME
                            st.rerun()
                        else:
                            st.error("Incorrect username or password.")
            
            if st.session_state.get("authentication_status") is False:
                st.error("Invalid username or password.")
            elif st.session_state.get("authentication_status") is None:
                st.caption(f"Default Coach Login: `{COACH_USERNAME}` / `{COACH_PASSWORD}`")
