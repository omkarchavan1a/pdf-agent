"""
IDP Intelligence Agent — Unified FastAPI Root Application
Serves the Premium HTML/JS Frontend and provides the Intelligence API.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import pathlib
import io
import sys
from datetime import datetime

# Logic imports from the backend package
ROOT_DIR     = pathlib.Path(__file__).parent
backend_dir  = ROOT_DIR / "backend"
sys.path.append(str(backend_dir))

from backend.parser import extract_text_from_pdf, chunk_text
from backend.agent_graph import build_agent_graph
from backend.vector_store import VectorStore
from backend.report_generator import generate_pdf_report

app = FastAPI(title="IDP Intelligence API")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── App State ──────────────────────────────────────────────────────────────
# In a real production app, this would use a database and distributed cache.
# For this session-based agent, we maintain internal state.
class AppState:
    def __init__(self):
        self.vector_store = None
        self.annotations = []
        self.chat_history = []
        self.doc_filename = ""

state = AppState()

# ── Static Frontend ────────────────────────────────────────────────────────
ROOT_DIR     = pathlib.Path(__file__).parent
frontend_dir = ROOT_DIR / "frontend"
static_dir   = frontend_dir / "static"

# Serve JS, CSS, and images
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the premium index.html."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Premium frontend not found in /frontend/index.html"}

@app.get("/health")
async def health_check():
    """Health check for frontend connection polling."""
    return {
        "status": "ok",
        "document_loaded": state.vector_store is not None,
        "annotations_count": len(state.annotations),
        "chat_count": len(state.chat_history),
        "filename": state.doc_filename,
    }

# ── Models ─────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str

class AnnotationRequest(BaseModel):
    text: str

# ── Intelligence AI Graph ──────────────────────────────────────────────────
graph = build_agent_graph()

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Extract and index a PDF for semantic intelligence."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_location = ROOT_DIR / "backend" / f"temp_{file.filename}"
    try:
        with open(str(file_location), "wb+") as f:
            shutil.copyfileobj(file.file, f)

        text_content = extract_text_from_pdf(str(file_location))
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text. PDF might be scanned/image-only.")

        chunks = chunk_text(text_content)
        
        # Initialize Vector Store
        if state.vector_store is None:
            state.vector_store = VectorStore()
        else:
            state.vector_store.clear()

        state.vector_store.add_documents(chunks)

        # Reset session context
        state.annotations = []
        state.chat_history = []
        state.doc_filename = file.filename

        return {"status": "success", "chunks_indexed": len(chunks), "filename": file.filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")
    finally:
        if file_location.exists():
            os.remove(file_location)

@app.post("/chat")
async def chat(request: QueryRequest):
    """Ask the IDP Agent about the loaded document."""
    if state.vector_store is None:
        raise HTTPException(status_code=400, detail="No document loaded. Please upload a PDF first.")

    try:
        # Construct context from vector store and annotations
        # For simplicity, we pass state variables to the graph
        # In a larger app, this would be managed via a proper session/state store
        inputs = {
            "query": request.query,
            "vector_store": state.vector_store,
            "annotations": state.annotations,
            "chat_history": state.chat_history
        }
        
        # Invoke the LangGraph agent
        result = graph.invoke(inputs)
        response_text = result.get("response", "I'm sorry, I couldn't formulate a response.")

        # Save to history
        state.chat_history.append({
            "query": request.query,
            "response": response_text,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        })

        return {"response": response_text}
    except Exception as e:
        return {"error": f"Agent Error: {str(e)}"}

@app.get("/annotations")
async def get_annotations():
    """Retrieve all current annotations."""
    return {"annotations": state.annotations}

@app.post("/annotations")
async def add_annotation(req: AnnotationRequest):
    """Save a new user annotation."""
    new_ann = {
        "text": req.text,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    }
    state.annotations.append(new_ann)
    return {"status": "success", "annotation": new_ann}

@app.delete("/annotations/{index}")
async def delete_annotation(index: int):
    """Delete an annotation by index."""
    if 0 <= index < len(state.annotations):
        state.annotations.pop(index)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Annotation not found")

@app.get("/download-report")
async def download_report():
    """Generate and return a PDF intelligence report."""
    if not state.doc_filename:
        raise HTTPException(status_code=400, detail="No document metadata available to generate report.")

    try:
        pdf_bytes = generate_pdf_report(
            filename=state.doc_filename,
            chat_history=state.chat_history,
            annotations=state.annotations
        )
        
        readable_fn = state.doc_filename.replace(".pdf", "")
        output_fn = f"IDP_Intelligence_{readable_fn}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{output_fn}\""}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # IDP Agent standard port is 8000
    print("🚀 IDP Intelligence Agent starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
