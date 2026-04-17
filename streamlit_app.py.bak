import streamlit as st
import os
import sys
import shutil
import io
from datetime import datetime
from pathlib import Path

# Add project root to path for package imports
sys.path.append(str(Path(__file__).parent))

from backend.parser import extract_text_from_pdf, chunk_text
from backend.agent_graph import build_agent_graph
from backend.vector_store import VectorStore
from backend.report_generator import generate_pdf_report

# ── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Intelligence Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Initialize Session State ────────────────────────────────────────────────
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "annotations" not in st.session_state:
    st.session_state.annotations = []
if "doc_filename" not in st.session_state:
    st.session_state.doc_filename = ""
if "graph" not in st.session_state:
    st.session_state.graph = build_agent_graph()
if "original_pdf_bytes" not in st.session_state:
    st.session_state.original_pdf_bytes = None

# ── Sidebar: Document Management ────────────────────────────────────────────
with st.sidebar:
    st.title("📄 PDF Agent")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])
    
    if uploaded_file and uploaded_file.name != st.session_state.doc_filename:
        with st.spinner(f"Indexing {uploaded_file.name}..."):
            # Store original bytes for later merging
            st.session_state.original_pdf_bytes = uploaded_file.getvalue()
            
            # Save temp file for indexing
            temp_path = Path("backend") / f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(st.session_state.original_pdf_bytes)
            
            try:
                # Extract and Chunk
                text = extract_text_from_pdf(str(temp_path))
                if not text.strip():
                    st.error("No text found in PDF.")
                else:
                    chunks = chunk_text(text)
                    
                    # Initialize or Clear Vector Store
                    if st.session_state.vector_store is None:
                        st.session_state.vector_store = VectorStore()
                    else:
                        st.session_state.vector_store.clear()
                    
                    st.session_state.vector_store.add_documents(chunks)
                    
                    # Update State
                    st.session_state.doc_filename = uploaded_file.name
                    st.session_state.chat_history = []
                    st.session_state.annotations = []
                    st.success(f"Successfully indexed {len(chunks)} chunks!")
            finally:
                if temp_path.exists():
                    os.remove(temp_path)

    st.markdown("---")
    st.subheader("📝 User Annotations")
    new_note = st.text_input("Add a private note/context:", key="note_input")
    if st.button("Add Annotation") and new_note:
        st.session_state.annotations.append({
            "text": new_note,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        })
        st.rerun()

    if st.session_state.annotations:
        for i, note in enumerate(st.session_state.annotations):
            with st.expander(f"Note {i+1} ({note['timestamp']})"):
                st.write(note["text"])
                if st.button("Delete", key=f"del_{i}"):
                    st.session_state.annotations.pop(i)
                    st.rerun()

# ── Main UI: Chat Interface ─────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.header("🔍 Document Chat")
with col2:
    if st.session_state.doc_filename and st.session_state.original_pdf_bytes:
        # Generate the consolidated PDF (Original + Appendix)
        updated_pdf_data = generate_pdf_report(
            filename=st.session_state.doc_filename,
            annotations=st.session_state.annotations,
            chat_history=st.session_state.chat_history,
            original_pdf_bytes=st.session_state.original_pdf_bytes
        )
        st.download_button(
            label="📥 Download Updated PDF",
            data=updated_pdf_data,
            file_name=f"{st.session_state.doc_filename.replace('.pdf', '')}_Updated.pdf",
            mime="application/pdf",
            use_container_width=True
        )

if not st.session_state.doc_filename:
    st.info("Please upload a PDF document in the sidebar to start chatting.")
else:
    # Display Chat History In a Container
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat["query"])
            with st.chat_message("assistant"):
                st.write(chat["response"])

    # Chat Input
    if prompt := st.chat_input("Ask something about the document..."):
        with st.chat_message("user"):
            st.write(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # 1. Retrieval
                context = st.session_state.vector_store.search(prompt, top_k=5)
                
                # 2. Inject Annotations
                if st.session_state.annotations:
                    notes = "\n".join(f"- {a['text']}" for a in st.session_state.annotations)
                    context += f"\n\n[User Annotations]\n{notes}"
                
                # 3. Agent Execution
                state = {
                    "input_query": prompt,
                    "context": context,
                    "result": ""
                }
                
                try:
                    result_state = st.session_state.graph.invoke(state)
                    answer = result_state.get("result", "I couldn't find an answer in the document.").strip()
                    
                    st.write(answer)
                    
                    # 4. Save to History
                    st.session_state.chat_history.append({
                        "query": prompt,
                        "response": answer,
                        "timestamp": datetime.utcnow().strftime("%H:%M")
                    })
                    st.rerun() # Ensure download button updates with new history
                except Exception as e:
                    st.error(f"Error invoking agent: {e}")

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid #1E293B;
    }
    .stButton>button {
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        border-color: #00D1FF;
        box-shadow: 0 0 10px rgba(0, 209, 255, 0.2);
    }
</style>
""", unsafe_allow_html=True)
