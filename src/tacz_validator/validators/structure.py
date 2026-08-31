"""Layer 3: does this folder look like a gunpack at all?"""

from __future__ import annotations

from typing import Iterable, Set

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.result import Code, ValidationResult
from ..core.validator import Validator, register

#: Directories TaCZ reads.  Anything else under a namespace is inert, which is
#: worth mentioning but never an error -- packs ship readmes and spare art.
_KNOWN_DIRECTORIES = {
    "assets": {
        "display", "geo_models", "textures", "animations", "tacz_sounds",
        "scripts", "player_animator", "lang", "sounds", "models",
    },
    "data": {
        "index", "data", "recipes", "recipe_filters", "tacz_tags",
        "tacz_loot_injectors", "scripts",
    },
}


@register
class PackStructureValidator(Validator):
    name = "pack-structure"
    description = "gunpack.meta.json, namespace declaration and top-level layout"
    order = 20

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index

        if index.meta_document is None:
            yield context.error(
                Code.PACK_META_MISSING,
                Message("pack.meta_missing"),
                file=index.META_FILE,
                suggestion=Message("suggestion.create_meta"),
            )
        elif index.meta_document.error is None:
            if not isinstance(index.meta_document.value, dict):
                yield context.error(
                    Code.JSON_ROOT_NOT_OBJECT,
                    Message("pack.meta_not_object"),
                    file=index.META_FILE,
                )
            elif index.meta_namespace is None:
                yield context.error(
                    Code.PACK_META_NAMESPACE_MISSING,
                    Message("pack.namespace_missing"),
                    file=index.META_FILE,
                )

        if not index.namespaces:
            yield context.error(
                Code.PACK_NO_CONTENT,
                Message("pack.no_content"),
                suggestion=Message("suggestion.pack_layout"),
            )
            return

        yield from self._check_namespace_consistency(context)
        yield from self._check_pack_info(context)
        yield from self._check_directories(context)

    @staticmethod
    def _check_namespace_consistency(context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index
        declared = index.meta_namespace
        if declared is None:
            return
        if declared not in index.namespaces:
            yield context.error(
                Code.PACK_NAMESPACE_MISMATCH,
                Message("pack.namespace_dir_missing", {"namespace": declared}),
                file=index.META_FILE,
                resource_id=declared,
                suggestion=Message(
                    "suggestion.found_namespaces", {"found": ", ".join(sorted(index.namespaces))}
                ),
            )
        for namespace in sorted(index.namespaces - {declared}):
            yield context.warning(
                Code.PACK_NAMESPACE_MISMATCH,
                Message("pack.namespace_extra", {"namespace": namespace, "declared": declared}),
                resource_id=namespace,
                suggestion=Message("suggestion.declare_namespace", {"declared": declared}),
            )

    @staticmethod
    def _check_pack_info(context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index
        if index.info_document is not None:
            return
        namespace = index.meta_namespace or sorted(index.namespaces)[0]
        yield context.warning(
            Code.PACK_INFO_MISSING,
            Message("pack.info_missing"),
            file="assets/{}/{}".format(namespace, index.INFO_FILE),
        )

    @staticmethod
    def _check_directories(context: ValidationContext) -> Iterable[ValidationResult]:
        index = context.index
        for side, known in sorted(_KNOWN_DIRECTORIES.items()):
            for namespace in sorted(index.namespaces):
                prefix = "{}/{}/".format(side, namespace)
                seen = set()  # type: Set[str]
                for directory in index.directories:
                    if directory.startswith(prefix):
                        seen.add(directory[len(prefix) :].split("/", 1)[0])
                for name in sorted(seen - known):
                    yield context.info(
                        Code.PACK_UNKNOWN_DIRECTORY,
                        Message("pack.unknown_directory", {"path": prefix + name}),
                        file="{}{}".format(prefix, name),
                    )
