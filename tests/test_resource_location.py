"""Identifier rules -- the single most common source of broken packs."""

import unittest

from tacz_validator.core.resource_location import (
    MalformedResourceLocation,
    ResourceLocation,
    closest_matches,
    invalid_characters,
    suggest_identifier,
)


class ParseTests(unittest.TestCase):
    def test_valid_identifiers(self):
        for raw in ("tacz:ak47", "mypack:gun/uv/m4a1", "prd.iron_horus:x", "a-b:c-d"):
            location = ResourceLocation.parse(raw)
            self.assertTrue(location.is_valid(), raw)

    def test_rejected_identifiers(self):
        for raw in ("mypack:M4A1", "MyGunPack:x", "my pack:m4a1", "mypack:m4@a1"):
            self.assertFalse(ResourceLocation.parse(raw).is_valid(), raw)

    def test_missing_namespace_uses_the_default(self):
        self.assertEqual(ResourceLocation.parse("m4a1", "mypack"), ResourceLocation("mypack", "m4a1"))

    def test_malformed(self):
        for raw in ("a:b:c", ":path", "ns:", ""):
            with self.assertRaises(MalformedResourceLocation, msg=raw):
                ResourceLocation.parse(raw)


class SuggestionTests(unittest.TestCase):
    def test_normalises_case_and_spaces(self):
        self.assertEqual(suggest_identifier("MyGunPack", allow_slash=False), "mygunpack")
        self.assertEqual(suggest_identifier("my pack", allow_slash=False), "my_pack")

    def test_keeps_slashes_in_paths(self):
        self.assertEqual(suggest_identifier("Gun/UV/M4A1"), "gun/uv/m4a1")

    def test_reports_each_bad_character_once(self):
        self.assertEqual(invalid_characters("A A@b", allow_slash=False), ["A", " ", "@"])

    def test_typo_suggestion(self):
        self.assertEqual(closest_matches("rifel", ["rifle", "pistol", "smg"]), ["rifle"])

    def test_no_suggestion_for_unrelated_input(self):
        self.assertEqual(closest_matches("zzzzz", ["rifle", "pistol"]), [])


if __name__ == "__main__":
    unittest.main()
