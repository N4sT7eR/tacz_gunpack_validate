"""Importing this package registers every built-in validator."""

from . import (  # noqa: F401
    cross_reference,
    entries,
    json_syntax,
    localization,
    lua_script,
    naming,
    structure,
)

__all__ = [
    "cross_reference",
    "entries",
    "json_syntax",
    "localization",
    "lua_script",
    "naming",
    "structure",
]
