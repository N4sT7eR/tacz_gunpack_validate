"""The Lua checks, and the fixture pack that exercises one finding per file.

Skipped when luaparser is not installed, mirroring the GUI tests: the extra is
optional, so the core suite has to keep passing without it.
"""

import contextlib
import io as _io
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
SYNTAX_PACK = os.path.join(DATA, "lua_syntax_pack")
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

    def test_a_name_that_resembles_nothing_still_gets_a_next_step(self):
        """"It is nil at runtime" is a diagnosis, not something to act on."""
        plain = next(
            r for r in self.report.results
            if r.code == Code.LUA_UNDEFINED_GLOBAL and "FIRE_MODE_TRACK" in r.text("en")
        )
        advice = plain.suggestion_text("en")
        self.assertIn("FIRE_MODE_TRACK", advice)
        self.assertIn("local", advice)

    def test_the_missing_return_names_the_table_the_script_built(self):
        found = next(r for r in self.report.results if r.code == Code.LUA_NO_MODULE_RETURN)
        self.assertIn("return M", found.suggestion_text("en"))
        # And points at where that table was declared, not at nothing.
        self.assertIsNotNone(found.line)

    def test_an_unavailable_library_says_what_to_use_instead(self):
        advice = {
            r.text("en").split('"')[1]: r.suggestion_text("en")
            for r in self.report.results
            if r.code == Code.LUA_UNAVAILABLE_LIBRARY
        }
        self.assertIn("api:getCurrentTimestamp()", advice["os"])
        # io has no TaCZ equivalent, so the advice is to drop the call.
        self.assertIn("Remove", advice["io"])

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
class SyntaxDiagnosisTests(unittest.TestCase):
    """One broken script per common mistake, each answering three questions.

    Where is it, what is wrong, and what do I do -- luaparser answers none of
    them on its own: it parses with ANTLR's bail strategy, which for most parser
    errors throws the position away entirely.
    """

    @classmethod
    def setUpClass(cls):
        report = tv.validate(SYNTAX_PACK)
        cls.findings = {
            os.path.basename(r.file): r
            for r in report.results
            if r.code == Code.LUA_SYNTAX
        }

    def test_every_broken_script_is_reported_exactly_once(self):
        scripts = os.listdir(
            os.path.join(SYNTAX_PACK, "assets", "luasyntax", "scripts")
        )
        self.assertEqual(sorted(self.findings), sorted(scripts))

    def test_every_report_carries_a_line_a_column_and_a_fix(self):
        for name, finding in sorted(self.findings.items()):
            self.assertIsNotNone(finding.line, name)
            self.assertIsNotNone(finding.column, name)
            self.assertTrue(finding.suggestion_text("en"), name)
            self.assertTrue(finding.suggestion_text("ja"), name)

    def test_no_report_leaks_antlr_wording(self):
        for name, finding in sorted(self.findings.items()):
            text = finding.text("en")
            for jargon in ("mismatched input", "extraneous input", "<EOF>",
                           "token recognition", "expecting"):
                self.assertNotIn(jargon, text, "{}: {}".format(name, text))

    def test_the_position_points_at_the_line_that_is_wrong(self):
        # Spot-checked rather than exhaustive: these are the ones whose line is
        # unambiguous, and a checker that points at the wrong line is worse than
        # one that points nowhere.
        self.assertEqual(self.findings["missing_then.lua"].line, 5)
        self.assertEqual(self.findings["missing_comma.lua"].line, 3)
        self.assertEqual(self.findings["assign_in_condition.lua"].line, 5)
        self.assertEqual(self.findings["extra_end.lua"].line, 6)

    def test_an_unclosed_block_says_so_rather_than_naming_the_file_end(self):
        text = self.findings["missing_end.lua"].text("en")
        self.assertIn("end", text)
        self.assertIn("Add the missing", self.findings["missing_end.lua"].suggestion_text("en"))

    def test_a_comparison_written_with_one_equals_is_named_as_such(self):
        finding = self.findings["assign_in_condition.lua"]
        self.assertIn("==", finding.text("en"))
        self.assertIn("==", finding.suggestion_text("ja"))

    def test_bang_not_equals_points_at_the_lua_spelling(self):
        self.assertIn("~=", self.findings["bang_not_equals.lua"].suggestion_text("en"))

    def test_an_unterminated_string_is_recognised_as_one(self):
        finding = self.findings["unterminated_string.lua"]
        self.assertIn("string", finding.text("en"))
        self.assertEqual(finding.line, 3)

    def test_nothing_is_written_to_the_terminal_behind_the_report(self):
        """luaparser prints ANTLR's wording to stderr unless it is stopped.

        That raw diagnostic is what this checker exists to replace, so it must
        not appear alongside the replacement.
        """
        captured = _io.StringIO()
        with contextlib.redirect_stderr(captured):
            tv.validate(SYNTAX_PACK)
        self.assertEqual(captured.getvalue(), "")

    def test_a_leftover_bracket_is_offered_for_deletion(self):
        for name in ("extra_end.lua", "extra_paren.lua"):
            self.assertIn("Remove", self.findings[name].suggestion_text("en"), name)


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
    """The fallback path, for when re-parsing cannot place the error either."""

    def test_a_position_is_lifted_out_of_the_message(self):
        line, column, detail = lua_script._from_message(
            Exception("syntax errors: line 4:0: no viable alternative")
        )
        self.assertEqual(line, 4)
        self.assertEqual(column, 1)  # ANTLR counts from zero, this tool from one
        self.assertEqual(detail, "no viable alternative")

    def test_a_message_without_a_position_still_reports_its_text(self):
        line, column, detail = lua_script._from_message(Exception("boom"))
        self.assertIsNone(line)
        self.assertIsNone(column)
        self.assertEqual(detail, "boom")

    def test_unmapped_wording_is_shown_rather_than_swallowed(self):
        message, suggestion = lua_script._explain("something ANTLR has never said")
        self.assertEqual(message.key, "lua.syntax")
        self.assertIsNone(suggestion)

    def test_the_end_of_file_marker_is_rendered_as_a_phrase(self):
        from tacz_validator.core.i18n import Message, render

        readable = lua_script._readable("<EOF>")
        self.assertIsInstance(readable, Message)
        self.assertNotIn("EOF", render(readable, "ja"))

    def test_quoted_tokens_lose_their_quotes(self):
        self.assertEqual(lua_script._readable("'then'"), "then")


if __name__ == "__main__":
    unittest.main()
