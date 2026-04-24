import unittest

import fitz

from backend.report_generator import generate_pdf_report


def build_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample document content")
    data = doc.tobytes()
    doc.close()
    return data


class ReportGeneratorTests(unittest.TestCase):
    def test_generate_pdf_report_renders_visible_edit_and_appendix(self):
        original_pdf = build_sample_pdf_bytes()
        output = generate_pdf_report(
            filename="sample.pdf",
            annotations=[],
            chat_history=[{"query": "q", "response": "r", "timestamp": "12:00"}],
            original_pdf_bytes=original_pdf,
            pdf_edits=[{"page": 1, "text": "Add visible callout"}],
        )

        doc = fitz.open(stream=output, filetype="pdf")
        combined_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        self.assertIn("AI EDIT (Page 1)", combined_text)
        self.assertIn("APPLIED DIRECT EDITS", combined_text)
        self.assertIn("Add visible callout", combined_text)


if __name__ == "__main__":
    unittest.main()
