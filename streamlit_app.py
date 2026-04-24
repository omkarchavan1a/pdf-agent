import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT_DIR = Path(__file__).parent
BACKEND_URL = os.getenv("IDP_BACKEND_URL", "").strip().rstrip("/")
STARTUP_TIMEOUT_SECONDS = int(os.getenv("IDP_BACKEND_STARTUP_TIMEOUT", "60"))
DEFAULT_LOCAL_HOST = "127.0.0.1"
STREAMLIT_SHARING_MODE = os.getenv("STREAMLIT_SHARING_MODE", "").strip().lower()


def pick_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_LOCAL_HOST, 0))
        return int(sock.getsockname()[1])


def resolve_backend_url() -> str:
    configured = os.getenv("IDP_BACKEND_URL", "").strip().rstrip("/")
    if configured:
        return configured
    port = st.session_state.get("backend_port")
    if not port:
        port = int(os.getenv("IDP_BACKEND_PORT", "8000"))
    return f"http://{DEFAULT_LOCAL_HOST}:{port}"


def health_url_for(base_url: str) -> str:
    return f"{base_url}/health"


def backend_is_healthy(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url_for(base_url), timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def backend_start_logs() -> tuple[str, str]:
    stdout_path = ROOT_DIR / ".backend_stdout.log"
    stderr_path = ROOT_DIR / ".backend_stderr.log"
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    return stdout, stderr


def start_backend_process(local_port: int) -> None:
    current = st.session_state.get("backend_process")
    if current and current.poll() is None:
        return

    env = os.environ.copy()
    # Allow embedding the FastAPI UI in Streamlit iframe.
    env["ALLOW_FRAME_EMBED"] = "1"

    env["IDP_BACKEND_HOST"] = DEFAULT_LOCAL_HOST
    env["IDP_BACKEND_PORT"] = str(local_port)

    stdout_path = ROOT_DIR / ".backend_stdout.log"
    stderr_path = ROOT_DIR / ".backend_stderr.log"
    stdout_file = open(stdout_path, "w", encoding="utf-8")
    stderr_file = open(stderr_path, "w", encoding="utf-8")

    process = subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "app.py")],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=stdout_file,
        stderr=stderr_file,
    )
    stdout_file.close()
    stderr_file.close()
    st.session_state.backend_process = process


def wait_for_backend(base_url: str, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if backend_is_healthy(base_url):
            return True
        time.sleep(0.5)
    return backend_is_healthy(base_url)


st.set_page_config(
    page_title="IDP Intelligence Website",
    page_icon="🌐",
    layout="wide",
)

st.title("IDP Intelligence Website")
st.caption("This Streamlit page hosts the FastAPI website flow.")

backend_url = resolve_backend_url()
is_external_backend = bool(BACKEND_URL)

if not backend_is_healthy(backend_url):
    if is_external_backend:
        ready = False
    else:
        with st.spinner("Starting website backend..."):
            local_port = st.session_state.get("backend_port") or pick_free_local_port()
            st.session_state.backend_port = local_port
            backend_url = f"http://{DEFAULT_LOCAL_HOST}:{local_port}"
            start_backend_process(local_port)
            ready = wait_for_backend(backend_url, STARTUP_TIMEOUT_SECONDS)
else:
    ready = True

if ready:
    st.success(f"Website is running at {backend_url}")
    st.markdown(f"[Open Website In New Tab]({backend_url})")
    if STREAMLIT_SHARING_MODE == "streamlit" and backend_url.startswith(f"http://{DEFAULT_LOCAL_HOST}:"):
        st.warning(
            "This deployment appears to be Streamlit Community Cloud. "
            "A localhost backend is not browser-reachable there. "
            "Set `IDP_BACKEND_URL` to a public backend URL."
        )
    components.iframe(src=backend_url, height=900, scrolling=True)
else:
    if is_external_backend:
        st.error(f"Configured backend is unreachable: {backend_url}")
        st.markdown("Set `IDP_BACKEND_URL` to a reachable backend URL and refresh.")
    else:
        st.error("Backend could not be started from Streamlit.")
        st.code("python app.py", language="bash")
        stdout, stderr = backend_start_logs()
        if stderr.strip() or stdout.strip():
            st.caption("Backend startup logs")
            st.code((stderr or stdout)[-4000:], language="bash")
        st.markdown(
            "After starting backend manually, refresh this Streamlit page "
            "to load the proper website."
        )
