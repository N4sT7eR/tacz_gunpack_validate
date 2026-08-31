"""End-to-end runs against the fixture packs in tests/data."""

import os
import shutil
import tempfile
import unittest
import zipfile

import tacz_validator as tv
from tacz_validator.core.result import Severity
from tacz_validator.core.source import PackSourceError, open_source

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VALID = os.path.join(DATA, "valid_pack")
BROKEN = os.path.join(DATA, "broken_pack")


def codes(report, severity=None):
    return sorted(
        {r.code for r in report.results if severity is None or r.severity is severity}
    )


class ValidPackTests(unittest.TestCase):
    def test_a_correct_pack_reports_nothing(self):
        report = tv.validate(VALID)
        self.assertEqual(
            (report.errors, report.warnings, report.infos),
            (0, 0, 0),
            "unexpected findings: {}".format([r.text() for r in report.results]),
        )

    def test_scans_every_file(self):
        report = tv.validate(VALID)
        self.assertGreater(report.scanned_files, 10)


class BrokenPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tv.validate(BROKEN)

    def test_finds_each_planted_defect(self):
        for code in ("JSON001", "ID004", "REF001", "REF002", "ENTRY004"):
            self.assertIn(code, codes(self.report), code)

    def test_json_syntax_error_carries_a_position(self):
        finding = next(r for r in self.report.results if r.code == "JSON001")
        self.assertTrue(finding.file.endswith("broken_json.json"))
        self.assertIsNotNone(finding.line)

    def test_typo_in_an_enum_suggests_the_real_value(self):
        finding = next(
            r for r in self.report.results if r.code == "ENTRY004" and "rifel" in r.text()
        )
        self.assertIn("rifle", finding.suggestion_text())

    def test_case_mismatch_names_the_file_on_disk(self):
        finding = next(r for r in self.report.results if r.code == "REF002")
        self.assertIn("Ranged", finding.text())

    def test_out_of_range_rpm_is_a_warning_not_an_error(self):
        finding = next(r for r in self.report.results if r.code == "ENTRY005")
        self.assertIs(finding.severity, Severity.WARNING)

    def test_findings_are_translated(self):
        finding = next(r for r in self.report.results if r.code == "REF001")
        self.assertNotEqual(finding.text("en"), finding.text("ja"))


class SettingsTests(unittest.TestCase):
    def test_ignored_codes_are_filtered_out(self):
        report = tv.validate(BROKEN)
        kept = report.filtered(ignored_codes=["JSON001"])
        self.assertNotIn("JSON001", {r.code for r in kept})

    def test_disabling_a_check_skips_it(self):
        settings = tv.ValidatorSettings(disabled_validators={"json-syntax"})
        report = tv.validate(BROKEN, settings)
        self.assertNotIn("JSON001", codes(report))

    def test_minimum_severity(self):
        report = tv.validate(BROKEN)
        kept = report.filtered(minimum=Severity.ERROR)
        self.assertTrue(all(r.severity is Severity.ERROR for r in kept))


class ZipSourceTests(unittest.TestCase):
    def zip_of(self, folder, nested=False):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        archive = os.path.join(directory, "pack.zip")
        prefix = "MyPack-1.0/" if nested else ""
        with zipfile.ZipFile(archive, "w") as handle:
            for root, _, files in os.walk(folder):
                for name in files:
                    full = os.path.join(root, name)
                    handle.write(full, prefix + os.path.relpath(full, folder).replace(os.sep, "/"))
        return archive

    def test_zip_and_folder_agree(self):
        from_folder = tv.validate(BROKEN)
        from_zip = tv.validate(self.zip_of(BROKEN))
        self.assertEqual(codes(from_folder), codes(from_zip))

    def test_pack_nested_one_level_inside_the_archive(self):
        report = tv.validate(self.zip_of(VALID, nested=True))
        self.assertEqual(report.errors, 0)
        self.assertGreater(report.scanned_files, 10)

    def test_a_non_zip_file_is_rejected_clearly(self):
        handle, path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        with self.assertRaises(PackSourceError):
            open_source(path)


if __name__ == "__main__":
    unittest.main()
