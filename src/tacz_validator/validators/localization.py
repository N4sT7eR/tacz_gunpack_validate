"""Layer 8: every ``name``/``tooltip`` key needs a translation to show up in game."""

from __future__ import annotations

from typing import Dict, Iterable, Set

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.result import Code, Severity, ValidationResult
from ..core.validator import Validator, register


@register
class LocalizationValidator(Validator):
    name = "localization"
    description = "Localization keys referenced by entries exist in the language files"
    order = 60

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        reference_language = context.rules.language_files.get("reference_language", "en_us")
        used = self._collect_used_keys(context)
        if not used:
            return

        for namespace, languages in sorted(context.index.language_files.items()):
            catalogues = {
                name: document.value
                for name, document in languages.items()
                if document.error is None and isinstance(document.value, dict)
            }
            if not catalogues:
                continue
            for name in sorted(catalogues):
                # A key missing from the reference language is invisible in game
                # for everyone; missing from a translation only affects that one.
                severity = (
                    Severity.WARNING if name == reference_language else Severity.INFO
                )
                document = languages[name]
                for key, origin in sorted(used.items()):
                    if key in catalogues[name]:
                        continue
                    if not key.startswith(namespace + "."):
                        continue  # keys for another namespace live in its own pack
                    yield context.result(
                        severity,
                        Code.LANG_KEY_MISSING,
                        Message("lang.key_missing", {"key": key, "language": name + ".json"}),
                        file=document.relative_path,
                        resource_id=origin,
                        suggestion=Message(
                            "suggestion.add_key", {"key": key, "language": name + ".json"}
                        ),
                    )

            if context.settings.check_unused_assets:
                yield from self._report_unused(context, languages, catalogues, used)

    @staticmethod
    def _collect_used_keys(context: ValidationContext) -> Dict[str, str]:
        """Localization keys referenced by entries, mapped to the entry using them."""
        used = {}  # type: Dict[str, str]
        for kind in sorted(context.index.entries):
            keys = context.rules.entry(kind).get("localization_keys", [])
            if not keys:
                continue
            for entry in context.index.entries_of(kind):
                value = entry.document.value
                if not isinstance(value, dict):
                    continue
                for key_name in keys:
                    candidate = value.get(key_name)
                    if isinstance(candidate, str) and candidate:
                        used.setdefault(candidate, entry.resource_id)
        return used

    @staticmethod
    def _report_unused(context, languages, catalogues, used) -> Iterable[ValidationResult]:
        reference = context.rules.language_files.get("reference_language", "en_us")
        catalogue = catalogues.get(reference)
        if catalogue is None:
            return
        for key in sorted(catalogue):
            if key in used:
                continue
            yield context.info(
                Code.LANG_KEY_UNUSED,
                Message("lang.key_unused", {"key": key}),
                file=languages[reference].relative_path,
            )
