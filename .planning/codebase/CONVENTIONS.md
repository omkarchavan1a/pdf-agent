# CONVENTIONS

## Python & FastAPI
- **Typing:** Type annotations (`typing.Dict`, `typing.Any`, `typing.List`) are present in utility and graph nodes but largely missing on root FastAPI routes (`main.py`).
- **Dependencies:** Uses Pydantic for validation schemas (`BaseModel`) on API inputs.

## LangGraph
- State logic revolves around the custom `TypedDict` class (`AgentState`) containing three string keys: `input_query`, `context`, `result`.
- Graph flow functions expect state dictionaries and output a dictionary reflecting changes to the state.

## Formatting & Naming
- **Functions:** `snake_case` (e.g. `summarize_node`, `extract_text_from_pdf`).
- **Variables/Filepaths:** `snake_case`. Standard python conventions applied.
- Python logic blocks feature clear docstrings explaining component responsibility.
