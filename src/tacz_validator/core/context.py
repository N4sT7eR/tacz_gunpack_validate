"""Settings and the shared state every validator reads from."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

from ..rules import RuleSet
from .i18n import DEFAULT_LOCALE, Message
from .index import GunpackIndex
from .result import Category, Severity, ValidationResult

__all__ = ["ValidatorSettings", "ValidationContext"]


@dataclass
class ValidatorSettings:
    """User-facing knobs, shared by the CLI and the GUI."""

    version: str = "1.20.1"
    #: Language the report is rendered in ("en" or "ja").
    locale: str = DEFAULT_LOCALE
    minimum_severity: Severity = Severity.INFO
    ignored_codes: Set[str] = field(default_factory=set)
    #: Report only these categories.  Empty means "every category", so that the
    #: default stays "show everything" without a sentinel.
    categories: Set[Category] = field(default_factory=set)
    #: Categories to drop, applied after :attr:`categories`.
    ignored_categories: Set[Category] = field(default_factory=set)
    disabled_validators: Set[str] = field(default_factory=set)
    #: Namespaces owned by other packs or mods.  References into these are
    #: reported as informational, never as missing files.
    external_namespaces: Set[str] = field(default_factory=set)
    #: Report references into namespaces this pack does not define at all.
    report_unknown_external: bool = True
    #: Reject comments outright instead of accepting the JSONC that TaCZ uses.
    strict_json: bool = False
    #: Unused-asset detection is prone to false positives, so it is opt-in.
    check_unused_assets: bool = False

    def is_ignored(self, code: str) -> bool:
        return code.upper() in {c.upper() for c in self.ignored_codes}

    @property
    def selected_categories(self):
        """The allow-list in the shape :meth:`ValidationReport.filtered` wants."""
        return self.categories or None


class ValidationContext:
    """Everything a validator needs, and nothing it should have to rebuild."""

    def __init__(self, index: GunpackIndex, rule_set: RuleSet, settings: ValidatorSettings) -> None:
        self.index = index
        self.rules = rule_set
        self.settings = settings
        self._current_validator = None  # type: Optional[str]

    # -- namespaces ----------------------------------------------------------

    @property
    def pack_namespaces(self) -> Set[str]:
        """Namespaces this pack actually ships content for."""
        return set(self.index.namespaces)

    @property
    def primary_namespace(self) -> Optional[str]:
        """The namespace declared in ``gunpack.meta.json``, when there is one."""
        return self.index.meta_namespace

    def is_internal(self, namespace: str) -> bool:
        return namespace in self.index.namespaces

    def is_known_external(self, namespace: str) -> bool:
        return namespace in self.rules.known_namespaces or namespace in self.settings.external_namespaces

    # -- result construction -------------------------------------------------

    def result(
        self,
        severity: Severity,
        code: str,
        message: Message,
        file: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        resource_id: Optional[str] = None,
        suggestion: Optional[Message] = None,
    ) -> ValidationResult:
        return ValidationResult(
            severity=severity,
            code=code,
            message=message,
            file=file,
            line=line,
            column=column,
            resource_id=resource_id,
            suggestion=suggestion,
            validator=self._current_validator,
        )

    def error(self, code: str, message: Message, **kwargs) -> ValidationResult:
        return self.result(Severity.ERROR, code, message, **kwargs)

    def warning(self, code: str, message: Message, **kwargs) -> ValidationResult:
        return self.result(Severity.WARNING, code, message, **kwargs)

    def info(self, code: str, message: Message, **kwargs) -> ValidationResult:
        return self.result(Severity.INFO, code, message, **kwargs)
