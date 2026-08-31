"""CSV export.

Written with a BOM so that Excel on a Japanese Windows install opens it as
UTF-8 instead of mangling every message.
"""

from __future__ import annotations

import csv
from typing import List, Optional

from ..core.result import ValidationReport, ValidationResult

_HEADERS = {
    "en": ["Severity", "Code", "File", "Line", "Column", "Message", "Suggested fix", "Resource", "Check"],
    "ja": ["重要度", "コード", "ファイル", "行", "列", "内容", "修正案", "リソース", "検査"],
}


def write_csv(
    report: ValidationReport,
    path: str,
    locale: str = "en",
    results: Optional[List[ValidationResult]] = None,
) -> str:
    rows = report.sorted_results() if results is None else results
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADERS.get(locale, _HEADERS["en"]))
        for result in rows:
            writer.writerow(
                [
                    result.severity.label,
                    result.code,
                    result.file or "",
                    result.line if result.line is not None else "",
                    result.column if result.column is not None else "",
                    result.text(locale),
                    result.suggestion_text(locale),
                    result.resource_id or "",
                    result.validator or "",
                ]
            )
    return path
