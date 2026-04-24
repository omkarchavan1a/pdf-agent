import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT_DIR = Path(__file__).parent
BACKEND_PORT = int(os.getenv("IDP_BACKEND_PORT", "8000"))
BACKEND_URL = os.getenv("IDP_BACKEND_URL", f"http://127.0.0.1:{BACKEND_PORT}").rstrip("/")
HEALTH_URL = f"{BACKEND_URL}/health"
STARTUP_TIMEOUT_SECONDS = 20


def backend_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def start_backend_process() -> None:
    current = st.session_state.get("backend_process")
    if current and current.poll() is None:
        return

    env = os.environ.copy()
    # Allow embedding the FastAPI UI in Streamlit iframe.
    env["ALLOW_FRAME_EMBED"] = "1"

    process = subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "app.py")],
        cwd=str(ROOT_DIR),
        env=env,
    )
    st.session_state.backend_process = process


def wait_for_backend(timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if backend_is_healthy():
            return True
        time.sleep(0.5)
    return backend_is_healthy()


st.set_page_config(
    page_title="IDP Intelligence Website",
    page_icon="🌐",
    layout="wide",
)

st.title("IDP Intelligence Website")
st.caption("This Streamlit page hosts the FastAPI website flow.")

if not backend_is_healthy():
    with st.spinner("Starting website backend..."):
        start_backend_process()
        ready = wait_for_backend(STARTUP_TIMEOUT_SECONDS)
else:
    ready = True

if ready:
    st.success(f"Website is running at {BACKEND_URL}")
    st.markdown(f"[Open Website In New Tab]({BACKEND_URL})")
    components.iframe(src=BACKEND_URL, height=900, scrolling=True)
else:
    st.error("Backend could not be started from Streamlit.")
    st.code("python app.py", language="bash")
    st.markdown(
        "After starting backend manually, refresh this Streamlit page "
        "to load the proper website."
    )

