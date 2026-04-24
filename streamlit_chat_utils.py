import os
import re
from typing import Dict, List, Optional, Tuple


DEFAULT_MAX_EDIT_TEXT_LEN = 500
EDIT_PATTERN = re.compile(
    r"\[\[\s*edit\s*:\s*page\s*(\d+)\s*\|\s*(.*?)\s*\]\]",
    re.IGNORECASE | re.DOTALL,
)
EDIT_COMMAND_PATTERN = re.compile(
    r"^\s*/edit\s+page\s*=\s*(\d+)\s+text\s*=\s*(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def strip_control_chars(text: str) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text if ch in ("\n", "\t") or ch >= " ")


def normalize_whitespace(text: str) -> str:
    cleaned = strip_control_chars(text)
    cleaned = cleaned.replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def normalize_edit_text(text: str, max_text_len: int = DEFAULT_MAX_EDIT_TEXT_LEN) -> str:
    normalized = normalize_whitespace(text).replace("\n", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) > max_text_len:
        normalized = normalized[:max_text_len].rstrip()
    return normalized


def clamp_page(page: int, page_count: int) -> int:
    if page_count <= 0:
        return max(1, page)
    return max(1, min(page, page_count))


def extract_pdf_edits_from_response(
    response_text: str,
    max_text_len: int = DEFAULT_MAX_EDIT_TEXT_LEN,
) -> List[Dict[str, int | str]]:
    if not response_text:
        return []
    matches = EDIT_PATTERN.findall(response_text)
    edits: List[Dict[str, int | str]] = []
    for page, content in matches:
        text = normalize_edit_text(content, max_text_len=max_text_len)
        if not text:
            continue
        edits.append({"page": int(page), "text": text})
    return edits


def parse_direct_edit_command(
    prompt_text: str,
    max_text_len: int = DEFAULT_MAX_EDIT_TEXT_LEN,
) -> Optional[Dict[str, int | str]]:
    if not prompt_text:
        return None
    match = EDIT_COMMAND_PATTERN.match(prompt_text)
    if not match:
        return None
    page = int(match.group(1))
    text = normalize_edit_text(match.group(2), max_text_len=max_text_len)
    if not text:
        return None
    return {"page": page, "text": text}


def normalize_pdf_edits(
    edits: List[Dict[str, int | str]],
    page_count: int,
    max_text_len: int = DEFAULT_MAX_EDIT_TEXT_LEN,
) -> List[Dict[str, int | str]]:
    normalized: List[Dict[str, int | str]] = []
    seen: set[Tuple[int, str]] = set()

    for edit in edits:
        try:
            raw_page = int(edit.get("page", 1))
        except (TypeError, ValueError):
            raw_page = 1
        page = clamp_page(raw_page, page_count)
        text = normalize_edit_text(str(edit.get("text", "")), max_text_len=max_text_len)
        if not text:
            continue
        key = (page, text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"page": page, "text": text})
    return normalized


def rebuild_pdf_edits_from_chat_history(
    chat_history: List[Dict[str, str]],
    page_count: int = 0,
    max_text_len: int = DEFAULT_MAX_EDIT_TEXT_LEN,
) -> List[Dict[str, int | str]]:
    edits: List[Dict[str, int | str]] = []
    for turn in chat_history:
        edits.extend(
            extract_pdf_edits_from_response(
                turn.get("response", ""),
                max_text_len=max_text_len,
            )
        )
    return normalize_pdf_edits(edits, page_count=page_count, max_text_len=max_text_len)


def build_edited_filename(filename: str) -> str:
    original = (filename or "document.pdf").strip()
    stem, ext = os.path.splitext(original)
    if not ext:
        ext = ".pdf"
    if not stem.endswith("_Edited"):
        stem = f"{stem}_Edited"
    return f"{stem}{ext}"
