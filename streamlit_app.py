import os
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st

# Add project root and backend to path for package imports.
ROOT_PATH = Path(__file__).parent
sys.path.append(str(ROOT_PATH))
sys.path.append(str(ROOT_PATH / "backend"))

from backend.agent_graph import build_agent_graph
from backend.parser import chunk_text, extract_text_from_pdf
from backend.report_generator import generate_pdf_report
from streamlit_chat_utils import build_edited_filename, rebuild_pdf_edits_from_chat_history


def generate_captcha_code() -> str:
    return f"{random.randint(10000, 99999)}"


def initialize_session_state() -> None:
    defaults = {
        "gate_stage": "captcha",
        "captcha_code": generate_captcha_code(),
        "captcha_verified": False,
        "user_details_verified": False,
        "user_profile": {"email": "", "phone": ""},
        "vector_store": None,
        "chat_history": [],
        "annotations": [],
        "doc_filename": "",
        "graph": None,
        "original_pdf_bytes": None,
        "pdf_edits": [],
        "editing_turn_index": None,
        "editing_query_text": "",
        "is_editing_turn": False,
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
        "annotations",
        "doc_filename",
        "graph",
        "original_pdf_bytes",
        "pdf_edits",
        "editing_turn_index",
        "editing_query_text",
        "is_editing_turn",
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    initialize_session_state()


def build_query_context(query: str) -> str:
    context = st.session_state.vector_store.search(query, top_k=5)
    if st.session_state.annotations:
        notes = "\n".join(f"- {a['text']}" for a in st.session_state.annotations)
        context += f"\n\n[User Annotations]\n{notes}"
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


def append_chat_turn(query: str, response: str) -> None:
    st.session_state.chat_history.append(
        {
            "query": query,
            "response": response,
            "timestamp": datetime.now(UTC).strftime("%H:%M"),
        }
    )
    st.session_state.pdf_edits = rebuild_pdf_edits_from_chat_history(st.session_state.chat_history)


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


def handle_edit_save() -> None:
    edit_index = st.session_state.editing_turn_index
    edited_query = st.session_state.get("pending_edited_query", "").strip()
    if edit_index is None:
        st.error("No message selected for editing.")
        return
    if not edited_query:
        st.error("Edited message cannot be empty.")
        return

    try:
        regenerated_answer = generate_answer_for_query(edited_query)
    except Exception as exc:
        st.error(f"Error regenerating edited message: {exc}")
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
                st.session_state.original_pdf_bytes = uploaded_file.getvalue()

                try:
                    regenerate_index_from_pdf_bytes(st.session_state.original_pdf_bytes)
                    st.session_state.doc_filename = uploaded_file.name
                    st.session_state.chat_history = []
                    st.session_state.annotations = []
                    st.session_state.pdf_edits = []
                    clear_edit_state()
                    st.success("PDF indexed successfully.")
                except Exception as exc:
                    st.error(f"Failed to process uploaded PDF: {exc}")

        st.markdown("---")
        st.subheader("Annotations")
        new_note = st.text_input("Add a private note/context", key="note_input")
        if st.button("Add annotation") and new_note.strip():
            st.session_state.annotations.append(
                {
                    "text": new_note.strip(),
                    "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
                }
            )
            st.rerun()

        if st.session_state.annotations:
            for idx, note in enumerate(st.session_state.annotations):
                with st.expander(f"Note {idx + 1} ({note['timestamp']})"):
                    st.write(note["text"])
                    if st.button("Delete", key=f"delete_note_{idx}"):
                        st.session_state.annotations.pop(idx)
                        st.rerun()

    col1, col2 = st.columns([3, 2])
    with col1:
        st.header("PDF Chat Workspace")

    updated_pdf_data = None
    with col2:
        if st.session_state.doc_filename and st.session_state.original_pdf_bytes:
            updated_pdf_data = generate_pdf_report(
                filename=st.session_state.doc_filename,
                annotations=st.session_state.annotations,
                chat_history=st.session_state.chat_history,
                original_pdf_bytes=st.session_state.original_pdf_bytes,
                pdf_edits=st.session_state.pdf_edits,
            )
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
                    except Exception as exc:
                        st.error(f"Failed to apply edited PDF: {exc}")
                    else:
                        st.session_state.original_pdf_bytes = updated_pdf_data
                        st.session_state.doc_filename = build_edited_filename(st.session_state.doc_filename)
                        st.session_state.chat_history = []
                        st.session_state.annotations = []
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

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = generate_answer_for_query(prompt)
                st.write(answer)
                append_chat_turn(prompt, answer)
                st.rerun()
            except Exception as exc:
                st.error(f"Error invoking agent: {exc}")


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
