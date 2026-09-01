"""The findings table.

The model holds :class:`ValidationResult` objects and renders them in whatever
language is currently selected, so switching language never re-runs the check.
"""

from __future__ import annotations

from typing import List, Optional, Set

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from ..core.i18n import Message, render
from ..core.result import Category, Severity, ValidationResult

_COLUMNS = (
    ("gui.col_severity", "severity"),
    ("gui.col_category", "category"),
    ("gui.col_code", "code"),
    ("gui.col_file", "file"),
    ("gui.col_line", "line"),
    ("gui.col_message", "message"),
    ("gui.col_suggestion", "suggestion"),
)

#: Field name per column, so callers size and stretch columns by name.  The
#: window used to hard-code 2 and 4, which silently pointed at the wrong
#: columns the moment one was inserted.
COLUMN_FIELDS = tuple(field for _key, field in _COLUMNS)


def column_index(field: str) -> int:
    return COLUMN_FIELDS.index(field)


SEVERITY_COLOURS = {
    Severity.ERROR: QColor(200, 50, 50),
    Severity.WARNING: QColor(190, 130, 0),
    Severity.INFO: QColor(70, 120, 180),
}


class FindingsModel(QAbstractTableModel):
    def __init__(self, locale: str = "en", parent=None) -> None:
        super().__init__(parent)
        self._results = []  # type: List[ValidationResult]
        self._locale = locale

    # -- content -------------------------------------------------------------

    def set_results(self, results: List[ValidationResult]) -> None:
        self.beginResetModel()
        self._results = list(results)
        self.endResetModel()

    def set_locale(self, locale: str) -> None:
        self._locale = locale
        self.beginResetModel()
        self.endResetModel()

    def result_at(self, row: int) -> Optional[ValidationResult]:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    # -- QAbstractTableModel -------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return render(Message(_COLUMNS[section][0]), self._locale)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        result = self._results[index.row()]
        field = _COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if field == "severity":
                return result.severity.label
            if field == "category":
                return result.category_label(self._locale)
            if field == "code":
                return result.code
            if field == "file":
                return result.file or ""
            if field == "line":
                return "" if result.line is None else str(result.line)
            if field == "message":
                return result.text(self._locale)
            return result.suggestion_text(self._locale)

        if role == Qt.ItemDataRole.ForegroundRole and field == "severity":
            return SEVERITY_COLOURS.get(result.severity)

        if role == Qt.ItemDataRole.TextAlignmentRole and field == "line":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ToolTipRole:
            suggestion = result.suggestion_text(self._locale)
            text = result.text(self._locale)
            return "{}\n{}".format(text, suggestion) if suggestion else text

        if role == Qt.ItemDataRole.UserRole:
            return result.severity.label

        return None


class FindingsFilter(QSortFilterProxyModel):
    """Severity checkboxes, a category picker and a free-text box, applied together."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._severities = {s.label for s in Severity}  # type: Set[str]
        self._category = None  # type: Optional[Category]
        self._text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_severities(self, labels: Set[str]) -> None:
        self._severities = set(labels)
        self.invalidateFilter()

    def set_category(self, category: Optional[Category]) -> None:
        """Show a single category, or every one when ``category`` is None."""
        self._category = category
        self.invalidateFilter()

    def set_text(self, text: str) -> None:
        self._text = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model = self.sourceModel()
        result = model.result_at(source_row)
        if result is None:
            return False
        if result.severity.label not in self._severities:
            return False
        if self._category is not None and result.category is not self._category:
            return False
        if not self._text:
            return True
        haystack = " ".join(
            [
                result.code,
                result.file or "",
                model.data(model.index(source_row, column_index("category"))) or "",
                model.data(model.index(source_row, column_index("message"))) or "",
                model.data(model.index(source_row, column_index("suggestion"))) or "",
            ]
        ).lower()
        return self._text in haystack

    def visible_results(self) -> List[ValidationResult]:
        model = self.sourceModel()
        return [
            model.result_at(self.mapToSource(self.index(row, 0)).row())
            for row in range(self.rowCount())
        ]
