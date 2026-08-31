"""Finding categories -- which body of rules a code belongs to."""

import csv
import json
import os
import tempfile
import unittest

import tacz_validator as tv
from tacz_validator.core.result import Category, Code, Severity, category_of, code_prefix
from tacz_validator.core.i18n import supported_locales
from tacz_validator.reporting import render_text, write

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BROKEN = os.path.join(DATA, "broken_pack")


def _declared_codes():
    return [
        value
        for name, value in vars(Code).items()
        if not name.startswith("_") and isinstance(value, str)
    ]


class CategoryMappingTests(unittest.TestCase):
    def test_every_declared_code_has_a_category(self):
        """A new code prefix must be registered, not silently become "other".

        This is the guard rail for the whole feature: the category is derived
        from the prefix, so an unregistered prefix would quietly file findings
        under "Other" instead of failing loudly here.
        """
        unmapped = [c for c in _declared_codes() if category_of(c) is Category.UNKNOWN]
        self.assertEqual(unmapped, [], "codes without a category: {}".format(unmapped))

    def test_declared_codes_are_not_empty(self):
        # Guards the test above from passing because it found nothing to check.
        self.assertGreater(len(_declared_codes()), 20)

    def test_prefix_is_the_leading_letters(self):
        self.assertEqual(code_prefix("REF001"), "REF")
        self.assertEqual(code_prefix("JSON002"), "JSON")
        self.assertEqual(code_prefix(""), "")

    def test_unregistered_prefix_falls_back_to_unknown(self):
        self.assertIs(category_of("NOPE001"), Category.UNKNOWN)

    def test_known_prefixes_land_where_expected(self):
        self.assertIs(category_of("JSON001"), Category.JSON)
        self.assertIs(category_of("LUA001"), Category.LUA)
        self.assertIs(category_of("PACK001"), Category.STRUCTURE)
        self.assertIs(category_of("ID004"), Category.NAMING)
        self.assertIs(category_of("ENTRY003"), Category.SCHEMA)
        self.assertIs(category_of("REF001"), Category.REFERENCE)
        self.assertIs(category_of("LANG001"), Category.LOCALIZATION)
        self.assertIs(category_of("ASSET001"), Category.CONVENTION)

    def test_from_name_round_trips_and_rejects_junk(self):
        for category in Category:
            self.assertIs(Category.from_name(category.value), category)
        with self.assertRaises(ValueError):
            Category.from_name("not-a-category")

    def test_every_category_is_translated_in_every_locale(self):
        for locale in supported_locales():
            for category in Category:
                label = category.label(locale)
                self.assertTrue(label)
                # An untranslated key renders as "category.x(...)".
                self.assertNotIn(category.label_key, label)


class CategoryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tv.validate(BROKEN)

    def test_the_broken_pack_produces_more_than_one_category(self):
        self.assertGreater(len(self.report.counts_by_category()), 1)

    def test_allow_list_keeps_only_that_category(self):
        kept = self.report.filtered(categories=[Category.JSON])
        self.assertTrue(kept)
        self.assertEqual({r.category for r in kept}, {Category.JSON})

    def test_ignore_list_drops_that_category(self):
        kept = self.report.filtered(ignored_categories=[Category.JSON])
        self.assertNotIn(Category.JSON, {r.category for r in kept})

    def test_allow_and_ignore_intersect_rather_than_one_winning(self):
        kept = self.report.filtered(
            categories=[Category.JSON], ignored_categories=[Category.JSON]
        )
        self.assertEqual(kept, [])

    def test_no_category_argument_keeps_everything(self):
        self.assertEqual(len(self.report.filtered()), len(self.report.results))

    def test_category_filter_composes_with_severity(self):
        kept = self.report.filtered(minimum=Severity.ERROR, categories=[Category.JSON])
        self.assertTrue(all(r.severity is Severity.ERROR for r in kept))
        self.assertTrue(all(r.category is Category.JSON for r in kept))

    def test_counts_by_category_only_lists_categories_that_occurred(self):
        counts = self.report.counts_by_category()
        self.assertTrue(all(n > 0 for n in counts.values()))
        self.assertEqual(sum(counts.values()), len(self.report.results))


class CategoryReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tv.validate(BROKEN)

    def output(self, suffix):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        self.addCleanup(os.unlink, path)
        return path

    def test_csv_carries_a_category_column_readable_by_header_name(self):
        path = self.output(".csv")
        write(self.report, path, "csv", "ja")
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertIn("分類", rows[0])
        self.assertTrue(all(row["分類"] for row in rows))

    def test_json_report_exposes_the_stable_value_not_the_label(self):
        path = self.output(".json")
        write(self.report, path, "json", "ja")
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        values = {c.value for c in Category}
        self.assertTrue(all(f["category"] in values for f in payload["findings"]))
        # by_category belongs to the summary, so like every other summary
        # number it covers the whole run, not the exported subset.
        self.assertEqual(
            sum(payload["summary"]["by_category"].values()), len(self.report.results)
        )

    def test_summary_counts_stay_whole_run_when_the_view_is_filtered(self):
        kept = self.report.filtered(categories=[Category.JSON])
        self.assertLess(len(kept), len(self.report.results))
        path = self.output(".json")
        write(self.report, path, "json", "en", results=kept)
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(len(payload["findings"]), len(kept))
        self.assertEqual(
            sum(payload["summary"]["by_category"].values()), len(self.report.results)
        )

    def test_text_report_names_the_category_and_summarises_by_it(self):
        text = render_text(self.report, "ja", colour=False)
        self.assertIn(Category.JSON.label("ja"), text)
        # The breakdown is the last line, under the counts.
        self.assertIn("/", text.strip().splitlines()[-1])

    def test_summary_only_view_ends_on_the_counts_line(self):
        """``--quiet`` prints the last line, so nothing may follow the counts."""
        text = render_text(self.report, "ja", results=[], colour=False)
        last = text.splitlines()[-1]
        self.assertIn("エラー", last)
        self.assertNotIn(Category.JSON.label("ja"), last)

    def test_markdown_report_has_the_extra_column_in_every_row(self):
        path = self.output(".md")
        write(self.report, path, "md", "en")
        with open(path, encoding="utf-8") as handle:
            body = handle.read().split("## Findings", 1)[1]
        lines = [l for l in body.splitlines() if l.startswith("| ")]
        header = lines[0]
        self.assertIn("Category", header)
        width = header.count("|")
        self.assertTrue(all(l.count("|") == width for l in lines[1:]))

    def test_exports_honour_a_filtered_view(self):
        kept = self.report.filtered(categories=[Category.JSON])
        path = self.output(".csv")
        write(self.report, path, "csv", "en", results=kept)
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), len(kept))


if __name__ == "__main__":
    unittest.main()
