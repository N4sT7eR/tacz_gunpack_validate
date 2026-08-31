"""The Japanese UI is a shipped feature, so missing translations are bugs."""

import json
import os
import re
import unittest

from tacz_validator.core.i18n import Message, render, supported_locales

LOCALE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
    "tacz_validator",
    "locales",
)
SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "tacz_validator"
)


def load(locale):
    with open(os.path.join(LOCALE_DIR, "{}.json".format(locale)), encoding="utf-8") as handle:
        return json.load(handle)


class CatalogueTests(unittest.TestCase):
    def test_both_languages_are_available(self):
        self.assertEqual(supported_locales(), ["en", "ja"])

    def test_every_english_key_has_a_japanese_translation(self):
        self.assertEqual(sorted(load("en")), sorted(load("ja")))

    def test_placeholders_match_between_languages(self):
        english, japanese = load("en"), load("ja")
        pattern = re.compile(r"\{(\w+)\}")
        for key, template in english.items():
            self.assertEqual(
                sorted(pattern.findall(template)),
                sorted(pattern.findall(japanese[key])),
                "placeholders differ for {}".format(key),
            )

    def test_every_key_used_in_the_code_exists(self):
        english = load("en")
        used = set()
        pattern = re.compile(r'Message\(\s*"([a-z_]+\.[a-z_]+)"')
        for root, _, files in os.walk(SOURCE_DIR):
            for name in files:
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    used.update(pattern.findall(handle.read()))
        missing = sorted(key for key in used if key not in english)
        self.assertEqual(missing, [], "message keys with no catalogue entry")


class RenderTests(unittest.TestCase):
    def test_nested_messages_are_translated_too(self):
        message = Message(
            "entry.out_of_range",
            {"path": "rpm", "value": 5000, "problem": Message("range.at_most", {"value": 1200})},
        )
        self.assertIn("1200", render(message, "ja"))
        self.assertNotEqual(render(message, "en"), render(message, "ja"))

    def test_unknown_locale_falls_back_to_english(self):
        message = Message("pack.meta_missing")
        self.assertEqual(render(message, "xx"), render(message, "en"))

    def test_unknown_key_still_shows_its_parameters(self):
        self.assertIn("value=7", render(Message("nope.nope", {"value": 7}), "en"))


if __name__ == "__main__":
    unittest.main()
