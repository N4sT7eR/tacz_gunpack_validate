"""TaCZ Gunpack Validator -- checks a TaCZ gunpack without launching Minecraft."""

from __future__ import annotations

__version__ = "0.11.0"

from .core.context import ValidatorSettings  # noqa: E402
from .core.pipeline import Progress, validate, validate_source  # noqa: E402
from .core.result import Code, Severity, ValidationReport, ValidationResult  # noqa: E402
from . import validators as _validators  # noqa: E402,F401  (registers the built-ins)

__all__ = [
    "__version__",
    "Code",
    "Progress",
    "Severity",
    "ValidationReport",
    "ValidationResult",
    "ValidatorSettings",
    "validate",
    "validate_source",
]
