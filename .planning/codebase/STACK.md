# STACK

## Core Technology Stack
- **Language:** Python 3.x
- **Framework:** FastAPI (REST API framework)
- **Server:** Uvicorn (ASGI server)

## AI & Machine Learning
- **Orchestration:** LangChain, LangGraph
- **Models & Inference:** 
  - Hugging Face Endpoints (`langchain-huggingface`)
  - Hugging Face Hub (`huggingface_hub`)
  - Target LLM: `gemma-4-31B-it`
- **Embeddings:**
  - `sentence-transformers/all-MiniLM-L6-v2` (Laptop context)
  - `EmbeddingGemma-300M` (Mobile context)
- **Vector Search / Indexing:** FAISS (`faiss-cpu`)

## Data Extraction
- **PDF Parsing:** PyMuPDF (`fitz`)
- **Other utilities:** `tensorflow` (Available but currently not strictly utilized in existing code)

## Environment & Security
- `python-dotenv` (For managing API credentials)
