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
from datetime import datetime

from parser import extract_text_from_pdf, chunk_text
from agent_graph import build_agent_graph
from vector_store import VectorStore
from report_generator import generate_pdf_report

app = FastAPI(title="AI Document Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── App State ──────────────────────────────────────────────────────────────
app.state.vector_store  = None
app.state.annotations   = []          # List of { text, timestamp }
app.state.chat_history  = []          # List of { query, response, timestamp }
app.state.doc_filename  = ""

# ── Static Frontend ────────────────────────────────────────────────────────
BASE_DIR     = pathlib.Path(__file__).parent.parent
frontend_dir = BASE_DIR / "frontend"
static_dir   = frontend_dir / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_frontend():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found"}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "document_loaded": app.state.vector_store is not None,
        "annotations_count": len(app.state.annotations),
        "chat_count": len(app.state.chat_history),
        "filename": app.state.doc_filename,
    }

# ── Models ─────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str

class AnnotationRequest(BaseModel):
    text: str

# ── Build LangGraph ────────────────────────────────────────────────────────
graph = build_agent_graph()

# ── Upload Endpoint ────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_location = BASE_DIR / "backend" / f"temp_{file.filename}"
    chunks = []
    try:
        with open(str(file_location), "wb+") as f:
            shutil.copyfileobj(file.file, f)

        text_content = extract_text_from_pdf(str(file_location))
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="Could not extract text. The PDF may be image-only or scanned.")

        chunks = chunk_text(text_content)

        if app.state.vector_store is None:
            app.state.vector_store = VectorStore()
        else:
            app.state.vector_store.clear()

        app.state.vector_store.add_documents(chunks)

        # Reset session state for new document
        app.state.annotations  = []
        app.state.chat_history = []
        app.state.doc_filename = file.filename

        print(f"[OK] Indexed {len(chunks)} chunks from '{file.filename}'")

    finally:
        if file_location.exists():
            os.remove(str(file_location))

    return {
        "message": f"'{file.filename}' processed successfully.",
        "chunks_indexed": len(chunks),
        "filename": file.filename
    }

# ── Chat Endpoint ──────────────────────────────────────────────────────────
@app.post("/chat")
async def chat_with_pdf(request: QueryRequest):
    if app.state.vector_store is None:
        return {"error": "No document loaded. Please upload a PDF first."}

    if not request.query.strip():
        return {"error": "Query cannot be empty."}

    # Semantic retrieval from document
    retrieved_context = app.state.vector_store.search(request.query, top_k=5)

    # Inject user annotations into context
    annotation_context = ""
    if app.state.annotations:
        notes = "\n".join(f"- {a['text']}" for a in app.state.annotations)
        annotation_context = f"\n\n[User Annotations on this document]\n{notes}"

    full_context = retrieved_context + annotation_context

    if not full_context.strip():
        return {"response": "I searched the document but couldn't find relevant content. Try rephrasing your question."}

    state = {
        "input_query": request.query,
        "context": full_context,
        "result": ""
    }

    try:
        result_state = graph.invoke(state)
        answer = result_state.get("result", "").strip()
        if not answer:
            answer = "The model returned an empty response. Please try again."

        # Save to chat history for report
        app.state.chat_history.append({
            "query": request.query,
            "response": answer,
            "timestamp": datetime.utcnow().strftime("%H:%M")
        })

        return {"response": answer}
    except Exception as e:
        print(f"[CRITICAL] Agent Workflow Error: {str(e)}")
        return {"error": f"Agent error: {str(e)}"}

# ── Annotations Endpoints ──────────────────────────────────────────────────
@app.post("/annotations")
async def add_annotation(req: AnnotationRequest):
    """Add a user annotation to the current document session."""
    if app.state.vector_store is None:
        raise HTTPException(status_code=400, detail="Upload a document first before adding annotations.")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Annotation text cannot be empty.")

    annotation = {
        "text": req.text.strip(),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    }
    app.state.annotations.append(annotation)
    print(f"[OK] Annotation added: '{req.text[:40]}...'")
    return {"message": "Annotation saved.", "total": len(app.state.annotations), "annotation": annotation}

@app.get("/annotations")
async def get_annotations():
    """Retrieve all annotations for the current session."""
    return {"annotations": app.state.annotations}

@app.delete("/annotations/{index}")
async def delete_annotation(index: int):
    """Delete an annotation by its index."""
    if index < 0 or index >= len(app.state.annotations):
        raise HTTPException(status_code=404, detail="Annotation not found.")
    removed = app.state.annotations.pop(index)
    return {"message": "Deleted.", "removed": removed}

# ── Download Report Endpoint ───────────────────────────────────────────────
@app.get("/download-report")
async def download_report():
    """Generate and stream a PDF report of the current analysis session."""
    if app.state.vector_store is None:
        raise HTTPException(status_code=400, detail="No document loaded. Upload a PDF first.")

    pdf_bytes = generate_pdf_report(
        filename=app.state.doc_filename,
        annotations=app.state.annotations,
        chat_history=app.state.chat_history,
    )

    report_name = f"IDP_Report_{app.state.doc_filename.replace('.pdf', '')}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_name}"'}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
