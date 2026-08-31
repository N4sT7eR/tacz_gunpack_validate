"""JSON export, for scripting and CI."""

from __future__ import annotations

import json
from typing import List, Optional

from ..core.result import ValidationReport, ValidationResult


def write_json(
    report: ValidationReport,
    path: str,
    locale: str = "en",
    results: Optional[List[ValidationResult]] = None,
) -> str:
    rows = report.sorted_results() if results is None else results
    payload = {
        "pack": report.root,
        "summary": {
            "errors": report.errors,
            "warnings": report.warnings,
            "infos": report.infos,
            "files": report.scanned_files,
            "duration_seconds": round(report.duration_seconds, 3),
            "cancelled": report.cancelled,
        },
        "findings": [
            {
                "severity": r.severity.label,
                "code": r.code,
                "file": r.file,
                "line": r.line,
                "column": r.column,
                "message": r.text(locale),
                "suggestion": r.suggestion_text(locale) or None,
                "resource": r.resource_id,
                "validator": r.validator,
            }
            for r in rows
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path
