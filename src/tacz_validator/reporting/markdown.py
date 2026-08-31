"""Markdown export, for pasting into an issue or a pull request."""

from __future__ import annotations

import os
from typing import List, Optional

from ..core.result import Severity, ValidationReport, ValidationResult

_TEXT = {
    "en": {
        "title": "# TaCZ Gunpack Validation Report",
        "pack": "**Pack**",
        "summary": "## Summary",
        "errors": "Errors",
        "warnings": "Warnings",
        "infos": "Notes",
        "files": "Files scanned",
        "duration": "Duration",
        "findings": "## Findings",
        "clean": "No problems found.",
        "headers": ["Severity", "Code", "File", "Line", "Message", "Suggested fix"],
    },
    "ja": {
        "title": "# TaCZ Gunpack 検証レポート",
        "pack": "**対象**",
        "summary": "## サマリー",
        "errors": "エラー",
        "warnings": "警告",
        "infos": "情報",
        "files": "走査ファイル数",
        "duration": "所要時間",
        "findings": "## 検出結果",
        "clean": "問題は見つかりませんでした。",
        "headers": ["重要度", "コード", "ファイル", "行", "内容", "修正案"],
    },
}


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_markdown(
    report: ValidationReport,
    path: str,
    locale: str = "en",
    results: Optional[List[ValidationResult]] = None,
) -> str:
    text = _TEXT.get(locale, _TEXT["en"])
    rows = report.sorted_results() if results is None else results
    lines = [
        text["title"],
        "",
        "{}: `{}`".format(text["pack"], os.path.basename(report.root.rstrip("/\\")) or report.root),
        "",
        text["summary"],
        "",
        "| | |",
        "|---|---:|",
        "| {} | {} |".format(text["errors"], report.errors),
        "| {} | {} |".format(text["warnings"], report.warnings),
        "| {} | {} |".format(text["infos"], report.infos),
        "| {} | {} |".format(text["files"], report.scanned_files),
        "| {} | {:.2f}s |".format(text["duration"], report.duration_seconds),
        "",
        text["findings"],
        "",
    ]

    if not rows:
        lines.append(text["clean"])
    else:
        lines.append("| " + " | ".join(text["headers"]) + " |")
        lines.append("|---|---|---|---:|---|---|")
        for result in rows:
            lines.append(
                "| {} | `{}` | `{}` | {} | {} | {} |".format(
                    result.severity.label,
                    result.code,
                    result.file or "",
                    result.line if result.line is not None else "",
                    _escape(result.text(locale)),
                    _escape(result.suggestion_text(locale)),
                )
            )
    lines.append("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path
