import os
import re
from typing import Dict, List


EDIT_PATTERN = re.compile(r"\[\[EDIT:\s*Page\s*(\d+)\s*\|\s*(.*?)\]\]")


def extract_pdf_edits_from_response(response_text: str) -> List[Dict[str, str]]:
    if not response_text:
        return []
    matches = EDIT_PATTERN.findall(response_text)
    return [{"page": page, "text": content.strip()} for page, content in matches]


def rebuild_pdf_edits_from_chat_history(chat_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    edits: List[Dict[str, str]] = []
    for turn in chat_history:
        edits.extend(extract_pdf_edits_from_response(turn.get("response", "")))
    return edits


def build_edited_filename(filename: str) -> str:
    original = (filename or "document.pdf").strip()
    stem, ext = os.path.splitext(original)
    if not ext:
        ext = ".pdf"
    if not stem.endswith("_Edited"):
        stem = f"{stem}_Edited"
    return f"{stem}{ext}"
