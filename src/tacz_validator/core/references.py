"""Turning a ``namespace:path`` reference into a file on disk -- or a verdict."""

from __future__ import annotations

import enum
from typing import List, NamedTuple, Optional

from .context import ValidationContext
from .resource_location import MalformedResourceLocation, ResourceLocation

__all__ = ["ReferenceStatus", "Resolution", "resolve"]


class ReferenceStatus(enum.Enum):
    FOUND = "found"
    #: The file exists but under different letter case.  Windows loads it,
    #: Minecraft does not.
    CASE_MISMATCH = "case_mismatch"
    #: No exact file, but siblings share the reference as a prefix -- how TaCZ
    #: sound sets are usually laid out.
    PREFIX_MATCH = "prefix_match"
    MISSING = "missing"
    #: Points at a namespace this pack does not own; another pack may provide it.
    EXTERNAL_KNOWN = "external_known"
    EXTERNAL_UNKNOWN = "external_unknown"
    #: Inside a namespace the pack only partly ships -- a pack that adds one
    #: file under assets/tacz/ still relies on TaCZ for everything else there.
    EXTERNAL_MISSING = "external_missing"
    #: Not shaped like an identifier at all.
    MALFORMED = "malformed"


class Resolution(NamedTuple):
    status: ReferenceStatus
    raw: str
    location: Optional[ResourceLocation]
    expected_paths: List[str]
    actual_path: Optional[str] = None
    detail: str = ""
    namespace_omitted: bool = False

    @property
    def ok(self) -> bool:
        return self.status in (ReferenceStatus.FOUND, ReferenceStatus.PREFIX_MATCH)


def resolve(context: ValidationContext, kind_name: str, raw: object) -> Resolution:
    """Resolve ``raw`` as a reference to a resource of kind ``kind_name``."""
    kind = context.rules.kind(kind_name)
    if kind is None:
        raise KeyError("Unknown resource kind: {}".format(kind_name))

    if not isinstance(raw, str):
        return Resolution(
            ReferenceStatus.MALFORMED,
            str(raw),
            None,
            [],
            detail="expected a string identifier, got {}".format(type(raw).__name__),
        )

    namespace_omitted = ":" not in raw
    default_namespace = context.primary_namespace or context.rules.default_namespace
    try:
        location = ResourceLocation.parse(raw, default_namespace=default_namespace)
    except MalformedResourceLocation as exc:
        return Resolution(ReferenceStatus.MALFORMED, raw, None, [], detail=str(exc))

    if not context.is_internal(location.namespace):
        status = (
            ReferenceStatus.EXTERNAL_KNOWN
            if context.is_known_external(location.namespace)
            else ReferenceStatus.EXTERNAL_UNKNOWN
        )
        return Resolution(status, raw, location, [], namespace_omitted=namespace_omitted)

    candidates = kind.relative_paths(location.namespace, location.path)
    index = context.index
    for candidate in candidates:
        if index.exists(candidate):
            return Resolution(
                ReferenceStatus.FOUND,
                raw,
                location,
                candidates,
                actual_path=candidate,
                namespace_omitted=namespace_omitted,
            )

    for candidate in candidates:
        matches = index.case_insensitive_matches(candidate)
        if matches:
            return Resolution(
                ReferenceStatus.CASE_MISMATCH,
                raw,
                location,
                candidates,
                actual_path=matches[0],
                namespace_omitted=namespace_omitted,
            )

    if kind.prefix_match:
        directory = kind.directory_for(location.namespace)
        stem = location.path
        if "/" in stem:
            sub, stem = stem.rsplit("/", 1)
            directory = "{}/{}".format(directory, sub)
        for extension in kind.extensions:
            if index.has_prefix_match(directory, stem, extension):
                return Resolution(
                    ReferenceStatus.PREFIX_MATCH,
                    raw,
                    location,
                    candidates,
                    detail="matched as a filename prefix in {}".format(directory),
                    namespace_omitted=namespace_omitted,
                )

    status = (
        ReferenceStatus.EXTERNAL_MISSING
        if context.is_known_external(location.namespace)
        else ReferenceStatus.MISSING
    )
    return Resolution(status, raw, location, candidates, namespace_omitted=namespace_omitted)
