# ARCHITECTURE

## System Overview
The application is an AI Document Intelligence API built with **FastAPI**. It leverages **LangChain** and **LangGraph** to process PDF logic via stateful agents. The architecture is primarily stateless API-driven, managing per-request state via FastAPI application context.

## Core Flow

### 1. Document Ingestion (`POST /upload`)
- Receives a PDF file upload.
- Uses PyMuPDF inside `parser.py` to extract text.
- Stores the extracted text temporarily in the FastAPI `app.state` (Note: this is not scalable for multiple users in production).

### 2. Querying Context (`POST /chat`)
- Rejects requests if no global document context is loaded.
- Initializes the **LangGraph Agent** state:
  - `input_query`: The user statement.
  - `context`: The active document text.
  - `result`: The final answer space.
- Invokes the graph engine.

### 3. Agent Graph execution (`agent_graph.py`)
- **Router Logic:** Inspects the query to determine intent (e.g. if the word "summarize" is present).
- **Summarize Node (`summarize_node`):**
  - Sends the first 3000 characters of context to the LLM with a summarization prompt.
- **Search Node (`search_node`):**
  - Sends the query and the current context (first 3000 characters) to answer a specific factual question.
- Both nodes terminate to `END` after assigning the resultant string back to the state mapping.

## RAG & Vector Dependencies
While FAISS and `embeddings.py` are present, they are currently stubbed out/initialized but disconnected from the graph. The graph directly feeds static string subsets to the LLM. Vectorization pipelines will plug into `embeddings.py` in later iterations.
