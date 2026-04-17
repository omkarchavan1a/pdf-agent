# AI Document Intelligence Agent

## Problem/Opportunity
The current goal is to build a "Flagship" AI Document Intelligence Agent that leverages Retrieval-Augmented Generation (RAG) for semantic search and summarization on document data (PDFs). The project currently utilizes local processing and specific models (`all-MiniLM-L6-v2`, `EmbeddingGemma-300M`, `gemma-4-31B-it`) keeping logic private and fast.

## Scope
- Integrate a FastAPI server for document uploads and LLM chats.
- Maintain context of uploaded PDF files.
- Enable basic querying and summarization utilizing a state-machine via LangGraph.
- Ensure credentials and tokens (Hugging Face API) are kept secure using environment files.

## Out of Scope
- Frontend GUI (to be addressed separately if needed, per active documents in separate workspaces).
- Advanced production multi-user state isolation (FastAPI uses global `app.state` stub).

## Timeline / Phases
- [x] Pre-reqs: Codebase mapping, dependency review, and token security hardening.
- [ ] Phase 1: FAISS Vector store integration with `embeddings.py` correctly wiring into `agent_graph.py`.
- [ ] Phase 2: Resolving the 3000-character max truncation pipeline inside LangGraph execution by properly utilizing the parsed overlapping text fragments from `parser.py`.
- [ ] Phase 3: User isolation in the backend to ensure safe multi-tenant operation.
