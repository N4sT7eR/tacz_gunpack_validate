"""Reading a pack from a folder or straight out of a .zip.

Gunpacks are distributed as zip archives, and asking users to unpack one before
checking it is exactly the friction this tool exists to remove.  Both forms are
exposed through the same interface, so nothing above this module knows or cares
which one it is looking at.
"""

from __future__ import annotations

import os
import zipfile
from typing import Dict, Iterable, List

__all__ = ["PackSource", "DirectorySource", "ZipSource", "open_source", "PackSourceError"]

#: The file that marks the root of a pack.
ROOT_MARKER = "gunpack.meta.json"
#: Directories that must sit next to it.
ROOT_SIBLINGS = ("assets/", "data/")

_IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
_IGNORED_DIRECTORIES = {".git", "__MACOSX"}


class PackSourceError(Exception):
    """The path is not something we can read a pack out of."""


class PackSource:
    """A read-only, flat view of a pack: relative POSIX paths to bytes."""

    #: What to show the user (a folder name or the zip's filename).
    display_name = ""
    #: Absolute path of the folder or archive on disk.
    origin = ""
    #: Prefix stripped from every path, when the pack sits inside a subfolder.
    root_prefix = ""

    def paths(self) -> List[str]:
        raise NotImplementedError

    def read_bytes(self, relative_path: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "PackSource":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _detect_root_prefix(paths: Iterable[str]) -> str:
    """Find the folder holding ``gunpack.meta.json``, if it is not the top one.

    Archives are commonly zipped one level up, so the interesting content sits
    under ``MyPack-1.0/``.  Rather than telling the user off, we just descend.
    """
    candidates = [p for p in paths if p.endswith(ROOT_MARKER)]
    if not candidates:
        return ""
    candidates.sort(key=lambda p: p.count("/"))
    best = candidates[0]
    return best[: -len(ROOT_MARKER)]


class DirectorySource(PackSource):
    def __init__(self, root: str) -> None:
        if not os.path.isdir(root):
            raise PackSourceError("Not a directory: {}".format(root))
        self.origin = os.path.abspath(root)
        self.display_name = os.path.basename(self.origin.rstrip(os.sep)) or self.origin
        self._paths = self._walk()
        self.root_prefix = _detect_root_prefix(self._paths)
        if self.root_prefix:
            self._paths = [
                p[len(self.root_prefix) :] for p in self._paths if p.startswith(self.root_prefix)
            ]

    def _walk(self) -> List[str]:
        collected = []  # type: List[str]
        for dirpath, dirnames, filenames in os.walk(self.origin):
            dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRECTORIES]
            relative_dir = os.path.relpath(dirpath, self.origin).replace(os.sep, "/")
            if relative_dir == ".":
                relative_dir = ""
            for name in filenames:
                if name in _IGNORED_NAMES:
                    continue
                collected.append("{}/{}".format(relative_dir, name) if relative_dir else name)
        return collected

    def paths(self) -> List[str]:
        return list(self._paths)

    def read_bytes(self, relative_path: str) -> bytes:
        absolute = os.path.join(self.origin, *(self.root_prefix + relative_path).split("/"))
        with open(absolute, "rb") as handle:
            return handle.read()


class ZipSource(PackSource):
    """A pack read directly from its distribution archive."""

    def __init__(self, archive_path: str) -> None:
        if not os.path.isfile(archive_path):
            raise PackSourceError("Not a file: {}".format(archive_path))
        self.origin = os.path.abspath(archive_path)
        self.display_name = os.path.basename(self.origin)
        try:
            self._zip = zipfile.ZipFile(self.origin)
        except (zipfile.BadZipFile, OSError) as exc:
            raise PackSourceError("Cannot open archive: {}".format(exc))
        self._members = {}  # type: Dict[str, str]
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            if any(part in _IGNORED_DIRECTORIES for part in parts[:-1]):
                continue
            if parts[-1] in _IGNORED_NAMES:
                continue
            self._members[name] = info.filename
        self.root_prefix = _detect_root_prefix(self._members)
        if self.root_prefix:
            self._members = {
                name[len(self.root_prefix) :]: original
                for name, original in self._members.items()
                if name.startswith(self.root_prefix)
            }

    def paths(self) -> List[str]:
        return list(self._members)

    def read_bytes(self, relative_path: str) -> bytes:
        member = self._members.get(relative_path)
        if member is None:
            raise KeyError(relative_path)
        return self._zip.read(member)

    def close(self) -> None:
        self._zip.close()


def open_source(path: str) -> PackSource:
    """Open ``path`` as a pack, whether it is a folder or a ``.zip``."""
    if os.path.isdir(path):
        return DirectorySource(path)
    if os.path.isfile(path):
        if zipfile.is_zipfile(path):
            return ZipSource(path)
        raise PackSourceError(
            "{} is a file but not a zip archive. Select the gunpack folder or its .zip.".format(
                os.path.basename(path)
            )
        )
    raise PackSourceError("Path does not exist: {}".format(path))
