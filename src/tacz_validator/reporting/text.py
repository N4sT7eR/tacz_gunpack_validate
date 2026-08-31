"""Console output: one block per finding, in the order they should be fixed."""

from __future__ import annotations

from typing import List, Optional

from ..core.result import Severity, ValidationReport, ValidationResult

_COLOURS = {
    Severity.ERROR: "\033[31m",
    Severity.WARNING: "\033[33m",
    Severity.INFO: "\033[36m",
}
_RESET = "\033[0m"

_SUMMARY = {
    "en": "{errors} errors, {warnings} warnings, {infos} notes  ({files} files in {seconds:.2f}s)",
    "ja": "エラー {errors} 件、警告 {warnings} 件、情報 {infos} 件  （{files} ファイル / {seconds:.2f} 秒）",
}
_CLEAN = {"en": "No problems found.", "ja": "問題は見つかりませんでした。"}
_SUGGESTION_PREFIX = {"en": "  -> ", "ja": "  → "}


def render_text(
    report: ValidationReport,
    locale: str = "en",
    results: Optional[List[ValidationResult]] = None,
    colour: bool = True,
) -> str:
    lines = []  # type: List[str]
    shown = report.sorted_results() if results is None else results

    for result in shown:
        marker = _COLOURS.get(result.severity, "") if colour else ""
        reset = _RESET if colour and marker else ""
        lines.append(
            "{}{:<7}{} {}  {}".format(marker, result.severity.label, reset, result.code, result.location)
        )
        lines.append("  {}".format(result.text(locale)))
        suggestion = result.suggestion_text(locale)
        if suggestion:
            lines.append("{}{}".format(_SUGGESTION_PREFIX.get(locale, "  -> "), suggestion))
        lines.append("")

    if not shown:
        lines.append(_CLEAN.get(locale, _CLEAN["en"]))
        lines.append("")

    lines.append(
        _SUMMARY.get(locale, _SUMMARY["en"]).format(
            errors=report.errors,
            warnings=report.warnings,
            infos=report.infos,
            files=report.scanned_files,
            seconds=report.duration_seconds,
        )
    )
    return "\n".join(lines)
