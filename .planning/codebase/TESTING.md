# TESTING

## Current Testing State
- **Unit Tests**: No formal unit test suite (`pytest` or `unittest`) is currently configured in the repository.
- **Manual Testing**: Development testing is primarily done by running the Streamlit app locally (`streamlit run streamlit_app.py`) and manually verifying the PDF upload, parsing, and chat functionalities.

## Quality Assurance Areas
- **PDF Upload and Validation**: Needs tests for various edge cases (large files, corrupted signatures, non-PDF files).
- **Text Extraction (PyMuPDF)**: Needs validation against PDFs with complex layouts or scanned images to ensure robust degradation or warnings.
- **Vector Store**: Should be tested with and without `SentenceTransformer`/`FAISS` to ensure the deterministic fallback works correctly.
- **LLM and LangGraph**: Needs mocking of the HuggingFaceEndpoint to verify the state machine behavior and prompt generation without incurring API calls.
- **PDF Merging (FPDF + PyMuPDF)**: Important to verify that generated PDF reports handle Unicode correctly and correctly overlay annotations on original PDF pages.

## Recommendations
- Implement a `tests/` directory with `pytest`.
- Add fixtures for sample PDFs.
- Mock external LLM calls to test the LangGraph workflow locally.
