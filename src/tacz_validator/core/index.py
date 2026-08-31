"""A single pass over the gunpack, shared by every validator.

Scanning a pack means touching thousands of files, so it happens exactly once:
:class:`GunpackIndex` reads every path from a :class:`~.source.PackSource`
(a folder or a zip), parses every JSON document, and exposes lookups -- including
a case-sensitive view of a case-insensitive filesystem -- that the validators
query instead of hitting the disk again.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from . import jsonc
from .jsonc import JsonSyntaxError, ParsedDocument, Position
from .source import PackSource

__all__ = ["Entry", "JsonDocument", "GunpackIndex", "ScanProgress"]


class ScanProgress(NamedTuple):
    stage: str
    current: int
    total: int


class JsonDocument(NamedTuple):
    """One parsed (or unparseable) JSON file."""

    relative_path: str
    text: str
    value: object
    issues: List[jsonc.LenientIssue]
    error: Optional[JsonSyntaxError]

    @property
    def ok(self) -> bool:
        return self.error is None


class Entry(NamedTuple):
    """An index/data/display document, addressable as ``namespace:id``."""

    kind: str  # e.g. "gun_index"
    namespace: str
    id: str  # path portion, e.g. "ak47" or "gun/ak47"
    relative_path: str
    document: JsonDocument

    @property
    def resource_id(self) -> str:
        return "{}:{}".format(self.namespace, self.id)


class Cancelled(Exception):
    """Raised inside the scan when the caller asked it to stop."""


class GunpackIndex:
    """Everything discovered about a pack, built once per validation run."""

    def __init__(self, source: PackSource) -> None:
        self.source = source
        self.root = source.origin
        self.display_name = source.display_name
        self.files = set()  # type: Set[str]                 # pack-relative paths
        self.directories = set()  # type: Set[str]
        self._files_by_lower = {}  # type: Dict[str, List[str]]
        self._dir_contents = {}  # type: Dict[str, List[str]] # dir -> file names
        self.json_documents = {}  # type: Dict[str, JsonDocument]
        self.entries = {}  # type: Dict[str, Dict[str, Entry]]  # kind -> resource_id -> Entry
        self.namespaces = set()  # type: Set[str]
        self.asset_namespaces = set()  # type: Set[str]
        self.data_namespaces = set()  # type: Set[str]
        self.meta_namespace = None  # type: Optional[str]
        self.meta_document = None  # type: Optional[JsonDocument]
        self.info_document = None  # type: Optional[JsonDocument]
        self.language_files = {}  # type: Dict[str, Dict[str, JsonDocument]]  # ns -> lang -> doc
        self._position_prefixes = ()  # type: Tuple[str, ...]

    # -- construction --------------------------------------------------------

    @classmethod
    def build(
        cls,
        source: PackSource,
        rule_set,
        progress: Optional[Callable[[ScanProgress], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> "GunpackIndex":
        index = cls(source)
        index._scan_files(progress, is_cancelled)
        index._detect_namespaces()
        index._prepare_position_prefixes(rule_set)
        index._parse_json(progress, is_cancelled)
        index._collect_metadata()
        index._collect_entries(rule_set)
        index._collect_languages(rule_set)
        return index

    def _check_cancelled(self, is_cancelled: Optional[Callable[[], bool]]) -> None:
        if is_cancelled is not None and is_cancelled():
            raise Cancelled()

    def _scan_files(self, progress, is_cancelled) -> None:
        for relative in self.source.paths():
            self._check_cancelled(is_cancelled)
            self.files.add(relative)
            self._files_by_lower.setdefault(relative.lower(), []).append(relative)
            directory, _, name = relative.rpartition("/")
            self._dir_contents.setdefault(directory, []).append(name)
            while directory:
                self.directories.add(directory)
                directory = directory.rpartition("/")[0]
        if progress:
            progress(ScanProgress("scan", len(self.files), len(self.files)))

    def _detect_namespaces(self) -> None:
        for side, bucket in (("assets", self.asset_namespaces), ("data", self.data_namespaces)):
            prefix = side + "/"
            for rel in self.directories:
                if rel.startswith(prefix) and rel.count("/") == 1:
                    bucket.add(rel[len(prefix) :])
        self.namespaces = self.asset_namespaces | self.data_namespaces

    #: Kinds whose contents validators inspect key by key, and which therefore
    #: need source positions.  Everything else (models, animations) is parsed
    #: with the fast path -- see :func:`jsonc.parse_fast`.
    _ALWAYS_POSITIONED = ("lang", "recipe", "recipe_filter", "attachment_tag")

    def _prepare_position_prefixes(self, rule_set) -> None:
        prefixes = []
        wanted = set(rule_set.entries) | set(self._ALWAYS_POSITIONED)
        for kind_name in wanted:
            kind = rule_set.kind(kind_name)
            if kind is None:
                continue
            for namespace in self.namespaces:
                prefixes.append(kind.directory_for(namespace) + "/")
        self._position_prefixes = tuple(sorted(prefixes))

    def _needs_positions(self, relative_path: str) -> bool:
        if "/" not in relative_path:
            return True  # gunpack.meta.json and friends are tiny
        return relative_path.startswith(self._position_prefixes)

    def _parse_json(self, progress, is_cancelled) -> None:
        json_files = sorted(rel for rel in self.files if rel.lower().endswith(".json"))
        total = len(json_files)
        for i, rel in enumerate(json_files):
            self._check_cancelled(is_cancelled)
            self.json_documents[rel] = self._read_json(rel)
            if progress and (i % 50 == 0 or i == total - 1):
                progress(ScanProgress("parse", i + 1, total))

    def _read_json(self, rel: str) -> JsonDocument:
        try:
            text = self.source.read_bytes(rel).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            error = JsonSyntaxError(
                "File is not valid UTF-8 ({})".format(exc.reason), Position(1, 1, 0)
            )
            return JsonDocument(rel, "", None, [], error)
        except (OSError, KeyError) as exc:  # pragma: no cover - unreadable file
            error = JsonSyntaxError("Cannot read file: {}".format(exc), Position(1, 1, 0))
            return JsonDocument(rel, "", None, [], error)
        try:
            if self._needs_positions(rel):
                parsed = jsonc.parse(text)  # type: ParsedDocument
            else:
                parsed = jsonc.parse_fast(text)
        except JsonSyntaxError as exc:
            return JsonDocument(rel, text, None, [], exc)
        return JsonDocument(rel, text, parsed.value, list(parsed.issues), None)

    #: The pack's identity lives in these two files: the namespace it claims,
    #: and the metadata the in-game gun smith table shows.
    META_FILE = "gunpack.meta.json"
    INFO_FILE = "gunpack_info.json"

    def _collect_metadata(self) -> None:
        self.meta_document = self.json_documents.get(self.META_FILE)
        if self.meta_document is not None and isinstance(self.meta_document.value, dict):
            namespace = self.meta_document.value.get("namespace")
            if isinstance(namespace, str):
                self.meta_namespace = namespace
        for namespace in sorted(self.asset_namespaces):
            rel = "assets/{}/{}".format(namespace, self.INFO_FILE)
            if rel in self.json_documents:
                self.info_document = self.json_documents[rel]
                break

    def _collect_entries(self, rule_set) -> None:
        for kind_name, kind in rule_set.resource_kinds.items():
            if kind_name not in rule_set.entries:
                continue
            bucket = self.entries.setdefault(kind_name, {})
            for namespace in sorted(self.namespaces):
                directory = kind.directory_for(namespace)
                for rel in self._json_files_under(directory):
                    resource_path = rel[len(directory) + 1 :]
                    for ext in kind.extensions:
                        if resource_path.endswith(ext):
                            resource_path = resource_path[: -len(ext)]
                            break
                    entry = Entry(
                        kind=kind_name,
                        namespace=namespace,
                        id=resource_path,
                        relative_path=rel,
                        document=self.json_documents[rel],
                    )
                    bucket[entry.resource_id] = entry

    def _json_files_under(self, directory: str) -> List[str]:
        prefix = directory + "/"
        return sorted(rel for rel in self.json_documents if rel.startswith(prefix))

    def _collect_languages(self, rule_set) -> None:
        kind = rule_set.kind("lang")
        if kind is None:
            return
        for namespace in sorted(self.namespaces):
            directory = kind.directory_for(namespace)
            for rel in self._json_files_under(directory):
                name = rel[len(directory) + 1 :]
                if name.endswith(".json"):
                    name = name[: -len(".json")]
                self.language_files.setdefault(namespace, {})[name] = self.json_documents[rel]

    # -- lookups -------------------------------------------------------------

    def exists(self, relative_path: str) -> bool:
        return relative_path in self.files

    def case_insensitive_matches(self, relative_path: str) -> List[str]:
        """Files whose path differs from ``relative_path`` only by letter case.

        Windows would happily load these; Minecraft, which treats resource paths
        as case-sensitive, would not -- which is exactly the bug worth reporting.
        """
        return [p for p in self._files_by_lower.get(relative_path.lower(), []) if p != relative_path]

    def files_in(self, directory: str) -> List[str]:
        return list(self._dir_contents.get(directory, []))

    def has_prefix_match(self, directory: str, stem: str, extension: str) -> bool:
        """Whether any file in ``directory`` starts with ``stem`` + ``_``.

        TaCZ sound references are sometimes a prefix shared by several files
        (``ak47_reload_empty`` -> ``ak47_reload_empty_magout.ogg``), so an exact
        miss is not automatically a broken reference.
        """
        needle = stem + "_"
        for name in self._dir_contents.get(directory, []):
            if name.startswith(needle) and name.lower().endswith(extension):
                return True
        return False

    def entry(self, kind: str, resource_id: str) -> Optional[Entry]:
        return self.entries.get(kind, {}).get(resource_id)

    def entries_of(self, kind: str) -> List[Entry]:
        return list(self.entries.get(kind, {}).values())

    def entry_ids(self, kind: str) -> List[str]:
        return sorted(self.entries.get(kind, {}))

    def documents(self) -> Iterable[JsonDocument]:
        return self.json_documents.values()

    @property
    def json_file_count(self) -> int:
        return len(self.json_documents)

    @property
    def file_count(self) -> int:
        return len(self.files)
