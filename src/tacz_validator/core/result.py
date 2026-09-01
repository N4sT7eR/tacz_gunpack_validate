"""Severity levels, error codes and the result model shared by every validator."""

from __future__ import annotations

import enum
import itertools
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .i18n import DEFAULT_LOCALE, Message, render

__all__ = ["Severity", "Category", "Code", "ValidationResult", "ValidationReport"]


class Severity(enum.IntEnum):
    """How badly a finding breaks the pack.

    The ordering matters: ``INFO < WARNING < ERROR`` lets the CLI filter with a
    single comparison, and lets the GUI sort the most urgent findings first.
    """

    INFO = 10
    WARNING = 20
    ERROR = 30

    @property
    def label(self) -> str:
        return self.name

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        try:
            return cls[name.strip().upper()]
        except KeyError:
            raise ValueError("Unknown severity: {}".format(name))


class Category(enum.Enum):
    """Which body of rules a finding comes from.

    Severity says how badly something is broken; the category says *whose rule*
    it broke, which is the question a pack author actually asks first -- is this
    my JSON being malformed, a TaCZ structural requirement, a naming convention,
    or my Lua?  The two are orthogonal: every category can produce findings at
    every severity.

    Deliberately derived from the code prefix rather than stored on each
    finding, so a validator never has to remember to set it and the two can
    never drift apart.
    """

    JSON = "json"
    LUA = "lua"
    STRUCTURE = "structure"
    NAMING = "naming"
    SCHEMA = "schema"
    REFERENCE = "reference"
    LOCALIZATION = "localization"
    CONVENTION = "convention"
    UNKNOWN = "unknown"

    @property
    def label_key(self) -> str:
        return "category.{}".format(self.value)

    def label(self, locale: str = DEFAULT_LOCALE) -> str:
        return render(Message(self.label_key), locale)

    @classmethod
    def from_name(cls, name: str) -> "Category":
        wanted = name.strip().lower()
        for member in cls:
            if member.value == wanted:
                return member
        raise ValueError("Unknown category: {}".format(name))


#: Code prefix -> category.  A new prefix must be added here; the test suite
#: fails otherwise, which is what stops a new check from silently landing in
#: "unknown".
_CATEGORY_BY_PREFIX = {
    "JSON": Category.JSON,
    "LUA": Category.LUA,
    "PACK": Category.STRUCTURE,
    "ID": Category.NAMING,
    "ENTRY": Category.SCHEMA,
    "REF": Category.REFERENCE,
    "LANG": Category.LOCALIZATION,
    "ASSET": Category.CONVENTION,
}


def code_prefix(code: str) -> str:
    """The leading letters of a finding code: ``"REF001"`` -> ``"REF"``."""
    return "".join(itertools.takewhile(str.isalpha, (code or "").upper()))


def category_of(code: str) -> Category:
    return _CATEGORY_BY_PREFIX.get(code_prefix(code), Category.UNKNOWN)


class Code:
    """Stable identifiers for findings.

    Messages get reworded and translated; codes do not.  They are what users put
    behind ``--ignore`` and what the GUI filters on, so **never reuse a retired
    code for a different check**.
    """

    # -- JSON syntax and lenient constructs ---------------------------------
    JSON_SYNTAX = "JSON001"
    JSON_TRAILING_COMMA = "JSON002"
    JSON_DUPLICATE_KEY = "JSON003"
    JSON_NON_STANDARD_NUMBER = "JSON004"
    JSON_ENCODING = "JSON005"
    JSON_ROOT_NOT_OBJECT = "JSON006"

    # -- Lua scripts ---------------------------------------------------------
    LUA_SYNTAX = "LUA001"
    LUA_UNDEFINED_GLOBAL = "LUA002"
    LUA_UNAVAILABLE_LIBRARY = "LUA003"
    LUA_NO_MODULE_RETURN = "LUA004"
    LUA_REQUIRE_UNRESOLVED = "LUA005"
    LUA_PARSER_MISSING = "LUA006"
    LUA_ENCODING = "LUA007"

    # -- pack structure ------------------------------------------------------
    PACK_META_MISSING = "PACK001"
    PACK_META_NAMESPACE_MISSING = "PACK002"
    PACK_NAMESPACE_MISMATCH = "PACK003"
    PACK_NO_CONTENT = "PACK004"
    PACK_INFO_MISSING = "PACK005"
    PACK_UNKNOWN_DIRECTORY = "PACK006"

    # -- identifiers and naming ---------------------------------------------
    ID_INVALID_NAMESPACE = "ID001"
    ID_INVALID_PATH = "ID002"
    ID_NAMESPACE_OMITTED = "ID003"
    ID_UPPERCASE = "ID004"
    ID_FILENAME_INVALID = "ID005"
    ID_MALFORMED = "ID006"

    # -- cross references ----------------------------------------------------
    REF_MISSING = "REF001"
    REF_CASE_MISMATCH = "REF002"
    REF_EXTERNAL_UNKNOWN = "REF003"
    REF_CIRCULAR = "REF004"
    REF_SOUND_MISSING = "REF005"

    # -- entry schema --------------------------------------------------------
    ENTRY_REQUIRED_KEY_MISSING = "ENTRY001"
    ENTRY_UNKNOWN_KEY = "ENTRY002"
    ENTRY_WRONG_TYPE = "ENTRY003"
    ENTRY_INVALID_ENUM = "ENTRY004"
    ENTRY_VALUE_OUT_OF_RANGE = "ENTRY005"
    ENTRY_RECOMMENDED_KEY_MISSING = "ENTRY006"

    # -- localization --------------------------------------------------------
    LANG_KEY_MISSING = "LANG001"
    LANG_FILENAME_INVALID = "LANG002"
    LANG_KEY_UNUSED = "LANG003"

    # -- assets --------------------------------------------------------------
    ASSET_UNUSED = "ASSET001"


@dataclass(frozen=True)
class ValidationResult:
    """A single finding.

    ``file`` is always relative to the pack root so that reports stay portable
    between machines, and the wording is kept as a :class:`~.i18n.Message` so a
    finished report can be re-rendered in another language without re-running.
    """

    severity: Severity
    code: str
    message: Message
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    resource_id: Optional[str] = None
    suggestion: Optional[Message] = None
    validator: Optional[str] = None

    @property
    def category(self) -> "Category":
        """Which body of rules this finding comes from, from its code prefix."""
        return category_of(self.code)

    def category_label(self, locale: str = DEFAULT_LOCALE) -> str:
        return self.category.label(locale)

    def text(self, locale: str = DEFAULT_LOCALE) -> str:
        return render(self.message, locale)

    def suggestion_text(self, locale: str = DEFAULT_LOCALE) -> str:
        return render(self.suggestion, locale) if self.suggestion is not None else ""

    @property
    def location(self) -> str:
        if self.file is None:
            return "(pack)"
        if self.line is None:
            return self.file
        if self.column is None:
            return "{}:{}".format(self.file, self.line)
        return "{}:{}:{}".format(self.file, self.line, self.column)

    def sort_key(self):
        return (
            -int(self.severity),
            self.file or "",
            self.line or 0,
            self.column or 0,
            self.code,
        )


@dataclass
class ValidationReport:
    """Everything a single validation run produced."""

    root: str
    results: List[ValidationResult] = field(default_factory=list)
    scanned_files: int = 0
    duration_seconds: float = 0.0
    cancelled: bool = False

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)

    def extend(self, results: Iterable[ValidationResult]) -> None:
        self.results.extend(results)

    def sorted_results(self) -> List[ValidationResult]:
        return sorted(self.results, key=lambda r: r.sort_key())

    def count(self, severity: Severity) -> int:
        return sum(1 for r in self.results if r.severity is severity)

    @property
    def errors(self) -> int:
        return self.count(Severity.ERROR)

    @property
    def warnings(self) -> int:
        return self.count(Severity.WARNING)

    @property
    def infos(self) -> int:
        return self.count(Severity.INFO)

    @property
    def has_errors(self) -> bool:
        return self.errors > 0

    def counts_by_category(
        self, results: Optional[Iterable[ValidationResult]] = None
    ) -> Dict[Category, int]:
        """Findings per category, in :class:`Category` declaration order.

        Only categories that actually occurred are returned: a breakdown line
        padded out with zeroes tells the reader nothing about what to fix next.
        """
        rows = self.results if results is None else list(results)
        tally = {}  # type: Dict[Category, int]
        for result in rows:
            tally[result.category] = tally.get(result.category, 0) + 1
        return {category: tally[category] for category in Category if category in tally}

    def filtered(
        self,
        minimum: Severity = Severity.INFO,
        ignored_codes: Optional[Iterable[str]] = None,
        categories: Optional[Iterable["Category"]] = None,
        ignored_categories: Optional[Iterable["Category"]] = None,
    ) -> List[ValidationResult]:
        """Apply the user's filters.

        ``categories`` is an allow-list (``None`` keeps everything);
        ``ignored_categories`` is subtracted afterwards, so passing both keeps
        the intersection rather than making one silently win.
        """
        ignored = {c.strip().upper() for c in (ignored_codes or []) if c.strip()}
        kept = set(categories) if categories is not None else None
        dropped = set(ignored_categories or ())
        return [
            r
            for r in self.sorted_results()
            if r.severity >= minimum
            and r.code.upper() not in ignored
            and (kept is None or r.category in kept)
            and r.category not in dropped
        ]
