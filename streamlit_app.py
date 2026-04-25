import logging
import os
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import fitz
import streamlit as st

# Add project root and backend to path for package imports.
ROOT_PATH = Path(__file__).parent
sys.path.append(str(ROOT_PATH))
sys.path.append(str(ROOT_PATH / "backend"))

from backend.agent_graph import build_agent_graph
from backend.parser import chunk_text, extract_text_from_pdf
from backend.report_generator import generate_pdf_report
from streamlit_chat_utils import (
    DEFAULT_MAX_EDIT_TEXT_LEN,
    build_edited_filename,
    extract_pdf_edits_from_response,
    normalize_pdf_edits,
    parse_direct_edit_command,
    rebuild_pdf_edits_from_chat_history,
    strip_control_chars,
)


LOGGER = logging.getLogger(__name__)
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
MAX_CHAT_INPUT_CHARS = 2000


def generate_captcha_code() -> str:
    return f"{random.randint(10000, 99999)}"


def now_timestamp(fmt: str) -> str:
    return datetime.now(UTC).strftime(fmt)


def sanitize_chat_input(text: str) -> str:
    cleaned = strip_control_chars(text or "").strip()
    return cleaned[:MAX_CHAT_INPUT_CHARS]


def is_probably_pdf(data: bytes) -> bool:
    if not data:
        return False
    probe = data[:1024]
    return b"%PDF-" in probe


def validate_pdf_upload(filename: str, data: bytes) -> str | None:
    if not (filename or "").lower().endswith(".pdf"):
        return "Only PDF files are supported."
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        return "PDF is too large. Maximum allowed size is 25 MB."
    if not is_probably_pdf(data):
        return "Invalid PDF file signature."
    return None


def initialize_session_state() -> None:
    defaults = {
        "gate_stage": "captcha",
        "captcha_code": generate_captcha_code(),
        "captcha_verified": False,
        "user_details_verified": False,
        "user_profile": {"email": "", "phone": ""},
        "vector_store": None,
        "chat_history": [],
        "doc_filename": "",
        "graph": None,
        "original_pdf_bytes": None,
        "pdf_edits": [],
        "editing_turn_index": None,
        "editing_query_text": "",
        "is_editing_turn": False,
        "pending_edited_query": "",
        "flash_message": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.graph is None:
        st.session_state.graph = build_agent_graph()


def enforce_gate_order() -> None:
    if st.session_state.gate_stage == "user_details" and not st.session_state.captcha_verified:
        st.session_state.gate_stage = "captcha"
    if st.session_state.gate_stage == "app" and not st.session_state.user_details_verified:
        st.session_state.gate_stage = "user_details" if st.session_state.captcha_verified else "captcha"


def clear_edit_state() -> None:
    st.session_state.editing_turn_index = None
    st.session_state.editing_query_text = ""
    st.session_state.is_editing_turn = False
    st.session_state.pending_edited_query = ""


def get_or_create_vector_store():
    if st.session_state.vector_store is None:
        # Lazy import avoids loading heavy transformer modules before needed.
        from backend.vector_store import VectorStore

        st.session_state.vector_store = VectorStore()
    return st.session_state.vector_store


def reset_session_to_captcha() -> None:
    keys_to_remove = [
        "gate_stage",
        "captcha_code",
        "captcha_verified",
        "user_details_verified",
        "user_profile",
        "vector_store",
        "chat_history",
        "doc_filename",
        "graph",
        "original_pdf_bytes",
        "pdf_edits",
        "editing_turn_index",
        "editing_query_text",
        "is_editing_turn",
        "pending_edited_query",
        "flash_message",
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    initialize_session_state()


def get_current_page_count() -> int:
    pdf_bytes = st.session_state.original_pdf_bytes
    if not pdf_bytes:
        return 0
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        doc.close()
        return page_count
    except Exception:
        return 0


def build_query_context(query: str) -> str:
    context = st.session_state.vector_store.search(query, top_k=5)
    return context


def generate_answer_for_query(query: str) -> str:
    state = {
        "input_query": query,
        "context": build_query_context(query),
        "result": "",
    }
    result_state = st.session_state.graph.invoke(state)
    answer = result_state.get("result", "I could not find an answer in the document.").strip()
    return answer


def rebuild_effective_pdf_edits() -> None:
    page_count = get_current_page_count()
    st.session_state.pdf_edits = rebuild_pdf_edits_from_chat_history(
        st.session_state.chat_history,
        page_count=page_count,
        max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
    )


def append_chat_turn(query: str, response: str) -> None:
    st.session_state.chat_history.append(
        {
            "query": query,
            "response": response,
            "timestamp": now_timestamp("%H:%M"),
        }
    )
    rebuild_effective_pdf_edits()


def regenerate_index_from_pdf_bytes(pdf_bytes: bytes) -> None:
    temp_path = ROOT_PATH / "backend" / f"temp_streamlit_{uuid4().hex}.pdf"
    with open(temp_path, "wb") as temp_file:
        temp_file.write(pdf_bytes)

    try:
        text = extract_text_from_pdf(str(temp_path))
        if not text.strip():
            raise ValueError("No text found in edited PDF.")
        chunks = chunk_text(text)
        vector_store = get_or_create_vector_store()
        vector_store.clear()
        vector_store.add_documents(chunks)
    finally:
        if temp_path.exists():
            os.remove(temp_path)


def build_updated_pdf_bytes() -> bytes:
    return generate_pdf_report(
        filename=st.session_state.doc_filename,
        annotations=[],
        chat_history=st.session_state.chat_history,
        original_pdf_bytes=st.session_state.original_pdf_bytes,
        pdf_edits=st.session_state.pdf_edits,
    )


def handle_edit_save() -> None:
    edit_index = st.session_state.editing_turn_index
    edited_query = sanitize_chat_input(st.session_state.get("pending_edited_query", ""))
    if edit_index is None:
        st.error("No message selected for editing.")
        return
    if not edited_query:
        st.error("Edited message cannot be empty.")
        return

    try:
        regenerated_answer = generate_answer_for_query(edited_query)
    except Exception:
        LOGGER.exception("Error regenerating edited message")
        st.error("Could not regenerate edited response. Please try again.")
        return

    st.session_state.chat_history = st.session_state.chat_history[:edit_index]
    append_chat_turn(edited_query, regenerated_answer)
    clear_edit_state()
    st.rerun()


def render_captcha_gate() -> None:
    st.title("IDP Intelligence Access")
    st.caption("Step 1 of 3: Enter the random captcha number to continue.")

    with st.container(border=True):
        st.subheader("Random Captcha Verification")
        st.write("Type the exact number shown below.")
        st.code(st.session_state.captcha_code, language="text")

        st.text_input("Captcha number", key="captcha_input", max_chars=5)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Refresh code", use_container_width=True):
                st.session_state.captcha_code = generate_captcha_code()
                st.rerun()
        with col2:
            if st.button("Continue", type="primary", use_container_width=True):
                entered = st.session_state.get("captcha_input", "").strip()
                if entered == st.session_state.captcha_code:
                    st.session_state.captcha_verified = True
                    st.session_state.gate_stage = "user_details"
                    st.rerun()
                st.error("Captcha does not match. Try again.")


def render_user_details_gate() -> None:
    st.title("User Details")
    st.caption("Step 2 of 3: Fill user details to continue.")

    with st.container(border=True):
        st.subheader("Enter Details")
        profile = st.session_state.user_profile
        with st.form("user_details_form", clear_on_submit=False):
            email = st.text_input("Gmail address", value=profile.get("email", ""))
            phone = st.text_input("Phone number", value=profile.get("phone", ""))
            submitted = st.form_submit_button("Continue", type="primary")

        if submitted:
            email_clean = email.strip().lower()
            phone_clean = phone.strip()
            if not email_clean.endswith("@gmail.com"):
                st.error("Please use a valid Gmail address.")
                return
            if not phone_clean:
                st.error("Phone number is required.")
                return
            st.session_state.user_profile = {"email": email_clean, "phone": phone_clean}
            st.session_state.user_details_verified = True
            st.session_state.gate_stage = "app"
            st.rerun()


def render_pdf_chat_app() -> None:
    if st.session_state.flash_message:
        st.success(st.session_state.flash_message)
        st.session_state.flash_message = ""

    with st.sidebar:
        st.markdown(
            f"Logged in as `{st.session_state.user_profile.get('email', '')}`",
            help="Session details captured during onboarding.",
        )
        if st.button("Reset session", use_container_width=True):
            reset_session_to_captcha()
            st.rerun()

        st.markdown("---")
        st.subheader("Document")
        uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

        if uploaded_file and uploaded_file.name != st.session_state.doc_filename:
            with st.spinner(f"Indexing {uploaded_file.name}..."):
                uploaded_bytes = uploaded_file.getvalue()
                validation_error = validate_pdf_upload(uploaded_file.name, uploaded_bytes)
                if validation_error:
                    st.error(validation_error)
                else:
                    st.session_state.original_pdf_bytes = uploaded_bytes

                    try:
                        regenerate_index_from_pdf_bytes(st.session_state.original_pdf_bytes)
                        st.session_state.doc_filename = uploaded_file.name
                        st.session_state.chat_history = []
                        st.session_state.pdf_edits = []
                        clear_edit_state()
                        st.success("PDF indexed successfully.")
                    except Exception:
                        LOGGER.exception("Failed to process uploaded PDF")
                        st.error("Failed to process PDF safely. Try another PDF file.")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.header("PDF Chat Workspace")

    updated_pdf_data = None
    has_visible_edits = bool(st.session_state.pdf_edits)
    has_chat_history = bool(st.session_state.chat_history)
    has_effective_updates = has_visible_edits or has_chat_history

    with col2:
        if st.session_state.doc_filename and st.session_state.original_pdf_bytes:
            if has_visible_edits:
                st.info(f"Visible PDF edits captured: {len(st.session_state.pdf_edits)}")
            elif has_chat_history:
                st.info("Chat history will appear in the appendix section of downloaded PDF.")
            else:
                st.warning("No updates detected yet. Download will look close to original.")

            updated_pdf_data = build_updated_pdf_bytes()
            action_download, action_apply = st.columns(2)
            with action_download:
                st.download_button(
                    label="Download updated PDF",
                    data=updated_pdf_data,
                    file_name=f"{st.session_state.doc_filename.replace('.pdf', '')}_Updated.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with action_apply:
                if st.button("Apply edited PDF", use_container_width=True):
                    try:
                        regenerate_index_from_pdf_bytes(updated_pdf_data)
                    except Exception:
                        LOGGER.exception("Failed to apply edited PDF")
                        st.error("Failed to apply edited PDF. Please try again.")
                    else:
                        st.session_state.original_pdf_bytes = updated_pdf_data
                        st.session_state.doc_filename = build_edited_filename(st.session_state.doc_filename)
                        st.session_state.chat_history = []
                        st.session_state.pdf_edits = []
                        clear_edit_state()
                        st.success("Edited PDF applied. Chat reset for a fresh conversation.")
                        st.rerun()

    if not st.session_state.doc_filename:
        st.info("Upload a PDF in the sidebar to start chatting.")
        return

    for idx, chat in enumerate(st.session_state.chat_history):
        with st.chat_message("user"):
            text_col, action_col = st.columns([8, 1])
            text_col.write(chat["query"])
            if action_col.button("Edit", key=f"edit_turn_{idx}"):
                st.session_state.editing_turn_index = idx
                st.session_state.editing_query_text = chat["query"]
                st.session_state.is_editing_turn = True
                st.rerun()
        with st.chat_message("assistant"):
            st.write(chat["response"])

    if st.session_state.is_editing_turn:
        with st.container(border=True):
            st.subheader("Edit previous question")
            edited_value = st.text_area(
                "Edited question",
                value=st.session_state.editing_query_text,
                height=100,
            )
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save edit", type="primary", use_container_width=True):
                    st.session_state.pending_edited_query = edited_value
                    handle_edit_save()
            with cancel_col:
                if st.button("Cancel edit", use_container_width=True):
                    clear_edit_state()
                    st.rerun()
        return

    prompt = st.chat_input("Ask something about the document...")
    if not prompt:
        return

    sanitized_prompt = sanitize_chat_input(prompt)
    if not sanitized_prompt:
        st.error("Please enter a valid message.")
        return

    with st.chat_message("user"):
        st.write(sanitized_prompt)

    page_count = get_current_page_count()
    direct_edit = parse_direct_edit_command(
        sanitized_prompt,
        max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
    )

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                if direct_edit:
                    normalized_direct_edits = normalize_pdf_edits(
                        [direct_edit],
                        page_count=page_count,
                        max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
                    )
                    if not normalized_direct_edits:
                        st.error("Could not parse edit command. Use: /edit page=<n> text=<note>")
                        return
                    edit = normalized_direct_edits[0]
                    answer = (
                        f"Confirmed: change captured for page {edit['page']}. "
                        "It will appear in Download/Apply edited PDF.\n\n"
                        f"[[EDIT: Page {edit['page']} | {edit['text']}]]"
                    )
                else:
                    answer = generate_answer_for_query(sanitized_prompt)
                st.write(answer)
                append_chat_turn(sanitized_prompt, answer)

                parsed_edits = normalize_pdf_edits(
                    extract_pdf_edits_from_response(
                        answer,
                        max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
                    ),
                    page_count=page_count,
                    max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
                )
                if parsed_edits:
                    st.session_state.flash_message = (
                        f"Confirmed: {len(parsed_edits)} change(s) captured in PDF update queue."
                    )
                st.rerun()
            except Exception:
                LOGGER.exception("Error while processing chat message")
                st.error("Could not process this request. Please try again.")


st.set_page_config(
    page_title="PDF Intelligence Agent",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_session_state()
enforce_gate_order()

if st.session_state.gate_stage == "captcha":
    render_captcha_gate()
elif st.session_state.gate_stage == "user_details":
    render_user_details_gate()
else:
    render_pdf_chat_app()
