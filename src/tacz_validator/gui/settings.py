"""User preferences that survive a restart.

The language rule the tool follows: pick the OS language the first time, then
remember whatever the user chose, for good.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QLocale, QSettings

from ..core.i18n import DEFAULT_LOCALE, supported_locales

ORGANISATION = "tacz_gunpack_validate"
APPLICATION = "TaCZValidator"

_KEY_LANGUAGE = "language"
_KEY_OUTPUT_DIR = "output_directory"
_KEY_LAST_PACK = "last_pack"
_KEY_VERSION = "tacz_version"
_KEY_SEVERITIES = "visible_severities"
_KEY_CATEGORY = "visible_category"
_KEY_GEOMETRY = "window_geometry"


class UserSettings:
    def __init__(self) -> None:
        self._store = QSettings(ORGANISATION, APPLICATION)

    # -- language ------------------------------------------------------------

    def language(self) -> str:
        """The stored choice, or the OS language on first launch."""
        stored = self._store.value(_KEY_LANGUAGE)
        if isinstance(stored, str) and stored in supported_locales():
            return stored
        return detect_system_language()

    def set_language(self, locale: str) -> None:
        self._store.setValue(_KEY_LANGUAGE, locale)

    @property
    def language_was_chosen(self) -> bool:
        return isinstance(self._store.value(_KEY_LANGUAGE), str)

    # -- paths ---------------------------------------------------------------

    def output_directory(self) -> str:
        value = self._store.value(_KEY_OUTPUT_DIR)
        return value if isinstance(value, str) else ""

    def set_output_directory(self, path: str) -> None:
        self._store.setValue(_KEY_OUTPUT_DIR, path)

    def last_pack(self) -> str:
        value = self._store.value(_KEY_LAST_PACK)
        return value if isinstance(value, str) else ""

    def set_last_pack(self, path: str) -> None:
        self._store.setValue(_KEY_LAST_PACK, path)

    # -- validation options --------------------------------------------------

    def tacz_version(self, default: str) -> str:
        value = self._store.value(_KEY_VERSION)
        return value if isinstance(value, str) else default

    def set_tacz_version(self, version: str) -> None:
        self._store.setValue(_KEY_VERSION, version)

    def visible_severities(self) -> Optional[List[str]]:
        value = self._store.value(_KEY_SEVERITIES)
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list) and value:
            return [str(v) for v in value]
        return None

    def set_visible_severities(self, names: List[str]) -> None:
        self._store.setValue(_KEY_SEVERITIES, names)

    def visible_category(self) -> str:
        """The remembered category value, or "" for "every category"."""
        value = self._store.value(_KEY_CATEGORY)
        return value if isinstance(value, str) else ""

    def set_visible_category(self, value: str) -> None:
        self._store.setValue(_KEY_CATEGORY, value)

    # -- window --------------------------------------------------------------

    def geometry(self):
        return self._store.value(_KEY_GEOMETRY)

    def set_geometry(self, value) -> None:
        self._store.setValue(_KEY_GEOMETRY, value)


def detect_system_language() -> str:
    """Map the OS locale onto a language we ship, defaulting to English."""
    name = QLocale.system().name()  # e.g. "ja_JP"
    language = name.split("_", 1)[0].lower()
    return language if language in supported_locales() else DEFAULT_LOCALE
