"""Walking dotted key paths such as ``lod.model``, ``sounds.*`` or ``fire_mode[]``.

Rule sets describe where references and enums live as small path patterns, so
one generic walker keeps the validators free of hand-written nesting.
"""

from __future__ import annotations

from typing import Any, Iterator, List, NamedTuple, Union

from .jsonc import JsonArray, JsonObject, Position

__all__ = ["Match", "iter_matches", "position_of"]


class Match(NamedTuple):
    """One concrete location a pattern matched."""

    path: str  # the concrete path, e.g. "sounds.shoot"
    parent: Any  # the container holding the value
    key: Union[str, int]
    value: Any

    def position(self) -> Position:
        return position_of(self.parent, self.key)


def position_of(parent: Any, key: Union[str, int]) -> Position:
    """Best available source position for ``parent[key]``."""
    if isinstance(parent, JsonObject) and isinstance(key, str):
        return parent.position_of(key)
    if isinstance(parent, JsonArray) and isinstance(key, int):
        return parent.position_of(key)
    return Position(1, 1, 0)


def _split(pattern: str) -> List[str]:
    segments = []  # type: List[str]
    for raw in pattern.split("."):
        while raw.endswith("[]"):
            raw = raw[: -len("[]")]
            segments.append(raw)
            segments.append("[]")
            raw = ""
        if raw:
            segments.append(raw)
    return segments


def iter_matches(root: Any, pattern: str) -> Iterator[Match]:
    """Yield every value in ``root`` matching ``pattern``.

    ``*`` matches every key of an object and ``[]`` every element of an array,
    so ``sounds.*`` reaches each sound reference and ``fire_mode[]`` each mode.
    """
    segments = _split(pattern)
    if not segments:
        return
    yield from _walk(root, segments, "")


def _walk(node: Any, segments: List[str], prefix: str) -> Iterator[Match]:
    segment = segments[0]
    rest = segments[1:]

    if segment == "[]":
        if not isinstance(node, list):
            return
        for i, item in enumerate(node):
            path = "{}[{}]".format(prefix, i)
            if rest:
                yield from _walk(item, rest, path)
            else:
                yield Match(path, node, i, item)
        return

    if not isinstance(node, dict):
        return

    if segment == "*":
        for key in list(node.keys()):
            path = "{}.{}".format(prefix, key) if prefix else key
            if rest:
                yield from _walk(node[key], rest, path)
            else:
                yield Match(path, node, key, node[key])
        return

    if segment not in node:
        return
    path = "{}.{}".format(prefix, segment) if prefix else segment
    if rest:
        yield from _walk(node[segment], rest, path)
    else:
        yield Match(path, node, segment, node[segment])
