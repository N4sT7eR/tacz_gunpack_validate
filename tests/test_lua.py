"""The Lua checks, and the fixture pack that exercises one finding per file.

Skipped when luaparser is not installed, mirroring the GUI tests: the extra is
optional, so the core suite has to keep passing without it.
"""

import os
import shutil
import tempfile
import unittest

import tacz_validator as tv
from tacz_validator.core.context import ValidatorSettings
from tacz_validator.core.result import Category, Code, Severity
from tacz_validator.validators import lua_script

try:
    import luaparser  # noqa: F401

    HAVE_LUAPARSER = True
except ImportError:  # pragma: no cover - the extra is optional
    HAVE_LUAPARSER = False

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LUA_PACK = os.path.join(DATA, "lua_pack")
VALID = os.path.join(DATA, "valid_pack")


def codes_for(report, filename):
    return sorted(
        r.code for r in report.results if r.file and r.file.endswith(filename)
    )


@unittest.skipUnless(HAVE_LUAPARSER, "luaparser is not installed")
class LuaFindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tv.validate(LUA_PACK)

    def test_unparseable_script_is_an_error_with_a_position(self):
        found = [r for r in self.report.results if r.code == Code.LUA_SYNTAX]
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].file.endswith("syntax_error.lua"))
        self.assertIs(found[0].severity, Severity.ERROR)
        # A syntax error the author cannot locate is barely better than none.
        self.assertIsNotNone(found[0].line)
        self.assertIsNotNone(found[0].column)

    def test_a_syntax_error_suppresses_the_other_checks_for_that_file(self):
        # No AST means every later check would be guessing.
        self.assertEqual(codes_for(self.report, "syntax_error.lua"), [Code.LUA_SYNTAX])

    def test_undefined_global_is_a_warning_naming_the_line(self):
        found = [
            r
            for r in self.report.results
            if r.code == Code.LUA_UNDEFINED_GLOBAL and r.file.endswith("undefined_global.lua")
        ]
        self.assertEqual(len(found), 2)
        self.assertTrue(all(r.severity is Severity.WARNING for r in found))
        self.assertTrue(all(r.line for r in found))

    def test_a_typo_of_a_real_constant_suggests_the_constant(self):
        typo = next(
            r for r in self.report.results
            if r.code == Code.LUA_UNDEFINED_GLOBAL and "PLAY_ONCE_STPO" in r.text("en")
        )
        self.assertIn("PLAY_ONCE_STOP", typo.suggestion_text("en"))

    def test_a_name_that_resembles_nothing_gets_no_suggestion(self):
        plain = next(
            r for r in self.report.results
            if r.code == Code.LUA_UNDEFINED_GLOBAL and "FIRE_MODE_TRACK" in r.text("en")
        )
        self.assertEqual(plain.suggestion_text("en"), "")

    def test_libraries_outside_the_sandbox_are_errors(self):
        found = [r for r in self.report.results if r.code == Code.LUA_UNAVAILABLE_LIBRARY]
        self.assertEqual({r.text("en").split('"')[1] for r in found}, {"os", "io"})
        self.assertTrue(all(r.severity is Severity.ERROR for r in found))

    def test_a_module_that_returns_nothing_is_an_error(self):
        found = [r for r in self.report.results if r.code == Code.LUA_NO_MODULE_RETURN]
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].file.endswith("no_return.lua"))

    def test_require_into_this_pack_must_resolve(self):
        found = [r for r in self.report.results if r.code == Code.LUA_REQUIRE_UNRESOLVED]
        self.assertEqual(len(found), 1)
        self.assertIn("luapack_missing_module", found[0].text("en"))

    def test_require_into_the_mods_own_namespace_is_left_alone(self):
        # tacz_default_state_machine ships with TaCZ, not with the pack.
        self.assertNotIn("tacz_default_state_machine", str(self.report.results))

    def test_a_clean_script_produces_nothing(self):
        self.assertEqual(codes_for(self.report, "clean_state_machine.lua"), [])

    def test_server_side_scripts_are_scanned_and_can_be_clean(self):
        scanned = {r.file for r in self.report.results}
        self.assertNotIn("data/luapack/scripts/server_logic.lua", scanned)
        # Prove it was actually looked at rather than simply never found.
        self.assertIn(
            "data/luapack/scripts/server_logic.lua",
            self._script_paths(),
        )

    def test_a_script_that_is_not_utf8_is_reported_rather_than_skipped(self):
        found = [r for r in self.report.results if r.code == Code.LUA_ENCODING]
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].file.endswith("shift_jis.lua"))
        self.assertIs(found[0].severity, Severity.ERROR)

    def test_an_unreadable_script_suppresses_the_other_checks_for_that_file(self):
        self.assertEqual(codes_for(self.report, "shift_jis.lua"), [Code.LUA_ENCODING])

    def test_every_finding_lands_in_the_lua_category(self):
        lua = [r for r in self.report.results if r.code.startswith("LUA")]
        self.assertTrue(lua)
        self.assertEqual({r.category for r in lua}, {Category.LUA})

    @staticmethod
    def _script_paths():
        from tacz_validator.core.index import GunpackIndex
        from tacz_validator.core.source import open_source
        from tacz_validator import rules

        with open_source(LUA_PACK) as source:
            index = GunpackIndex.build(source, rules.load())

            class Fake:
                pass

            context = Fake()
            context.index = index
            context.rules = rules.load()
            return lua_script.LuaScriptValidator._script_files(context)


@unittest.skipUnless(HAVE_LUAPARSER, "luaparser is not installed")
class LuaNoFalsePositiveTests(unittest.TestCase):
    def test_a_pack_without_scripts_reports_nothing_from_this_check(self):
        report = tv.validate(VALID)
        self.assertEqual([r for r in report.results if r.code.startswith("LUA")], [])

    def test_disabling_the_check_silences_it(self):
        settings = ValidatorSettings(disabled_validators={"lua-script"})
        report = tv.validate(LUA_PACK, settings)
        self.assertEqual([r for r in report.results if r.code.startswith("LUA")], [])

    def test_an_external_namespace_makes_its_requires_acceptable(self):
        """A pack may require a script another pack ships."""
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        pack = os.path.join(directory, "pack")
        shutil.copytree(LUA_PACK, pack)
        script = os.path.join(pack, "assets", "luapack", "scripts", "bad_require.lua")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write('local other = require("otherpack_shared")\nreturn other\n')

        loud = tv.validate(pack)
        self.assertTrue([r for r in loud.results if r.code == Code.LUA_REQUIRE_UNRESOLVED])

        quiet = tv.validate(pack, ValidatorSettings(external_namespaces={"otherpack"}))
        self.assertEqual(
            [r for r in quiet.results if r.code == Code.LUA_REQUIRE_UNRESOLVED], []
        )


class LuaWithoutTheParserTests(unittest.TestCase):
    """The extra is optional, so its absence has to be visible, not silent."""

    def test_a_note_says_the_scripts_went_unchecked(self):
        original = lua_script._load_parser
        lua_script._load_parser = lambda: None
        self.addCleanup(setattr, lua_script, "_load_parser", original)

        report = tv.validate(LUA_PACK)
        notes = [r for r in report.results if r.code == Code.LUA_PARSER_MISSING]
        self.assertEqual(len(notes), 1, "one note for the run, not one per file")
        self.assertIs(notes[0].severity, Severity.INFO)
        self.assertIn("luaparser", notes[0].text("en"))
        self.assertIn("pip install", notes[0].suggestion_text("en"))
        # Nothing else may be claimed about scripts that were never parsed.
        self.assertEqual(
            [r for r in report.results if r.code.startswith("LUA") and r.code != Code.LUA_PARSER_MISSING],
            [],
        )

    def test_a_pack_without_scripts_stays_silent_even_then(self):
        original = lua_script._load_parser
        lua_script._load_parser = lambda: None
        self.addCleanup(setattr, lua_script, "_load_parser", original)

        report = tv.validate(VALID)
        self.assertEqual([r for r in report.results if r.code.startswith("LUA")], [])


class SyntaxErrorPositionTests(unittest.TestCase):
    def test_a_position_is_lifted_out_of_the_message(self):
        line, column, detail = lua_script._describe_syntax_error(
            Exception("syntax errors: line 4:0: no viable alternative")
        )
        self.assertEqual(line, 4)
        self.assertEqual(column, 1)  # ANTLR counts from zero, this tool from one
        self.assertEqual(detail, "no viable alternative")

    def test_a_message_without_a_position_still_reports_its_text(self):
        line, column, detail = lua_script._describe_syntax_error(Exception("boom"))
        self.assertIsNone(line)
        self.assertIsNone(column)
        self.assertEqual(detail, "boom")


if __name__ == "__main__":
    unittest.main()
