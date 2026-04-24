from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import os
import shutil
import pathlib
import io
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime
from uuid import uuid4
from collections import defaultdict, deque
from pymongo import MongoClient
from pymongo.errors import PyMongoError

try:
    # Package imports (works when loaded as `backend.main`).
    from .parser import extract_text_from_pdf, chunk_text
    from .agent_graph import build_agent_graph
    from .vector_store import VectorStore
    from .report_generator import generate_pdf_report
except ImportError:
    # Script-mode fallback (works when running `python backend/main.py`).
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

# ── Basic API Security (headers + rate limiting) ───────────────────────────
RATE_LIMITS = {
    "/health": (60, 60),
    "/chat": (20, 60),
    "/upload": (8, 60),
    "/annotations": (30, 60),
    "/captcha/verify": (10, 60),
    "/user-details": (10, 60),
    "/chat/end": (20, 60),
}


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> Optional[JSONResponse]:
    path = request.url.path
    for prefix, (max_requests, window_sec) in RATE_LIMITS.items():
        if path.startswith(prefix):
            client_ip = get_client_ip(request)
            now = time.time()
            bucket = app.state.rate_buckets[f"{client_ip}:{prefix}"]
            while bucket and (now - bucket[0]) > window_sec:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please slow down."},
                    headers={"Retry-After": str(window_sec)},
                )
            bucket.append(now)
            break
    return None


def is_frame_embed_allowed() -> bool:
    return os.getenv("ALLOW_FRAME_EMBED", "").strip().lower() in {"1", "true", "yes", "on"}


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    blocked = enforce_rate_limit(request)
    if blocked:
        return blocked
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    allow_embed = is_frame_embed_allowed()
    if not allow_embed:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com https://challenges.cloudflare.com; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-src https://challenges.cloudflare.com"
    )
    if allow_embed:
        csp += "; frame-ancestors 'self' http://localhost:8501 http://127.0.0.1:8501"
    response.headers["Content-Security-Policy"] = csp
    return response

# ── App State ──────────────────────────────────────────────────────────────
app.state.vector_store = None
app.state.annotations = []          # List of { text, timestamp }
app.state.chat_history = []         # List of { query, response, timestamp }
app.state.doc_filename = ""
app.state.mongo_client = None
app.state.mongo_memory = None
app.state.rate_buckets = defaultdict(deque)
app.state.human_verified_sessions = set()

# ── Static Frontend ────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent.parent
frontend_dir = BASE_DIR / "frontend"
static_dir = frontend_dir / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def init_mongodb():
    mongo_uri = os.getenv("MONGODB_URI", "").strip()
    if not mongo_uri:
        return
    try:
        app.state.mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        app.state.mongo_client.admin.command("ping")
        db = app.state.mongo_client["idp_agent"]
        app.state.mongo_memory = db["conversation_memory"]
        app.state.mongo_memory.create_index("session_id", unique=True)
        app.state.mongo_memory.create_index("updated_at")
        print("[OK] MongoDB temporary memory enabled.")
    except Exception as exc:
        print(f"[WARN] MongoDB unavailable, continuing without it: {exc}")
        app.state.mongo_client = None
        app.state.mongo_memory = None


init_mongodb()


def upsert_session_memory(session_id: str, payload: dict):
    if not app.state.mongo_memory:
        return
    try:
        app.state.mongo_memory.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    **payload,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "session_id": session_id,
                    "created_at": datetime.utcnow(),
                },
            },
            upsert=True,
        )
    except PyMongoError as exc:
        print(f"[WARN] Failed to write temporary memory: {exc}")


def append_chat_memory(session_id: str, query: str, response: str):
    if not app.state.mongo_memory:
        return
    try:
        app.state.mongo_memory.update_one(
            {"session_id": session_id},
            {
                "$push": {
                    "chat_history": {
                        "query": query,
                        "response": response,
                        "timestamp": datetime.utcnow().strftime("%H:%M"),
                    }
                },
                "$set": {"updated_at": datetime.utcnow()},
                "$setOnInsert": {"session_id": session_id, "created_at": datetime.utcnow()},
            },
            upsert=True,
        )
    except PyMongoError as exc:
        print(f"[WARN] Failed to append temporary memory: {exc}")


def is_captcha_enabled() -> bool:
    return bool(os.getenv("TURNSTILE_SECRET_KEY", "").strip())


def verify_turnstile_token(token: str, remote_ip: str) -> bool:
    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        return True
    if not token.strip():
        return False
    payload = urllib.parse.urlencode({
        "secret": secret,
        "response": token.strip(),
        "remoteip": remote_ip,
    }).encode("utf-8")
    req = urllib.request.Request(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
            return bool(body.get("success"))
    except Exception as exc:
        print(f"[WARN] CAPTCHA verify failed: {exc}")
        return False


def session_is_human_verified(session_id: str) -> bool:
    if not session_id:
        return False
    if session_id in app.state.human_verified_sessions:
        return True
    if not app.state.mongo_memory:
        return not is_captcha_enabled()
    try:
        record = app.state.mongo_memory.find_one({"session_id": session_id}, {"human_verified": 1})
        return bool(record and record.get("human_verified"))
    except PyMongoError as exc:
        print(f"[WARN] Failed to check human verification: {exc}")
        return False


def mark_session_human_verified(session_id: str):
    app.state.human_verified_sessions.add(session_id)
    upsert_session_memory(session_id, {
        "human_verified": True,
    })


@app.get("/")
async def serve_root():
    return RedirectResponse(url="/captcha", status_code=302)


@app.get("/captcha")
async def serve_captcha():
    captcha_path = frontend_dir / "captcha.html"
    if captcha_path.exists():
        html = captcha_path.read_text(encoding="utf-8")
        site_key = os.getenv("TURNSTILE_SITE_KEY", "").strip()
        html = html.replace("__TURNSTILE_SITE_KEY__", site_key)
        return HTMLResponse(content=html)
    return {"message": "Captcha page not found"}


@app.get("/app")
async def serve_frontend():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found"}


@app.get("/user-details")
async def serve_user_details():
    details_path = frontend_dir / "user_details.html"
    if details_path.exists():
        return FileResponse(str(details_path))
    return {"message": "User details page not found"}


@app.get("/website-map")
async def serve_website_map():
    map_path = frontend_dir / "website_map.html"
    if map_path.exists():
        return FileResponse(str(map_path))
    return {"message": "Website map page not found"}


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "document_loaded": app.state.vector_store is not None,
        "annotations_count": len(app.state.annotations),
        "chat_count": len(app.state.chat_history),
        "filename": app.state.doc_filename,
        "mongodb_enabled": app.state.mongo_memory is not None,
        "captcha_enabled": is_captcha_enabled(),
    }


# ── Models ─────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class AnnotationRequest(BaseModel):
    text: str


class UserDetailsRequest(BaseModel):
    email: str
    phone: str
    session_id: Optional[str] = None


class CaptchaVerifyRequest(BaseModel):
    captcha_token: Optional[str] = ""
    session_id: Optional[str] = None


class EndChatRequest(BaseModel):
    session_id: str


# ── Build LangGraph ────────────────────────────────────────────────────────
graph = build_agent_graph()


@app.post("/captcha/verify")
async def verify_captcha(request: CaptchaVerifyRequest, raw_request: Request):
    session_id = request.session_id.strip() if request.session_id else str(uuid4())
    client_ip = get_client_ip(raw_request)
    if not verify_turnstile_token(request.captcha_token or "", client_ip):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed.")
    mark_session_human_verified(session_id)
    return {"message": "CAPTCHA verified.", "session_id": session_id}


@app.post("/user-details")
async def save_user_details(request: UserDetailsRequest):
    email = request.email.strip().lower()
    phone = request.phone.strip()
    if not email or "@" not in email or not email.endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Please enter a valid Gmail address.")
    if not phone:
        raise HTTPException(status_code=400, detail="Please enter your phone number.")

    session_id = request.session_id.strip() if request.session_id else ""
    if is_captcha_enabled():
        if not session_id:
            raise HTTPException(status_code=400, detail="Session missing. Complete CAPTCHA first.")
        if not session_is_human_verified(session_id):
            raise HTTPException(status_code=400, detail="Session is not human-verified. Complete CAPTCHA first.")
    elif not session_id:
        session_id = str(uuid4())
        mark_session_human_verified(session_id)

    upsert_session_memory(session_id, {
        "user_email": email,
        "user_phone": phone,
        "chat_history": [],
        "human_verified": True,
    })
    return {"message": "User details saved.", "session_id": session_id}


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

        app.state.annotations = []
        app.state.chat_history = []
        app.state.doc_filename = file.filename

        print(f"[OK] Indexed {len(chunks)} chunks from '{file.filename}'")
    finally:
        if file_location.exists():
            os.remove(str(file_location))

    return {
        "message": f"'{file.filename}' processed successfully.",
        "chunks_indexed": len(chunks),
        "filename": file.filename,
    }


# ── Chat Endpoint ──────────────────────────────────────────────────────────
@app.post("/chat")
async def chat_with_pdf(request: QueryRequest):
    if app.state.vector_store is None:
        return {"error": "No document loaded. Please upload a PDF first."}
    if not request.query.strip():
        return {"error": "Query cannot be empty."}
    if len(request.query) > 4000:
        return {"error": "Query too long. Please keep it under 4000 characters."}
    if is_captcha_enabled():
        if not request.session_id:
            return {"error": "Session ID missing. Complete CAPTCHA and user details first."}
        if not session_is_human_verified(request.session_id):
            return {"error": "Session is not human-verified. Complete CAPTCHA first."}

    retrieved_context = app.state.vector_store.search(request.query, top_k=5)

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
        "result": "",
    }

    try:
        result_state = graph.invoke(state)
        answer = result_state.get("result", "").strip()
        if not answer:
            answer = "The model returned an empty response. Please try again."

        app.state.chat_history.append({
            "query": request.query,
            "response": answer,
            "timestamp": datetime.utcnow().strftime("%H:%M"),
        })
        if request.session_id:
            append_chat_memory(request.session_id, request.query, answer)
        return {"response": answer}
    except Exception as exc:
        print(f"[CRITICAL] Agent Workflow Error: {str(exc)}")
        return {"error": f"Agent error: {str(exc)}"}


@app.post("/chat/end")
async def end_chat(request: EndChatRequest):
    session_id = request.session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    app.state.human_verified_sessions.discard(session_id)
    if app.state.mongo_memory:
        try:
            app.state.mongo_memory.delete_one({"session_id": session_id})
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to clear temporary memory: {exc}")
    return {"message": "Temporary conversation memory cleared."}


# ── Annotations Endpoints ──────────────────────────────────────────────────
@app.post("/annotations")
async def add_annotation(req: AnnotationRequest):
    if app.state.vector_store is None:
        raise HTTPException(status_code=400, detail="Upload a document first before adding annotations.")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Annotation text cannot be empty.")

    annotation = {
        "text": req.text.strip(),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    }
    app.state.annotations.append(annotation)
    print(f"[OK] Annotation added: '{req.text[:40]}...'")
    return {"message": "Annotation saved.", "total": len(app.state.annotations), "annotation": annotation}


@app.get("/annotations")
async def get_annotations():
    return {"annotations": app.state.annotations}


@app.delete("/annotations/{index}")
async def delete_annotation(index: int):
    if index < 0 or index >= len(app.state.annotations):
        raise HTTPException(status_code=404, detail="Annotation not found.")
    removed = app.state.annotations.pop(index)
    return {"message": "Deleted.", "removed": removed}


# ── Download Report Endpoint ───────────────────────────────────────────────
@app.get("/download-report")
async def download_report():
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
        headers={"Content-Disposition": f'attachment; filename="{report_name}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
