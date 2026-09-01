"""The Windows version resource, which is how a built EXE identifies itself."""

import ast
import contextlib
import importlib.util
import io as _io
import os
import tempfile
import unittest

import tacz_validator as tv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packaging", "make_version_file.py")


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


if __name__ == "__main__":
    unittest.main()
