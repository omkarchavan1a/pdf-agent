import unittest

from streamlit_chat_utils import (
    build_edited_filename,
    extract_pdf_edits_from_response,
    rebuild_pdf_edits_from_chat_history,
)


class StreamlitChatUtilsTests(unittest.TestCase):
    def test_extract_pdf_edits_from_response_returns_expected_entries(self):
        response = (
            "Done [[EDIT: Page 2 | Add title note]] "
            "and [[EDIT: Page 5 | Mark action item]]"
        )
        edits = extract_pdf_edits_from_response(response)
        self.assertEqual(
            edits,
            [
                {"page": "2", "text": "Add title note"},
                {"page": "5", "text": "Mark action item"},
            ],
        )

    def test_rebuild_pdf_edits_from_chat_history_uses_all_turns(self):
        history = [
            {"query": "q1", "response": "No edit"},
            {"query": "q2", "response": "Here [[EDIT: Page 1 | First]]"},
            {"query": "q3", "response": "Another [[EDIT: Page 3 | Third]]"},
        ]
        edits = rebuild_pdf_edits_from_chat_history(history)
        self.assertEqual(
            edits,
            [
                {"page": "1", "text": "First"},
                {"page": "3", "text": "Third"},
            ],
        )

    def test_build_edited_filename_appends_suffix_once(self):
        self.assertEqual(build_edited_filename("report.pdf"), "report_Edited.pdf")
        self.assertEqual(build_edited_filename("report_Edited.pdf"), "report_Edited.pdf")
        self.assertEqual(build_edited_filename("report"), "report_Edited.pdf")


if __name__ == "__main__":
    unittest.main()
