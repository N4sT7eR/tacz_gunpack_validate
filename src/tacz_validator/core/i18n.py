"""Message catalogue for the English and Japanese user interfaces.

Findings are produced as a key plus parameters rather than as a finished string,
so the same report can be re-rendered when the user switches language without
re-running the validation.  Nested :class:`Message` parameters let a sentence
embed a translated fragment ("contains uppercase characters", "1 - 1200").
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, NamedTuple, Optional

__all__ = ["Message", "DEFAULT_LOCALE", "supported_locales", "render", "locale_display_name"]

_LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")

DEFAULT_LOCALE = "en"
_LOCALE_NAMES = {"en": "English", "ja": "日本語"}

_catalogues = {}  # type: Dict[str, Dict[str, str]]


class Message(NamedTuple):
    """A translatable sentence: a catalogue key plus its parameters."""

    key: str
    params: Dict[str, Any] = {}

    def render(self, locale: str = DEFAULT_LOCALE) -> str:
        return render(self, locale)


def supported_locales() -> List[str]:
    if not os.path.isdir(_LOCALE_DIR):
        return [DEFAULT_LOCALE]
    return sorted(
        name[: -len(".json")] for name in os.listdir(_LOCALE_DIR) if name.endswith(".json")
    )


def locale_display_name(locale: str) -> str:
    return _LOCALE_NAMES.get(locale, locale)


def catalogue(locale: str) -> Dict[str, str]:
    if locale not in _catalogues:
        path = os.path.join(_LOCALE_DIR, "{}.json".format(locale))
        if not os.path.isfile(path):
            _catalogues[locale] = {}
        else:
            with open(path, encoding="utf-8") as handle:
                _catalogues[locale] = json.load(handle)
    return _catalogues[locale]


def render(message: Optional[Message], locale: str = DEFAULT_LOCALE) -> str:
    """Render ``message`` in ``locale``, falling back to English then to the key.

    A missing translation must never lose information, so an untranslated key
    still produces the English sentence rather than an empty cell in the report.
    """
    if message is None:
        return ""
    if isinstance(message, str):  # tolerate plain strings from ad-hoc callers
        return message
    template = catalogue(locale).get(message.key)
    if template is None and locale != DEFAULT_LOCALE:
        template = catalogue(DEFAULT_LOCALE).get(message.key)
    if template is None:
        return "{}({})".format(message.key, _describe_params(message.params, locale))
    params = {
        name: render(value, locale) if isinstance(value, Message) else value
        for name, value in (message.params or {}).items()
    }
    try:
        return template.format(**params)
    except (KeyError, IndexError):  # pragma: no cover - malformed catalogue entry
        return template


def _describe_params(params: Optional[Dict[str, Any]], locale: str) -> str:
    if not params:
        return ""
    return ", ".join(
        "{}={}".format(k, render(v, locale) if isinstance(v, Message) else v)
        for k, v in sorted(params.items())
    )


def join(values: Iterable[str]) -> str:
    return ", ".join(str(v) for v in values)
