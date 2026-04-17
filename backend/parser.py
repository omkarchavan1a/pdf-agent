import fitz  # PyMuPDF
from typing import List

def extract_text_from_pdf(filepath: str) -> str:
    """
    Parse text from a complex PDF file using PyMuPDF.
    """
    doc = fitz.open(filepath)
    text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text += page.get_text("text") + "\n\n"
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Simple chunking strategy for RAG.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
