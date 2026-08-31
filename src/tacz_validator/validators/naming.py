"""Layer 4: namespaces, resource ids and filenames must be lowercase and legal.

This is where most real breakage starts.  Windows happily stores ``M4A1.png``
and loads it through a reference spelled ``m4a1``, so a pack can work on the
author's machine and fail for everyone else -- or fail to register at all,
because Minecraft rejects an identifier with a capital letter outright.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.resource_location import (
    ResourceLocation,
    describe_characters,
    invalid_characters,
    suggest_identifier,
)
from ..core.result import Code, ValidationResult
from ..core.validator import Validator, register

#: Directories whose filenames become part of a resource path.
_ASSET_DIRECTORIES = ("textures", "geo_models", "animations", "tacz_sounds", "scripts", "player_animator")


@register
class NamingValidator(Validator):
    name = "naming"
    description = "Namespace, resource id and filename rules (uppercase, spaces, symbols)"
    order = 30

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        yield from self._check_namespaces(context)
        yield from self._check_entry_ids(context)
        yield from self._check_asset_filenames(context)
        yield from self._check_language_filenames(context)

    def _check_namespaces(self, context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index
        for namespace in sorted(index.namespaces | ({index.meta_namespace} if index.meta_namespace else set())):
            bad = invalid_characters(namespace, allow_slash=False)
            if not bad:
                continue
            suggestion = suggest_identifier(namespace, allow_slash=False)
            reason = self._reason(namespace, bad)
            yield context.error(
                Code.ID_INVALID_NAMESPACE,
                Message("naming.invalid_namespace", {"value": repr(namespace), "reason": reason}),
                file=index.META_FILE if namespace == index.meta_namespace else None,
                resource_id=namespace,
                suggestion=Message("suggestion.use_instead", {"value": suggestion}),
            )

    def _check_entry_ids(self, context: ValidationContext) -> Iterable[ValidationResult]:
        for kind in sorted(context.index.entries):
            for entry in context.index.entries_of(kind):
                bad = invalid_characters(entry.id, allow_slash=True)
                if not bad:
                    continue
                code = (
                    Code.ID_UPPERCASE
                    if all(ch.isalpha() and ch.isupper() for ch in bad)
                    else Code.ID_INVALID_PATH
                )
                suggested = suggest_identifier(entry.id, allow_slash=True)
                yield context.error(
                    code,
                    Message(
                        "naming.invalid_id",
                        {"value": repr(entry.resource_id), "reason": self._reason(entry.id, bad)},
                    ),
                    file=entry.relative_path,
                    resource_id=entry.resource_id,
                    suggestion=Message(
                        "suggestion.rename_id",
                        {"value": "{}:{}".format(entry.namespace, suggested)},
                    ),
                )

    def _check_asset_filenames(self, context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index
        for namespace in sorted(index.namespaces):
            for directory in _ASSET_DIRECTORIES:
                prefix = "assets/{}/{}/".format(namespace, directory)
                for relative in sorted(p for p in index.files if p.startswith(prefix)):
                    name = relative.rsplit("/", 1)[-1]
                    stem = name.split(".", 1)[0]
                    bad = invalid_characters(stem, allow_slash=False)
                    if not bad:
                        continue
                    # A name made entirely of non-ASCII characters has no sensible
                    # automatic rewrite, so offer no suggestion rather than a bad one.
                    suggested = suggest_identifier(stem, allow_slash=False)
                    usable = suggested not in ("unnamed", "") and any(c.isalnum() for c in suggested)
                    yield context.warning(
                        Code.ID_FILENAME_INVALID,
                        Message(
                            "naming.invalid_filename",
                            {"value": repr(name), "reason": self._reason(stem, bad)},
                        ),
                        file=relative,
                        suggestion=Message(
                            "suggestion.rename_file",
                            {"value": suggested + name[len(stem) :]},
                        )
                        if usable
                        else None,
                    )

    def _check_language_filenames(self, context: ValidationContext) -> Iterable[ValidationResult]:
        pattern = context.rules.language_files.get("pattern")
        if not pattern:
            return
        matcher = re.compile(pattern)
        for namespace, languages in sorted(context.index.language_files.items()):
            for name in sorted(languages):
                if matcher.match(name):
                    continue
                yield context.warning(
                    Code.LANG_FILENAME_INVALID,
                    Message("naming.lang_filename", {"value": name + ".json"}),
                    file=languages[name].relative_path,
                    suggestion=Message(
                        "suggestion.rename_file",
                        {"value": suggest_identifier(name, allow_slash=False) + ".json"},
                    ),
                )

    @staticmethod
    def _reason(value: str, bad_characters) -> Message:
        bad = list(bad_characters)
        if all(ch.isalpha() and ch.isupper() for ch in bad):
            return Message("reason.uppercase")
        return Message("reason.characters", {"characters": describe_characters(bad)})
