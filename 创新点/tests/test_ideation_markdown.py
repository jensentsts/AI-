"""Regression cases for Markdown encountered in actual research notes."""

from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "paper-innovation" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ideation_markdown import field, placeholders, section, table


class MarkdownTests(unittest.TestCase):
    def test_pipes_in_notes_do_not_shift_provenance_columns(self):
        note = r"$|P_i|$, \(\|x\|_2\), P(y|x), `state | next`, raw \| pipe"
        body = "\n".join((
            "| ID | Finding | Depth |",
            "| --- | --- | --- |",
            f"| W1 | {note} | full-text |",
        ))

        headers, rows = table(body)

        self.assertEqual(headers, ["ID", "Finding", "Depth"])
        self.assertEqual(rows, [["W1", note.replace(r"raw \|", "raw |"), "full-text"]])

    def test_anchors_survive_translated_headings_and_labels(self):
        body = "\n".join((
            "## 研究判据",
            "<!-- section:rules -->",
            "- **保留规则**： <!-- field:advance -->",
            "- **Advance**: untrusted label elsewhere",
            "## End of section",
        ))

        selected = section(body, "rules", "Preregistered criteria")

        self.assertNotIn("End of section", selected)
        self.assertEqual(field(selected, "advance", "Advance"), "")

    def test_ordinary_chinese_annotations_are_accepted(self):
        self.assertEqual(placeholders("【注】功率单位为 MW。"), [])
        self.assertTrue(placeholders("- **Evidence**: {{FILL:evidence}}"))


if __name__ == "__main__":
    unittest.main()
