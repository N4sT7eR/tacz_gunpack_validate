"""Layer 2: required keys, value types, enums and numeric limits.

The rules live entirely in the version's JSON rule set, so supporting a new TaCZ
release means editing data, not this file.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.paths import iter_matches, position_of
from ..core.resource_location import closest_matches
from ..core.result import Code, Severity, ValidationResult
from ..core.validator import Validator, register

_TYPE_NAMES = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


@register
class EntryValidator(Validator):
    name = "entries"
    description = "Required keys, value types, enum values and numeric ranges"
    order = 40

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        for kind in sorted(context.index.entries):
            spec = context.rules.entry(kind)
            if not spec:
                continue
            ranges = context.rules.ranges_for(kind)
            for entry in context.index.entries_of(kind):
                document = entry.document
                if document.error is not None:
                    continue  # already reported by json-syntax; nothing to inspect
                value = document.value
                if not isinstance(value, dict):
                    yield context.error(
                        Code.JSON_ROOT_NOT_OBJECT,
                        Message("json.root_not_object", {"kind": kind.replace("_", " ")}),
                        file=document.relative_path,
                        resource_id=entry.resource_id,
                    )
                    continue
                # Per-entry, so that one document's variant never leaks into the next.
                entry_spec = self._apply_variant(spec, value)
                yield from self._check_required(context, entry, entry_spec, value)
                yield from self._check_recommended(context, entry, entry_spec, value)
                yield from self._check_unknown(context, entry, entry_spec, value)
                yield from self._check_types(context, entry, entry_spec, value)
                yield from self._check_enums(context, entry, entry_spec, value)
                yield from self._check_ranges(context, entry, ranges, value)

    # -- individual checks ---------------------------------------------------

    @staticmethod
    def _apply_variant(spec, value):
        """Fold in the rules for this document's own ``type``.

        A pack's recipes folder holds both TaCZ gun smith recipes and ordinary
        vanilla ones, and they require completely different keys.
        """
        variants = spec.get("variants")
        if not variants:
            return spec
        discriminator = value.get(variants.get("key", "type"))
        case = variants.get("cases", {}).get(discriminator)
        if not case:
            return spec
        merged = dict(spec)
        for field in ("required", "recommended", "optional"):
            if field in case:
                merged[field] = list(spec.get(field, [])) + [
                    key for key in case[field] if key not in spec.get(field, [])
                ]
        for field in ("types", "enums", "references"):
            if field in case:
                combined = dict(spec.get(field, {}))
                combined.update(case[field])
                merged[field] = combined
        return merged


    @staticmethod
    def _check_required(context, entry, spec, value) -> Iterable[ValidationResult]:
        for key in spec.get("required", []):
            if key in value:
                continue
            yield context.error(
                Code.ENTRY_REQUIRED_KEY_MISSING,
                Message("entry.required_missing", {"key": key}),
                file=entry.relative_path,
                line=getattr(value, "position", None).line if hasattr(value, "position") else None,
                resource_id=entry.resource_id,
            )

    @staticmethod
    def _check_recommended(context, entry, spec, value) -> Iterable[ValidationResult]:
        """Keys every real pack sets, but which TaCZ appears to default.

        Reporting these as errors would flag working packs, so they are warnings:
        the pack loads, something just will not look or sound right.
        """
        for key in spec.get("recommended", []):
            if key in value:
                continue
            yield context.warning(
                Code.ENTRY_RECOMMENDED_KEY_MISSING,
                Message("entry.recommended_missing", {"key": key}),
                file=entry.relative_path,
                resource_id=entry.resource_id,
            )

    @staticmethod
    def _check_unknown(context, entry, spec, value) -> Iterable[ValidationResult]:
        # Only for entry kinds whose key set is fully known; guessing here would
        # bury the user in false positives the moment TaCZ adds a field.
        if not spec.get("closed"):
            return
        known = set(spec.get("required", [])) | set(spec.get("optional", []))
        for key in value:
            if key in known:
                continue
            position = value.position_of(key) if hasattr(value, "position_of") else None
            yield context.info(
                Code.ENTRY_UNKNOWN_KEY,
                Message("entry.unknown_key", {"key": key}),
                file=entry.relative_path,
                line=position.line if position else None,
                column=position.column if position else None,
                resource_id=entry.resource_id,
                suggestion=_suggest(key, known),
            )

    @staticmethod
    def _check_types(context, entry, spec, value) -> Iterable[ValidationResult]:
        for key, type_name in spec.get("types", {}).items():
            if key not in value:
                continue
            expected = _TYPE_NAMES.get(type_name)
            if expected is None:
                continue
            actual = value[key]
            # bool is a subclass of int, so it would sneak past a number check.
            if type_name == "number" and isinstance(actual, bool):
                ok = False
            else:
                ok = isinstance(actual, expected)
            if ok:
                continue
            position = value.position_of(key) if hasattr(value, "position_of") else None
            yield context.error(
                Code.ENTRY_WRONG_TYPE,
                Message(
                    "entry.wrong_type",
                    {
                        "key": key,
                        "expected": Message("type.{}".format(type_name)),
                        "actual": _describe_type(actual),
                    },
                ),
                file=entry.relative_path,
                line=position.line if position else None,
                column=position.column if position else None,
                resource_id=entry.resource_id,
            )

    @staticmethod
    def _check_enums(context, entry, spec, value) -> Iterable[ValidationResult]:
        for pattern, enum_name in spec.get("enums", {}).items():
            rule = context.rules.enum(enum_name)
            if rule is None:
                continue
            for match in iter_matches(value, pattern):
                if not isinstance(match.value, str) or match.value in rule.values:
                    continue
                position = match.position()
                yield context.result(
                    rule.severity,
                    Code.ENTRY_INVALID_ENUM,
                    Message(
                        "entry.invalid_enum",
                        {
                            "enum": enum_name.replace("_", " "),
                            "value": repr(match.value),
                            "path": match.path,
                        },
                    ),
                    file=entry.relative_path,
                    line=position.line,
                    column=position.column,
                    resource_id=entry.resource_id,
                    suggestion=_suggest(match.value, rule.values)
                    or Message("suggestion.valid_values", {"values": ", ".join(sorted(rule.values))}),
                )

    @staticmethod
    def _check_ranges(context, entry, ranges, value) -> Iterable[ValidationResult]:
        for pattern, rule in ranges.items():
            for match in iter_matches(value, pattern):
                if isinstance(match.value, bool) or not isinstance(match.value, (int, float)):
                    continue
                problem = rule.check(match.value)
                if problem is None:
                    continue
                position = match.position()
                yield context.result(
                    rule.severity,
                    Code.ENTRY_VALUE_OUT_OF_RANGE,
                    Message(
                        "entry.out_of_range",
                        {"path": match.path, "value": _number(match.value), "problem": problem},
                    ),
                    file=entry.relative_path,
                    line=position.line,
                    column=position.column,
                    resource_id=entry.resource_id,
                    suggestion=Message("suggestion.expected_range", {"range": rule.describe()}),
                )


def _suggest(value: str, candidates):
    """A ``Did you mean ...?`` message, or ``None`` when nothing is close."""
    matches = closest_matches(value, list(candidates))
    return Message("suggestion.did_you_mean", {"value": matches[0]}) if matches else None


def _describe_type(value: Any) -> Message:
    if isinstance(value, bool):
        return Message("type.boolean")
    if isinstance(value, (int, float)):
        return Message("type.number")
    if isinstance(value, str):
        return Message("type.string")
    if isinstance(value, list):
        return Message("type.array")
    if isinstance(value, dict):
        return Message("type.object")
    return Message("type.null")


def _number(value) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)
