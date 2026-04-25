# INTEGRATIONS

## External APIs
- **Hugging Face Hub**: Used for LLM inference (Gemma) via LangChain's HuggingFaceEndpoint. Requires `HUGGINGFACEHUB_API_TOKEN` environment variable.

## Libraries & Frameworks
- **Streamlit**: Provides the interactive frontend web interface.
- **LangChain / LangGraph**: Orchestrates the state machine for processing queries and interactions with the LLM.
- **PyMuPDF (fitz)**: Extracts text from PDFs and creates merged PDF reports with annotations.
- **FPDF**: Generates the PDF appendix with the chat session summary and edits.
- **Sentence-Transformers & FAISS** (Optional): Provides semantic search capabilities for the vector store. Uses a lightweight deterministic fallback if not installed.
