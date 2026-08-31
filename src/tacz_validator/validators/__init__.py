"""Importing this package registers every built-in validator."""

from . import cross_reference, entries, json_syntax, localization, naming, structure  # noqa: F401

__all__ = ["cross_reference", "entries", "json_syntax", "localization", "naming", "structure"]
