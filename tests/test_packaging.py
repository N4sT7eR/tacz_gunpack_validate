"""The Windows version resource, which is how a built EXE identifies itself."""

import ast
import contextlib
import re
import importlib.util
import io as _io
import os
import tempfile
import unittest

import tacz_validator as tv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packaging", "make_version_file.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "build-windows.yml")
INIT = os.path.join(ROOT, "src", "tacz_validator", "__init__.py")


def load_script():
    spec = importlib.util.spec_from_file_location("make_version_file", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.path.isfile(SCRIPT), "packaging/ is not shipped on main")
class NumericVersionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script()

    def test_three_parts_are_padded_to_the_four_windows_wants(self):
        self.assertEqual(self.module.numeric_version("0.11.0"), (0, 11, 0, 0))

    def test_four_parts_are_kept(self):
        self.assertEqual(self.module.numeric_version("1.2.3.4"), (1, 2, 3, 4))

    def test_a_pre_release_suffix_is_dropped_not_folded_in(self):
        # (1, 0, 2, 0) would make the candidate outrank the release it precedes.
        self.assertEqual(self.module.numeric_version("1.0.0rc2"), (1, 0, 0, 0))
        self.assertEqual(self.module.numeric_version("2.1.3b1"), (2, 1, 3, 0))

    def test_an_empty_part_becomes_zero_rather_than_failing_the_build(self):
        self.assertEqual(self.module.numeric_version("1..3"), (1, 0, 3, 0))


@unittest.skipUnless(os.path.isfile(SCRIPT), "packaging/ is not shipped on main")
class GeneratedResourceTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        handle, self.path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        self.addCleanup(os.unlink, self.path)

    def generate(self, name="TaCZValidator-v9.9.9"):
        # The script reports what it wrote; that belongs in a build log, not in
        # the middle of the test output.
        with contextlib.redirect_stdout(_io.StringIO()):
            code = self.module.main(["make_version_file.py", name, "A description", self.path])
        self.assertEqual(code, 0)
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def test_the_version_comes_from_the_package_so_it_cannot_drift(self):
        text = self.generate()
        self.assertIn(repr(tv.__version__), text)

    def test_the_executable_name_reaches_the_fields_windows_shows(self):
        text = self.generate("TaCZValidator-cli-v9.9.9")
        self.assertIn(repr("TaCZValidator-cli-v9.9.9"), text)
        self.assertIn(repr("TaCZValidator-cli-v9.9.9.exe"), text)

    def test_the_output_is_a_python_literal_pyinstaller_can_evaluate(self):
        # PyInstaller exec()s this file; a syntax error here fails the build
        # late and cryptically, so it is worth catching in the test suite.
        ast.parse(self.generate())

    def test_wrong_arguments_are_refused_rather_than_writing_a_broken_file(self):
        with contextlib.redirect_stderr(_io.StringIO()):
            self.assertEqual(self.module.main(["make_version_file.py", "only-one"]), 2)


@unittest.skipUnless(os.path.isfile(WORKFLOW), "the workflow is not shipped here")
class DevelopmentStampTests(unittest.TestCase):
    """The pattern the Windows build uses to mark a non-release build.

    It runs only on a Windows runner, where git checks the tree out with CRLF
    endings, so a pattern that works on a developer's LF copy can still match
    nothing there -- which is how it shipped broken the first time. Both endings
    are checked here rather than one round trip later.
    """

    def setUp(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            workflow = handle.read()
        found = re.search(r"-replace '([^']+)', '([^']+)'", workflow)
        if found is None:
            self.fail(
                "no -replace step found in build-windows.yml; if the marking "
                "step was rewritten, update this test to match"
            )
        self.pattern, self.replacement = found.group(1), found.group(2)
        with open(INIT, encoding="utf-8") as handle:
            self.source = handle.read()

    def as_python(self):
        """.NET and Python agree on this pattern apart from the group syntax."""
        return re.compile(self.pattern), self.replacement.replace("$1", r"\1")

    def test_the_pattern_matches_however_the_tree_was_checked_out(self):
        pattern, replacement = self.as_python()
        for name, text in (
            ("LF", self.source.replace("\r\n", "\n")),
            ("CRLF", self.source.replace("\r\n", "\n").replace("\n", "\r\n")),
        ):
            marked = pattern.sub(replacement, text)
            self.assertNotEqual(marked, text, "{}: nothing was marked".format(name))
            self.assertIn('__version__ = "{}-dev"'.format(tv.__version__), marked, name)

    def test_marking_leaves_the_file_importable(self):
        pattern, replacement = self.as_python()
        marked = pattern.sub(replacement, self.source)
        ast.parse(marked)

    def test_the_marked_version_still_yields_four_integers_for_windows(self):
        module = load_script()
        self.assertEqual(
            module.numeric_version(tv.__version__ + "-dev"),
            module.numeric_version(tv.__version__),
        )


if __name__ == "__main__":
    unittest.main()
