import fitz  # PyMuPDF
from fpdf import FPDF
from typing import List, Dict, Optional
from datetime import UTC, datetime

def clean_unicode(text: str) -> str:
    """
    Sanitize text for FPDF Latin-1 encoding.
    Maps common AI-generated Unicode characters to Latin-1 equivalents.
    """
    if not isinstance(text, str):
        return str(text)
    
    # Mapping for common Unicode characters that cause FPDF to crash
    mapping = {
        "\u201c": '"', "\u201d": '"',  # Smart double quotes
        "\u2018": "'", "\u2019": "'",  # Smart single quotes
        "\u2013": "-", "\u2014": "-",  # En and Em dashes
        "\u2022": "*",                 # Bullet points
        "\u2026": "...",               # Ellipsis
        "\u2122": "(TM)",              # Trademark
        "\u00a9": "(C)",               # Copyright
        "\u00ae": "(R)",               # Registered
    }
    
    for char, replacement in mapping.items():
        text = text.replace(char, replacement)
        
    # Fallback: remove any other non-latin-1 characters
    return text.encode('latin-1', 'replace').decode('latin-1')


def normalize_overlay_text(text: str, max_len: int = 300) -> str:
    cleaned = "".join(ch for ch in str(text) if ch in ("\n", "\t") or ch >= " ")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return cleaned


def normalize_pdf_edits_for_render(pdf_edits: Optional[List[Dict]], page_count: int) -> List[Dict]:
    if not pdf_edits:
        return []

    normalized: List[Dict] = []
    seen = set()
    for edit in pdf_edits:
        try:
            page = int(edit.get("page", 1))
        except (TypeError, ValueError):
            page = 1

        if page_count > 0:
            page = max(1, min(page, page_count))
        else:
            page = max(1, page)

        text = normalize_overlay_text(edit.get("text", ""))
        if not text:
            continue

        key = (page, text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"page": page, "text": text})
    return normalized


def draw_visible_edit_overlay(page: fitz.Page, page_number: int, text: str, slot_index: int) -> None:
    x0 = 36
    y0 = 36 + (slot_index * 62)
    box_width = min(290, max(180, page.rect.width - 72))
    y1 = min(y0 + 56, page.rect.height - 36)
    if y1 <= y0 + 12:
        y0 = max(36, page.rect.height - 92)
        y1 = page.rect.height - 36

    rect = fitz.Rect(x0, y0, x0 + box_width, y1)
    page.draw_rect(rect, color=(0.0, 0.45, 0.75), fill=(0.9, 0.97, 1.0), width=0.8)
    text_rect = fitz.Rect(rect.x0 + 6, rect.y0 + 5, rect.x1 - 6, rect.y1 - 5)
    overlay_text = f"AI EDIT (Page {page_number}): {normalize_overlay_text(text)}"
    page.insert_textbox(
        text_rect,
        overlay_text,
        fontsize=8.5,
        fontname="helv",
        color=(0.0, 0.22, 0.36),
        align=fitz.TEXT_ALIGN_LEFT,
    )



class ReportPDF(FPDF):
    DOC_TITLE = "Session Intelligence Appendix"
    # Color Palette (Slate & Cyan Theme)
    C_PRIMARY   = (0, 180, 216)   # Deep Cyan
    C_DARK      = (15, 23, 42)    # Slate 900
    C_MID       = (30, 41, 59)    # Slate 800
    C_TEXT      = (51, 65, 85)    # Slate 700
    C_LIGHT     = (148, 163, 184) # Slate 400
    C_ACCENT    = (79, 70, 229)   # Indigo 600

    def header(self):
        # Draw header bar for appendix
        self.set_fill_color(*self.C_DARK)
        self.rect(0, 0, 210, 28, 'F')
        
        # Title
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.C_PRIMARY)
        self.set_y(10)
        self.set_x(12)
        self.cell(0, 10, clean_unicode(self.DOC_TITLE), align="L", border=0)
        
        # Branding
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.C_LIGHT)
        self.set_y(10)
        self.set_x(-75)
        self.cell(63, 10, clean_unicode(datetime.now(UTC).strftime("%Y-%m-%d  |  IDP-772")), align="R", border=0)
        self.ln(22)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.C_LIGHT)
        self.line(12, self.get_y(), 198, self.get_y())
        footer_text = f"AI-Generated Intelligence Summary  ·  Page {self.page_no()}"
        self.cell(0, 10, clean_unicode(footer_text), align="C")

    def section_header(self, title: str):
        self.ln(6)
        self.set_fill_color(241, 245, 249)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.C_DARK)
        self.cell(0, 8, clean_unicode(f"  {title.upper()}"), fill=True, ln=True)
        self.set_draw_color(*self.C_PRIMARY)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 20, self.get_y())
        self.ln(4)

    def data_row(self, label: str, value: str):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.C_MID)
        self.cell(45, 8, clean_unicode(f" {label}:"), border=0)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.C_TEXT)
        remaining_width = self.w - self.get_x() - self.r_margin
        self.multi_cell(remaining_width, 8, clean_unicode(str(value)), border=0)
        self.ln(1)

def generate_pdf_report(
    filename: str,
    annotations: List[Dict],
    chat_history: List[Dict],
    original_pdf_bytes: Optional[bytes] = None,
    pdf_edits: Optional[List[Dict]] = None
) -> bytes:
    """
    Build a PDF summary and optionally merge it with the original PDF.
    Now also applies direct edits (Text Annotations) to the original pages.
    """
    # 1. Generate the Summary (Appendix) pages
    pdf = ReportPDF()
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    pdf.section_header("Analysis Metadata")
    pdf.data_row("Source File", filename)
    pdf.data_row("Process Date", datetime.now(UTC).strftime("%B %d, %Y"))
    pdf.data_row("Note count", str(len(annotations)))
    pdf.data_row("Query count", str(len(chat_history)))
    pdf.data_row("Direct Edits", str(len(pdf_edits) if pdf_edits else 0))
    pdf.ln(4)

    if annotations:
        pdf.section_header("AI Context & Annotations")
        for i, ann in enumerate(annotations, 1):
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*pdf.C_ACCENT)
            pdf.cell(0, 6, clean_unicode(f"ANNOTATION #{i} [{ann.get('timestamp', 'N/A')}]"), ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*pdf.C_TEXT)
            pdf.set_fill_color(252, 252, 255)
            pdf.multi_cell(0, 6, clean_unicode(ann["text"]), border='L', fill=True)
            pdf.ln(2)

    if chat_history:
        pdf.add_page()
        pdf.section_header("Intelligence Queries (Chat Log)")
        for i, item in enumerate(chat_history, 1):
            pdf.set_fill_color(241, 245, 249)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*pdf.C_DARK)
            pdf.multi_cell(0, 8, clean_unicode(f"QUERY {i}: {item['query']}"), fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*pdf.C_TEXT)
            pdf.ln(1)
            pdf.multi_cell(0, 6, clean_unicode(item["response"]))
            pdf.ln(4)

    if pdf_edits:
        pdf.add_page()
        pdf.section_header("Applied Direct Edits")
        for i, edit in enumerate(pdf_edits, 1):
            page_number = edit.get("page", 1)
            text = normalize_overlay_text(edit.get("text", ""))
            if not text:
                continue
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*pdf.C_MID)
            pdf.cell(0, 7, clean_unicode(f"EDIT #{i} - Page {page_number}"), ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*pdf.C_TEXT)
            pdf.multi_cell(0, 6, clean_unicode(text))
            pdf.ln(2)

    summary_bytes = pdf.output()

    # 2. Process Original PDF (Apply Edits & Merge Appendix)
    if original_pdf_bytes:
        try:
            doc_orig = fitz.open(stream=original_pdf_bytes, filetype="pdf")
            normalized_edits = normalize_pdf_edits_for_render(pdf_edits, len(doc_orig))
            
            # Apply visible direct edits on target pages.
            if normalized_edits:
                slot_counters: Dict[int, int] = {}
                for edit in normalized_edits:
                    page_idx = int(edit.get("page", 1)) - 1
                    if 0 <= page_idx < len(doc_orig):
                        slot = slot_counters.get(page_idx, 0)
                        draw_visible_edit_overlay(
                            doc_orig[page_idx],
                            page_idx + 1,
                            str(edit["text"]),
                            slot,
                        )
                        slot_counters[page_idx] = slot + 1
            
            doc_summary = fitz.open(stream=summary_bytes, filetype="pdf")
            doc_orig.insert_pdf(doc_summary)
            merged_bytes = doc_orig.tobytes()
            
            doc_orig.close()
            doc_summary.close()
            return merged_bytes
        except Exception as e:
            print(f"PDF Processing/Merge error: {e}")
            return summary_bytes
    
    return summary_bytes
