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
def _cells(text: str) -> int:
    """How many terminal columns ``text`` occupies.

    ``str.ljust`` counts characters, but a Japanese label such as "命名規則"
    takes two columns per character, so padding by length ragged-edges the
    whole report in the Japanese locale.
    """
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(1, width - _cells(text))


def render_text(
    report: ValidationReport,
    locale: str = "en",
    results: Optional[List[ValidationResult]] = None,
    colour: bool = True,
) -> str:
    lines = []  # type: List[str]
    shown = report.sorted_results() if results is None else results

    # Size the category column to what is actually on screen rather than to a
    # constant, so a run with no Lua findings does not carry a "Luaスクリプト"
    # sized gutter down the whole report.
    width = max([_cells(r.category.label(locale)) for r in shown] or [0]) + 2
    # The code column was ragged before the category column existed; now that
    # the line has two label columns, both need to line up or neither scans.
    code_width = max([len(r.code) for r in shown] or [0]) + 2

    for result in shown:
        marker = _COLOURS.get(result.severity, "") if colour else ""
        reset = _RESET if colour and marker else ""
        lines.append(
            "{}{:<7}{} {}{}{}".format(
                marker,
                result.severity.label,
                reset,
                _pad(result.category.label(locale), width),
                _pad(result.code, code_width),
                result.location,
            )
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

    # What to fix, grouped the way the fixing actually happens: a bare
    # "3 errors" does not tell the author whether to open a JSON file or a
    # .lua one.  Counted over the whole run, like every other number in the
    # summary, so a filtered view still shows what the pack as a whole holds.
    # Only under a listing: with nothing shown -- a clean pack, or --quiet,
    # which reads the last line as the summary -- the counts line is the end
    # of the report.
    breakdown = report.counts_by_category() if shown else {}
    if breakdown:
        lines.append(
            "  " + " / ".join("{} {}".format(c.label(locale), n) for c, n in breakdown.items())
        )
    return "\n".join(lines)
