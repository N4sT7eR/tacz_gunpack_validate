"""Report exports -- the artefacts a user actually hands to someone else."""

import csv
import json
import os
import tempfile
import unittest

import tacz_validator as tv
from tacz_validator.reporting import render_text, write

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BROKEN = os.path.join(DATA, "broken_pack")


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tv.validate(BROKEN)

    def output(self, suffix):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        self.addCleanup(os.unlink, path)
        return path

    def test_csv_has_one_row_per_finding_and_an_excel_friendly_bom(self):
        path = self.output(".csv")
        write(self.report, path, "csv", "ja")
        with open(path, "rb") as handle:
            self.assertTrue(handle.read(3) == b"\xef\xbb\xbf")
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), len(self.report.results) + 1)
        self.assertEqual(rows[0][0], "重要度")

    def test_csv_carries_line_message_and_suggestion(self):
        path = self.output(".csv")
        write(self.report, path, "csv", "en")
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        enum_row = next(r for r in rows if r["Code"] == "ENTRY004" and "rifel" in r["Message"])
        self.assertTrue(enum_row["Line"])
        self.assertIn("rifle", enum_row["Suggested fix"])

    def test_markdown_is_a_table_with_a_summary(self):
        path = self.output(".md")
        write(self.report, path, "md", "ja")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("## サマリー", text)
        self.assertIn("| ERROR |", text)

    def test_json_export_round_trips(self):
        path = self.output(".json")
        write(self.report, path, "json", "en")
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["summary"]["errors"], self.report.errors)
        self.assertEqual(len(payload["findings"]), len(self.report.results))

    def test_text_report_mentions_every_severity_count(self):
        text = render_text(self.report, "en", colour=False)
        self.assertIn("errors", text)
        self.assertIn("ERROR", text)


if __name__ == "__main__":
    unittest.main()
