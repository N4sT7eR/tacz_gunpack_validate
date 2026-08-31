"""The validator interface and its registry.

Adding a check means writing a class and registering it -- no other file needs
to change, which is what keeps the pipeline extensible.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Type

from .context import ValidationContext
from .result import ValidationResult

__all__ = ["Validator", "register", "all_validators", "get_validator"]


class Validator:
    """Base class for every check.

    Subclasses set :attr:`name` (stable, used by ``--disable``) and implement
    :meth:`validate`.  Yielding results as they are found keeps memory flat on
    large packs and lets the GUI stream them into the table.
    """

    #: Stable identifier, e.g. ``"json-syntax"``.
    name = "unnamed"
    #: One-line description, shown by ``--list-validators``.
    description = ""
    #: Lower runs earlier.  Parsing and structure come before cross-references.
    order = 100

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        raise NotImplementedError


_REGISTRY = {}  # type: Dict[str, Type[Validator]]


def register(cls: Type[Validator]) -> Type[Validator]:
    """Class decorator that adds a validator to the pipeline."""
    if cls.name in _REGISTRY:
        raise ValueError("Duplicate validator name: {}".format(cls.name))
    _REGISTRY[cls.name] = cls
    return cls


def all_validators() -> List[Type[Validator]]:
    return sorted(_REGISTRY.values(), key=lambda c: (c.order, c.name))


def get_validator(name: str) -> Type[Validator]:
    return _REGISTRY[name]
