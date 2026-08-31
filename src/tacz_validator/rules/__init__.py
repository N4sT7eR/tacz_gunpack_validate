"""Version-specific rule sets.

TaCZ changes its file format between versions, so nothing version-dependent
belongs in validator code.  Everything a validator needs to know about a given
TaCZ release -- directory layout, enum values, required keys, numeric limits --
lives in a JSON file next to this module and is loaded through :class:`RuleSet`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, NamedTuple, Optional

from ..core.i18n import Message
from ..core.result import Severity

__all__ = ["RuleSet", "ResourceKind", "EnumRule", "RangeRule", "available_versions", "load"]

_RULES_DIR = os.path.dirname(os.path.abspath(__file__))
_FILENAME_TEMPLATE = "tacz_{}.json"
DEFAULT_VERSION = "1.20.1"


class ResourceKind(NamedTuple):
    """Where a given kind of resource lives inside a pack."""

    name: str
    side: str  # "assets" or "data"
    directory: str
    extensions: List[str]
    prefix_match: bool = False

    def relative_paths(self, namespace: str, path: str) -> List[str]:
        """Candidate pack-relative paths for ``namespace:path``."""
        return [
            "{}/{}/{}/{}{}".format(self.side, namespace, self.directory, path, ext)
            for ext in self.extensions
        ]

    def directory_for(self, namespace: str) -> str:
        return "{}/{}/{}".format(self.side, namespace, self.directory)


class EnumRule(NamedTuple):
    values: List[str]
    severity: Severity
    comment: str = ""


class RangeRule(NamedTuple):
    minimum: Optional[float]
    maximum: Optional[float]
    exclusive_min: Optional[float]
    severity: Severity

    def check(self, value: float) -> Optional[Message]:
        """Describe what is wrong with ``value``, or ``None`` when it is fine."""
        if self.exclusive_min is not None and value <= self.exclusive_min:
            return Message("range.greater_than", {"value": _number(self.exclusive_min)})
        if self.minimum is not None and value < self.minimum:
            return Message("range.at_least", {"value": _number(self.minimum)})
        if self.maximum is not None and value > self.maximum:
            return Message("range.at_most", {"value": _number(self.maximum)})
        return None

    def describe(self) -> Message:
        if self.minimum is not None and self.maximum is not None:
            return Message(
                "range.between",
                {"minimum": _number(self.minimum), "maximum": _number(self.maximum)},
            )
        if self.maximum is not None:
            return Message("range.up_to", {"value": _number(self.maximum)})
        if self.exclusive_min is not None:
            return Message("range.above", {"value": _number(self.exclusive_min)})
        if self.minimum is not None:
            return Message("range.or_more", {"value": _number(self.minimum)})
        return Message("range.any")


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


class RuleSet:
    """Everything version-specific, loaded from one JSON document."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data
        self.id = data.get("id", "unknown")
        self.display_name = data.get("display_name", self.id)
        self.default_namespace = data.get("default_namespace", "minecraft")
        self.known_namespaces = set(data.get("known_namespaces", []))
        self.resource_kinds = {
            name: ResourceKind(
                name=name,
                side=spec["side"],
                directory=spec["directory"],
                extensions=list(spec.get("extensions", [".json"])),
                prefix_match=bool(spec.get("prefix_match", False)),
            )
            for name, spec in data.get("resource_kinds", {}).items()
        }
        self.entries = data.get("entries", {})
        self.enums = {
            name: EnumRule(
                values=list(spec["values"]),
                severity=Severity.from_name(spec.get("severity", "ERROR")),
                comment=spec.get("comment", ""),
            )
            for name, spec in data.get("enums", {}).items()
        }
        self.language_files = data.get("language_files", {})

    # -- lookups -------------------------------------------------------------

    def kind(self, name: str) -> Optional[ResourceKind]:
        return self.resource_kinds.get(name)

    def entry(self, entry_kind: str) -> Dict[str, Any]:
        return self.entries.get(entry_kind, {})

    def enum(self, name: str) -> Optional[EnumRule]:
        return self.enums.get(name)

    def ranges_for(self, entry_kind: str) -> Dict[str, RangeRule]:
        raw = self.entry(entry_kind).get("ranges", {})
        result = {}  # type: Dict[str, RangeRule]
        for path, spec in raw.items():
            result[path] = RangeRule(
                minimum=spec.get("min"),
                maximum=spec.get("max"),
                exclusive_min=spec.get("exclusive_min"),
                severity=Severity.from_name(spec.get("severity", "WARNING")),
            )
        return result

    #: Entry kinds that are indexed by their own directory, i.e. every JSON file
    #: found there is an entry of that kind.
    def entry_kind_for_directory(self, side: str, directory: str) -> Optional[str]:
        for name, kind in self.resource_kinds.items():
            if kind.side == side and kind.directory == directory and name in self.entries:
                return name
        return None

    @property
    def index_kinds(self) -> List[str]:
        return [k for k in self.resource_kinds if k.endswith("_index")]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<RuleSet {}>".format(self.id)


def available_versions() -> List[str]:
    versions = []
    for name in sorted(os.listdir(_RULES_DIR)):
        if name.startswith("tacz_") and name.endswith(".json"):
            versions.append(name[len("tacz_") : -len(".json")].replace("_", "."))
    return versions


def load(version: str = DEFAULT_VERSION) -> RuleSet:
    """Load the rule set for ``version`` (e.g. ``"1.20.1"``)."""
    filename = _FILENAME_TEMPLATE.format(version.replace(".", "_"))
    path = os.path.join(_RULES_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "No rule set for TaCZ {}. Available: {}".format(version, ", ".join(available_versions()))
        )
    with open(path, encoding="utf-8") as handle:
        return RuleSet(json.load(handle))
