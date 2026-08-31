"""Layers 5-6: every ``namespace:path`` must resolve to a file that exists.

This is where the tool earns its keep.  A typo in a reference costs nothing at
pack-build time and shows up in game as a missing model, a silent gun, or a
crash on the first shot.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.paths import iter_matches
from ..core.references import ReferenceStatus, resolve
from ..core.resource_location import closest_matches
from ..core.result import Code, Severity, ValidationResult
from ..core.validator import Validator, register

#: Sound references double as filename prefixes for multi-part sound sets, and
#: TaCZ substitutes defaults for several of them, so a miss is not fatal.
_SOFT_KINDS = {"sound"}
#: Level-of-detail models are optional extras: TaCZ falls back to the full model,
#: and the official pack itself ships several broken lod references.
_SOFT_PATTERNS = ("lod.",)


@register
class CrossReferenceValidator(Validator):
    name = "references"
    description = "Resolve every resource reference to a file in the pack"
    order = 50

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        for kind in sorted(context.index.entries):
            references = context.rules.entry(kind).get("references", {})
            if not references:
                continue
            for entry in context.index.entries_of(kind):
                document = entry.document
                if document.error is not None or not isinstance(document.value, dict):
                    continue
                for pattern, target_kind in sorted(references.items()):
                    soft = target_kind in _SOFT_KINDS or pattern.startswith(_SOFT_PATTERNS)
                    for match in iter_matches(document.value, pattern):
                        yield from self._check(context, entry, match, target_kind, soft)

    def _check(self, context, entry, match, target_kind, soft) -> Iterable[ValidationResult]:
        # TaCZ documents many of these fields as "may be empty", and an empty
        # string means "not set" rather than a reference to nothing.
        if isinstance(match.value, str) and not match.value.strip():
            return
        resolution = resolve(context, target_kind, match.value)
        position = match.position()
        common = dict(
            file=entry.relative_path,
            line=position.line,
            column=position.column,
            resource_id=entry.resource_id,
        )

        if resolution.namespace_omitted and resolution.status is not ReferenceStatus.MALFORMED:
            namespace = resolution.location.namespace if resolution.location else ""
            yield context.info(
                Code.ID_NAMESPACE_OMITTED,
                Message(
                    "ref.namespace_omitted",
                    {"value": resolution.raw, "namespace": namespace},
                ),
                suggestion=Message(
                    "suggestion.use_instead",
                    {"value": "{}:{}".format(namespace, resolution.raw)},
                ),
                **common
            )

        status = resolution.status
        if status in (ReferenceStatus.FOUND, ReferenceStatus.PREFIX_MATCH, ReferenceStatus.EXTERNAL_KNOWN):
            return

        if status is ReferenceStatus.MALFORMED:
            yield context.error(
                Code.ID_MALFORMED,
                Message("ref.malformed", {"value": repr(resolution.raw), "detail": resolution.detail}),
                **common
            )
            return

        if status is ReferenceStatus.CASE_MISMATCH:
            yield context.error(
                Code.REF_CASE_MISMATCH,
                Message(
                    "ref.case_mismatch",
                    {"value": resolution.raw, "actual": resolution.actual_path},
                ),
                suggestion=Message(
                    "suggestion.rename_file",
                    {"value": (resolution.expected_paths or [""])[0].rsplit("/", 1)[-1]},
                ),
                **common
            )
            return

        if status is ReferenceStatus.EXTERNAL_MISSING:
            yield context.info(
                Code.REF_EXTERNAL_UNKNOWN,
                Message(
                    "ref.external_missing",
                    {
                        "value": resolution.raw,
                        "namespace": resolution.location.namespace if resolution.location else "",
                    },
                ),
                **common
            )
            return

        if status is ReferenceStatus.EXTERNAL_UNKNOWN:
            if not context.settings.report_unknown_external:
                return
            yield context.info(
                Code.REF_EXTERNAL_UNKNOWN,
                Message(
                    "ref.external_unknown",
                    {
                        "value": resolution.raw,
                        "namespace": resolution.location.namespace if resolution.location else "",
                    },
                ),
                **common
            )
            return

        # ReferenceStatus.MISSING
        yield context.result(
            Severity.WARNING if soft else Severity.ERROR,
            Code.REF_SOUND_MISSING if target_kind in _SOFT_KINDS else Code.REF_MISSING,
            Message(
                "ref.missing",
                {"kind": Message("kind." + target_kind), "value": resolution.raw},
            ),
            suggestion=self._suggest(context, target_kind, resolution),
            **common
        )

    @staticmethod
    def _suggest(context, target_kind, resolution) -> Optional[Message]:
        """Point at a near-miss id when there is one, otherwise at the path."""
        if resolution.location is not None and target_kind in context.index.entries:
            candidates = context.index.entry_ids(target_kind)
            near = closest_matches(str(resolution.location), candidates)
            if near:
                return Message("suggestion.did_you_mean", {"value": near[0]})
        if resolution.expected_paths:
            return Message("suggestion.expected_path", {"path": resolution.expected_paths[0]})
        return None
