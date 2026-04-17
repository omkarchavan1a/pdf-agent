# CONCERNS

## Security Issues
- **[RESOLVED] Hardcoded Secrets:** `HUGGINGFACEHUB_API_TOKEN` was previously hardcoded in `llm_setup.py`. This has been resolved by migrating to `.env` using `python-dotenv`.
- **User Segregation:** FastAPI currently stores its text context globally in `app.state.context`. This is vulnerable to cross-talk between multiple users making requests concurrently and is a critical state injection vulnerability in production configurations.

## Performance & State Limitations
- **Token Truncation Limit:** Currently, `agent_graph.py` forcibly truncates contextual text input to the first 3000 characters to prevent overflowing the generic LLM context limits (`state['context'][:3000]`). For massive PDFs, significant knowledge is lost.
- **RAG Implementation Missing:** Vector search is not yet effectively wired in. Queries do not semantically align with the chunked document fragments, circumventing the actual purpose of FAISS embeddings in this repo.
- **Memory Management:** The uploaded temp files are handled appropriately and deleted, ensuring no filesystem bloat. However, keeping the parsed texts in the FastAPI RAM global space might rapidly consume memory.
