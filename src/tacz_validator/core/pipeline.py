"""Running the whole validation, in the order the layers depend on each other."""

from __future__ import annotations

import time
from typing import Callable, NamedTuple, Optional

from .. import rules as rules_module
from .context import ValidationContext, ValidatorSettings
from .index import Cancelled, GunpackIndex, ScanProgress
from .result import ValidationReport
from .source import PackSource, open_source
from .validator import Validator, all_validators

__all__ = ["Progress", "validate", "validate_source"]


class Progress(NamedTuple):
    """Where the run is, for a progress bar and a status line."""

    stage: str  # "scan" | "parse" | validator name | "done"
    current: int
    total: int

    @property
    def fraction(self) -> float:
        return (self.current / self.total) if self.total else 0.0


def validate(
    path: str,
    settings: Optional[ValidatorSettings] = None,
    progress: Optional[Callable[[Progress], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ValidationReport:
    """Validate the pack at ``path``, which may be a folder or a ``.zip``."""
    with open_source(path) as source:
        return validate_source(source, settings, progress, is_cancelled)


def validate_source(
    source: PackSource,
    settings: Optional[ValidatorSettings] = None,
    progress: Optional[Callable[[Progress], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ValidationReport:
    settings = settings or ValidatorSettings()
    rule_set = rules_module.load(settings.version)
    started = time.time()
    report = ValidationReport(root=source.origin)

    def forward(scan: ScanProgress) -> None:
        if progress:
            progress(Progress(scan.stage, scan.current, scan.total))

    try:
        index = GunpackIndex.build(source, rule_set, progress=forward, is_cancelled=is_cancelled)
    except Cancelled:
        report.cancelled = True
        report.duration_seconds = time.time() - started
        return report

    report.scanned_files = index.file_count
    context = ValidationContext(index, rule_set, settings)
    selected = [
        cls for cls in all_validators() if cls.name not in settings.disabled_validators
    ]

    for position, validator_class in enumerate(selected, start=1):
        if is_cancelled is not None and is_cancelled():
            report.cancelled = True
            break
        if progress:
            progress(Progress(validator_class.name, position, len(selected)))
        validator = validator_class()  # type: Validator
        context._current_validator = validator.name
        try:
            report.extend(validator.validate(context))
        except Cancelled:
            report.cancelled = True
            break
    context._current_validator = None

    if progress:
        progress(Progress("done", len(selected), len(selected)))
    report.duration_seconds = time.time() - started
    return report
