import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add project root and backend to path for package imports.
ROOT_PATH = Path(__file__).parent
sys.path.append(str(ROOT_PATH))
sys.path.append(str(ROOT_PATH / "backend"))

from backend.agent_graph import build_agent_graph
from backend.parser import chunk_text, extract_text_from_pdf
from backend.report_generator import generate_pdf_report
from backend.vector_store import VectorStore


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
        "captcha_input",
        "note_input",
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
    initialize_session_state()


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
                st.session_state.captcha_input = ""
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

                temp_path = ROOT_PATH / "backend" / f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(st.session_state.original_pdf_bytes)

                try:
                    text = extract_text_from_pdf(str(temp_path))
                    if not text.strip():
                        st.error("No text found in PDF.")
                    else:
                        chunks = chunk_text(text)

                        if st.session_state.vector_store is None:
                            st.session_state.vector_store = VectorStore()
                        else:
                            st.session_state.vector_store.clear()

                        st.session_state.vector_store.add_documents(chunks)

                        st.session_state.doc_filename = uploaded_file.name
                        st.session_state.chat_history = []
                        st.session_state.annotations = []
                        st.session_state.pdf_edits = []
                        st.success(f"Indexed {len(chunks)} chunks.")
                finally:
                    if temp_path.exists():
                        os.remove(temp_path)

        st.markdown("---")
        st.subheader("Annotations")
        new_note = st.text_input("Add a private note/context", key="note_input")
        if st.button("Add annotation") and new_note.strip():
            st.session_state.annotations.append(
                {
                    "text": new_note.strip(),
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
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

    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("PDF Chat Workspace")
    with col2:
        if st.session_state.doc_filename and st.session_state.original_pdf_bytes:
            updated_pdf_data = generate_pdf_report(
                filename=st.session_state.doc_filename,
                annotations=st.session_state.annotations,
                chat_history=st.session_state.chat_history,
                original_pdf_bytes=st.session_state.original_pdf_bytes,
                pdf_edits=st.session_state.pdf_edits,
            )
            st.download_button(
                label="Download updated PDF",
                data=updated_pdf_data,
                file_name=f"{st.session_state.doc_filename.replace('.pdf', '')}_Updated.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    if not st.session_state.doc_filename:
        st.info("Upload a PDF in the sidebar to start chatting.")
        return

    for chat in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(chat["query"])
        with st.chat_message("assistant"):
            st.write(chat["response"])

    prompt = st.chat_input("Ask something about the document...")
    if not prompt:
        return

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            context = st.session_state.vector_store.search(prompt, top_k=5)
            if st.session_state.annotations:
                notes = "\n".join(f"- {a['text']}" for a in st.session_state.annotations)
                context += f"\n\n[User Annotations]\n{notes}"

            state = {
                "input_query": prompt,
                "context": context,
                "result": "",
            }

            try:
                result_state = st.session_state.graph.invoke(state)
                answer = result_state.get("result", "I could not find an answer in the document.").strip()
                st.write(answer)

                edit_pattern = r"\[\[EDIT:\s*Page\s*(\d+)\s*\|\s*(.*?)\]\]"
                edits_found = re.findall(edit_pattern, answer)
                for page_num, content in edits_found:
                    st.session_state.pdf_edits.append({"page": page_num, "text": content.strip()})

                st.session_state.chat_history.append(
                    {
                        "query": prompt,
                        "response": answer,
                        "timestamp": datetime.utcnow().strftime("%H:%M"),
                    }
                )
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
