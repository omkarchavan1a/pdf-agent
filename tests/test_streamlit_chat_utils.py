import unittest

from streamlit_chat_utils import (
    DEFAULT_MAX_EDIT_TEXT_LEN,
    build_edited_filename,
    extract_pdf_edits_from_response,
    normalize_pdf_edits,
    parse_direct_edit_command,
    rebuild_pdf_edits_from_chat_history,
)


class StreamlitChatUtilsTests(unittest.TestCase):
    def test_extract_pdf_edits_from_response_returns_expected_entries(self):
        response = (
            "Done [[edit: Page 2 | Add   title note]] "
            "and [[EDIT: Page 5 | Mark\n action   item]]"
        )
        edits = extract_pdf_edits_from_response(response)
        self.assertEqual(
            edits,
            [
                {"page": 2, "text": "Add title note"},
                {"page": 5, "text": "Mark action item"},
            ],
        )

    def test_rebuild_pdf_edits_from_chat_history_uses_all_turns_and_clamps(self):
        history = [
            {"query": "q1", "response": "No edit"},
            {"query": "q2", "response": "Here [[EDIT: Page 1 | First]]"},
            {"query": "q3", "response": "Another [[EDIT: Page 30 | Third]]"},
            {"query": "q4", "response": "Dup [[EDIT: Page 3 | Third]]"},
        ]
        edits = rebuild_pdf_edits_from_chat_history(history, page_count=5)
        self.assertEqual(
            edits,
            [
                {"page": 1, "text": "First"},
                {"page": 5, "text": "Third"},
                {"page": 3, "text": "Third"},
            ],
        )

    def test_parse_direct_edit_command_parses_valid_input(self):
        parsed = parse_direct_edit_command("/edit page=4 text=  Add callout here  ")
        self.assertEqual(parsed, {"page": 4, "text": "Add callout here"})

    def test_parse_direct_edit_command_rejects_invalid_input(self):
        self.assertIsNone(parse_direct_edit_command("/edit text=missing-page"))
        self.assertIsNone(parse_direct_edit_command("hello"))

    def test_normalize_pdf_edits_limits_text_length(self):
        long_text = "x" * (DEFAULT_MAX_EDIT_TEXT_LEN + 50)
        normalized = normalize_pdf_edits(
            [{"page": 1, "text": long_text}],
            page_count=1,
            max_text_len=DEFAULT_MAX_EDIT_TEXT_LEN,
        )
        self.assertEqual(len(normalized[0]["text"]), DEFAULT_MAX_EDIT_TEXT_LEN)

    def test_build_edited_filename_appends_suffix_once(self):
        self.assertEqual(build_edited_filename("report.pdf"), "report_Edited.pdf")
        self.assertEqual(build_edited_filename("report_Edited.pdf"), "report_Edited.pdf")
        self.assertEqual(build_edited_filename("report"), "report_Edited.pdf")


if __name__ == "__main__":
    unittest.main()
