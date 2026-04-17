import fitz  # PyMuPDF
from fpdf import FPDF
from typing import List, Dict, Optional
from datetime import datetime
import io
import re

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
        self.cell(63, 10, clean_unicode(datetime.utcnow().strftime("%Y-%m-%d  |  IDP-772")), align="R", border=0)
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
    original_pdf_bytes: Optional[bytes] = None
) -> bytes:
    """
    Build a PDF summary and optionally merge it with the original PDF.
    """
    # 1. Generate the Summary (Appendix) pages
    pdf = ReportPDF()
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    pdf.section_header("Analysis Metadata")
    pdf.data_row("Source File", filename)
    pdf.data_row("Process Date", datetime.utcnow().strftime("%B %d, %Y"))
    pdf.data_row("Note count", str(len(annotations)))
    pdf.data_row("Query count", str(len(chat_history)))
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

    summary_bytes = pdf.output()

    # 2. Merge with Original PDF if available
    if original_pdf_bytes:
        try:
            doc_orig = fitz.open(stream=original_pdf_bytes, filetype="pdf")
            doc_summary = fitz.open(stream=summary_bytes, filetype="pdf")
            
            doc_orig.insert_pdf(doc_summary)
            merged_bytes = doc_orig.tobytes()
            
            doc_orig.close()
            doc_summary.close()
            return merged_bytes
        except Exception as e:
            # Fallback to just returning original or summary if merge fails (though it shouldn't)
            print(f"Merge error: {e}")
            return summary_bytes
    
    return summary_bytes
