"""Rendering a report for a terminal, a spreadsheet or a document."""

from .csv_report import write_csv
from .json_report import write_json
from .markdown import write_markdown
from .text import render_text

__all__ = ["render_text", "write_csv", "write_markdown", "write_json", "FORMATS", "write"]

FORMATS = ("text", "csv", "md", "json")


def write(report, path, fmt, locale="en", results=None):
    """Write ``report`` to ``path`` in ``fmt``.

    ``results`` is the already-filtered view; passing it keeps an exported file
    identical to what the user saw on screen instead of quietly re-including
    findings they filtered out.
    """
    if fmt == "csv":
        return write_csv(report, path, locale, results)
    if fmt == "md":
        return write_markdown(report, path, locale, results)
    if fmt == "json":
        return write_json(report, path, locale, results)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render_text(report, locale, results=results, colour=False))
    return path
