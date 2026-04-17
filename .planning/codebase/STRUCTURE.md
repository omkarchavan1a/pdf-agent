# STRUCTURE

```text
/ (Project Root)
├── .env                  # Environment variables (HUGGINGFACEHUB_API_TOKEN)
├── .gitignore            # Git exclusion rules
├── backend/              # Core API and logical implementation
│   ├── agent_graph.py    # LangGraph state machine and node definitions
│   ├── embeddings.py     # Embedding models initialization (Mobile & Laptop configs)
│   ├── llm_setup.py      # LLM endpoint setup (Gemma, LangChain)
│   ├── main.py           # FastAPI application, routing, and server entrypoint
│   ├── parser.py         # PyMuPDF extraction and text chunking logic
│   └── requirements.txt  # Python package dependencies
└── .planning/            # Project context and codebase map
    ├── PROJECT.md        # High-level project definition
    └── codebase/         # Codebase layout & architectural logs
```
