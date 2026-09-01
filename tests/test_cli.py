"""The command line, driven the way a user and a CI job drive it."""

import contextlib
import io
import json
import os
import tempfile
import unittest

# ``tacz_validator.cli`` re-exports main() as a function, so the module has
# to be imported by its full path to get at it.
from tacz_validator.cli.main import main as cli_main

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BROKEN = os.path.join(DATA, "broken_pack")
VALID = os.path.join(DATA, "valid_pack")


def run(*argv):
    """Run the CLI, returning (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main(["--no-progress"] + list(argv))
    return code, out.getvalue(), err.getvalue()


class ExitCodeTests(unittest.TestCase):
    def test_a_clean_pack_exits_zero(self):
        code, _, _ = run(VALID)
        self.assertEqual(code, 0)

    def test_errors_exit_one_so_ci_fails(self):
        code, _, _ = run(BROKEN)
        self.assertEqual(code, 1)

    def test_a_missing_pack_exits_two_and_says_so_on_stderr(self):
        code, _, err = run(os.path.join(DATA, "no_such_pack"))
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_filtering_the_errors_away_exits_zero(self):
        """Suppressing a finding has to move the gate, or --ignore is a lie."""
        code, _, _ = run(BROKEN, "--severity", "error", "--ignore-category", "reference",
                         "--ignore-category", "schema", "--ignore-category", "json",
                         "--ignore-category", "naming")
        self.assertEqual(code, 0)


class OutputTests(unittest.TestCase):
    def output(self, suffix):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        self.addCleanup(os.unlink, path)
        return path

    def test_text_is_the_default_and_names_the_findings(self):
        _, out, _ = run(BROKEN, "--lang", "en")
        self.assertIn("REF001", out)
        self.assertIn("Reference", out)

    def test_quiet_prints_the_summary_line_only(self):
        _, out, _ = run(BROKEN, "--quiet", "--lang", "en")
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertIn("errors", out)

    def test_json_goes_to_stdout_when_no_output_file_is_given(self):
        _, out, _ = run(BROKEN, "--format", "json")
        payload = json.loads(out)
        self.assertIn("findings", payload)

    def test_an_output_file_is_written_and_reported(self):
        path = self.output(".csv")
        _, out, _ = run(BROKEN, "--format", "csv", "-o", path)
        self.assertIn(path, out)
        with open(path, encoding="utf-8-sig") as handle:
            self.assertIn("Category", handle.readline())

    def test_a_category_filter_reaches_the_written_file(self):
        path = self.output(".json")
        run(BROKEN, "--format", "json", "--category", "naming", "-o", path)
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertTrue(payload["findings"])
        self.assertEqual({f["category"] for f in payload["findings"]}, {"naming"})


class ListingTests(unittest.TestCase):
    def test_checks_are_listed_without_a_pack(self):
        code, out, _ = run("--list-checks")
        self.assertEqual(code, 0)
        self.assertIn("lua-script", out)

    def test_categories_are_listed_with_their_code_prefix(self):
        code, out, _ = run("--list-categories")
        self.assertEqual(code, 0)
        self.assertIn("reference", out)
        self.assertIn("REF", out)
        self.assertIn("LUA", out)

    def test_a_pack_is_required_for_anything_else(self):
        with self.assertRaises(SystemExit):
            run()


class OptionTests(unittest.TestCase):
    def test_disabling_a_check_removes_its_findings(self):
        _, before, _ = run(BROKEN, "--lang", "en")
        _, after, _ = run(BROKEN, "--lang", "en", "--disable", "localization")
        self.assertIn("LANG001", before)
        self.assertNotIn("LANG001", after)

    def test_ignoring_a_code_removes_only_that_code(self):
        _, out, _ = run(BROKEN, "--lang", "en", "--ignore", "REF001")
        self.assertNotIn("REF001", out)
        self.assertIn("REF002", out)

    def test_an_unknown_category_is_rejected_by_the_parser(self):
        with self.assertRaises(SystemExit):
            run(BROKEN, "--category", "not-a-category")

    def test_japanese_output_is_selectable(self):
        _, out, _ = run(BROKEN, "--lang", "ja")
        self.assertIn("エラー", out)


if __name__ == "__main__":
    unittest.main()
