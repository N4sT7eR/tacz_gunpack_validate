"""Parsing and validation of Minecraft/TaCZ ``namespace:path`` identifiers."""

from __future__ import annotations

import difflib
import re
from typing import Iterable, List, NamedTuple, Optional, Tuple

__all__ = [
    "ResourceLocation",
    "MalformedResourceLocation",
    "NAMESPACE_PATTERN",
    "PATH_PATTERN",
    "DEFAULT_NAMESPACE",
    "invalid_characters",
    "suggest_identifier",
    "closest_matches",
]

#: Minecraft accepts these characters in a namespace.
NAMESPACE_PATTERN = re.compile(r"^[a-z0-9_.-]+$")
#: Paths may additionally contain ``/``.
PATH_PATTERN = re.compile(r"^[a-z0-9_./-]+$")

#: What a bare ``foo`` (no colon) resolves to, matching Minecraft's own rule.
DEFAULT_NAMESPACE = "minecraft"


class MalformedResourceLocation(ValueError):
    """The raw string is not shaped like an identifier at all."""


class ResourceLocation(NamedTuple):
    namespace: str
    path: str

    def __str__(self) -> str:
        return "{}:{}".format(self.namespace, self.path)

    @classmethod
    def parse(cls, raw: str, default_namespace: str = DEFAULT_NAMESPACE) -> "ResourceLocation":
        """Split ``raw`` into namespace and path.

        A missing namespace is filled in with ``default_namespace``; whether that
        is worth reporting is the caller's decision, since TaCZ's own files rely
        on it in a few places.
        """
        if not isinstance(raw, str) or not raw:
            raise MalformedResourceLocation("Identifier must be a non-empty string")
        if raw.count(":") > 1:
            raise MalformedResourceLocation(
                "Identifier must contain at most one ':' (got {!r})".format(raw)
            )
        if ":" in raw:
            namespace, path = raw.split(":", 1)
            if not namespace:
                raise MalformedResourceLocation("Namespace is empty in {!r}".format(raw))
        else:
            namespace, path = default_namespace, raw
        if not path:
            raise MalformedResourceLocation("Path is empty in {!r}".format(raw))
        return cls(namespace, path)

    @property
    def has_explicit_namespace(self) -> bool:  # pragma: no cover - informational
        return True

    def is_valid_namespace(self) -> bool:
        return bool(NAMESPACE_PATTERN.match(self.namespace))

    def is_valid_path(self) -> bool:
        return bool(PATH_PATTERN.match(self.path))

    def is_valid(self) -> bool:
        return self.is_valid_namespace() and self.is_valid_path()

    def normalized(self) -> "ResourceLocation":
        """Best-effort lowercase/sanitised form, used for ``Suggested:`` hints."""
        return ResourceLocation(
            suggest_identifier(self.namespace, allow_slash=False),
            suggest_identifier(self.path, allow_slash=True),
        )


def invalid_characters(value: str, allow_slash: bool) -> List[str]:
    """Characters in ``value`` that Minecraft would reject, in order, deduplicated."""
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
    if allow_slash:
        allowed.add("/")
    seen = []  # type: List[str]
    for ch in value:
        if ch not in allowed and ch not in seen:
            seen.append(ch)
    return seen


def describe_characters(chars: Iterable[str]) -> str:
    """Human-readable list such as ``'A', ' ' (space)``."""
    names = {" ": "space", "\t": "tab"}
    parts = []
    for ch in chars:
        if ch in names:
            parts.append("{!r} ({})".format(ch, names[ch]))
        else:
            parts.append(repr(ch))
    return ", ".join(parts)


def suggest_identifier(value: str, allow_slash: bool = True) -> str:
    """Turn ``MyGunPack`` into ``mygunpack`` and ``my pack`` into ``my_pack``."""
    lowered = value.lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
    if allow_slash:
        allowed.add("/")
    cleaned = "".join(ch if ch in allowed else "_" for ch in lowered)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_")
    return cleaned or "unnamed"


def closest_matches(value: str, candidates: Iterable[str], limit: int = 3, cutoff: float = 0.75) -> List[str]:
    """Typo suggestions, e.g. ``rifel`` -> ``rifle``.

    ``difflib`` keeps this dependency-free; the cutoff is deliberately high so
    that a wrong suggestion does not send the user chasing the wrong file.
    """
    pool = [c for c in candidates if c != value]
    return difflib.get_close_matches(value, pool, n=limit, cutoff=cutoff)
