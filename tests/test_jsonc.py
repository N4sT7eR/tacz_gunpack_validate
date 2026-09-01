"""The parser is the foundation: if positions drift, every report lies."""

import unittest

from tacz_validator.core import jsonc


class ParseTests(unittest.TestCase):
    def test_parses_comments_and_keeps_values(self):
        document = jsonc.parse('{\n  // a comment\n  "a": 1,\n  /* block */ "b": [1, 2]\n}')
        self.assertEqual(document.value["a"], 1)
        self.assertEqual(document.value["b"], [1, 2])

    def test_comment_inside_string_is_kept(self):
        document = jsonc.parse('{"url": "https://example.com//path"}')
        self.assertEqual(document.value["url"], "https://example.com//path")

    def test_records_position_of_each_value(self):
        document = jsonc.parse('{\n  "a": 1,\n  "b": {\n    "c": 2\n  }\n}')
        self.assertEqual(document.value.position_of("a").line, 2)
        self.assertEqual(document.value["b"].position_of("c").line, 4)

    def test_array_item_positions(self):
        document = jsonc.parse('[\n  "x",\n  "y"\n]')
        self.assertEqual(document.value.position_of(1).line, 3)

    def test_escapes_and_surrogate_pairs(self):
        document = jsonc.parse(r'{"a": "line\nbreak", "b": "A", "c": "😀"}')
        self.assertEqual(document.value["a"], "line\nbreak")
        self.assertEqual(document.value["b"], "A")
        self.assertEqual(document.value["c"], "\U0001f600")

    def test_reports_lenient_constructs_without_failing(self):
        document = jsonc.parse('{"a": 1, "a": 2, "b": [1,],}')
        kinds = sorted({issue.kind for issue in document.issues})
        self.assertEqual(kinds, ["duplicate_key", "trailing_comma"])
        self.assertEqual(document.value["a"], 2)

    def test_strict_mode_rejects_comments(self):
        with self.assertRaises(jsonc.JsonSyntaxError):
            jsonc.parse("{}// nope", allow_comments=False)


class SyntaxErrorTests(unittest.TestCase):
    def assert_fails_at(self, text, line, column):
        with self.assertRaises(jsonc.JsonSyntaxError) as caught:
            jsonc.parse(text)
        self.assertEqual(
            (caught.exception.position.line, caught.exception.position.column), (line, column)
        )

    def test_missing_comma(self):
        self.assert_fails_at('{"a": 1 "b": 2}', 1, 9)

    def test_unterminated_string_points_at_its_start(self):
        self.assert_fails_at('{\n  "a": "oops\n}', 2, 8)

    def test_missing_closing_brace_points_at_the_opening_one(self):
        self.assert_fails_at('{\n  "a": 1\n', 1, 1)

    def test_error_is_translatable(self):
        with self.assertRaises(jsonc.JsonSyntaxError) as caught:
            jsonc.parse('{"a" 1}')
        self.assertNotEqual(caught.exception.text("en"), caught.exception.text("ja"))


class FastPathTests(unittest.TestCase):
    def test_matches_the_positional_parser(self):
        text = '{\n  // comment\n  "a": [1, 2, {"b": null}],\n  "c": true\n}'
        self.assertEqual(jsonc.parse_fast(text).value, jsonc.parse(text).value)

    def test_falls_back_for_constructs_json_rejects(self):
        # json.loads rejects the trailing comma; TaCZ's parser accepts it.
        document = jsonc.parse_fast('{"a": [1, 2,]}')
        self.assertEqual(document.value["a"], [1, 2])

    def test_strip_comments_preserves_offsets(self):
        text = '{"a": 1} // tail'
        self.assertEqual(len(jsonc.strip_comments(text)), len(text))


if __name__ == "__main__":
    unittest.main()
