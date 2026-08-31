"""The main window: pick a pack, press the button, read the findings."""

from __future__ import annotations

import datetime
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.context import ValidatorSettings
from ..core.i18n import Message, locale_display_name, render, supported_locales
from ..core.pipeline import Progress
from ..core.result import Severity, ValidationReport
from ..reporting import write
from ..rules import DEFAULT_VERSION, available_versions
from .model import FindingsFilter, FindingsModel
from .settings import UserSettings
from .worker import ValidationRunner


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = UserSettings()
        self.locale = self.settings.language()
        self.report = None  # type: Optional[ValidationReport]
        self.pack_path = ""
        self.runner = ValidationRunner(self)

        self._build_ui()
        self._connect()
        self._restore_state()
        self.retranslate()

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._build_pack_box())
        layout.addWidget(self._build_options_row())
        layout.addWidget(self._build_summary())
        layout.addWidget(self._build_filter_row())
        layout.addWidget(self._build_results(), stretch=1)
        layout.addWidget(self._build_output_box())
        layout.addWidget(self._build_status_row())

        self.setCentralWidget(central)
        self.setAcceptDrops(True)
        self.resize(1100, 720)

    def _build_pack_box(self) -> QWidget:
        self.pack_box = QGroupBox()
        row = QHBoxLayout(self.pack_box)
        self.pack_field = QLineEdit()
        self.pack_field.setReadOnly(True)
        self.pack_field.setMinimumHeight(30)
        self.browse_zip_button = QPushButton()
        self.browse_folder_button = QPushButton()
        self.clear_button = QPushButton()
        row.addWidget(self.pack_field, stretch=1)
        row.addWidget(self.browse_zip_button)
        row.addWidget(self.browse_folder_button)
        row.addWidget(self.clear_button)
        return self.pack_box

    def _build_options_row(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)

        self.version_label = QLabel()
        self.version_combo = QComboBox()
        self.version_combo.addItems(available_versions())
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for code in supported_locales():
            self.language_combo.addItem(locale_display_name(code), code)

        self.validate_button = QPushButton()
        self.validate_button.setMinimumHeight(34)
        self.validate_button.setDefault(True)
        self.cancel_button = QPushButton()
        self.cancel_button.setEnabled(False)

        row.addWidget(self.version_label)
        row.addWidget(self.version_combo)
        row.addSpacing(16)
        row.addWidget(self.language_label)
        row.addWidget(self.language_combo)
        row.addStretch(1)
        row.addWidget(self.validate_button)
        row.addWidget(self.cancel_button)
        return widget

    def _build_summary(self) -> QWidget:
        self.summary_label = QLabel()
        self.summary_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.summary_label.setMinimumHeight(32)
        self.summary_label.setContentsMargins(8, 4, 8, 4)
        return self.summary_label

    def _build_filter_row(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.show_label = QLabel()
        self.severity_boxes = {}
        row.addWidget(self.show_label)
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            box = QCheckBox(severity.label)
            box.setChecked(True)
            self.severity_boxes[severity.label] = box
            row.addWidget(box)
        row.addSpacing(16)
        self.search_field = QLineEdit()
        self.search_field.setClearButtonEnabled(True)
        row.addWidget(self.search_field, stretch=1)
        return widget

    def _build_results(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.model = FindingsModel(self.locale, self)
        self.proxy = FindingsFilter(self)
        self.proxy.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(90)

        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _build_output_box(self) -> QWidget:
        self.output_box = QGroupBox()
        row = QHBoxLayout(self.output_box)
        self.output_field = QLineEdit()
        self.output_field.setReadOnly(True)
        self.output_button = QPushButton()
        self.csv_button = QPushButton()
        self.md_button = QPushButton()
        row.addWidget(self.output_field, stretch=1)
        row.addWidget(self.output_button)
        row.addSpacing(12)
        row.addWidget(self.csv_button)
        row.addWidget(self.md_button)
        return self.output_box

    def _build_status_row(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setVisible(False)
        row.addWidget(self.status_label, stretch=1)
        row.addWidget(self.progress)
        return widget

    def _connect(self) -> None:
        self.browse_zip_button.clicked.connect(self.choose_zip)
        self.browse_folder_button.clicked.connect(self.choose_folder)
        self.clear_button.clicked.connect(self.clear_pack)
        self.validate_button.clicked.connect(self.start_validation)
        self.cancel_button.clicked.connect(self.runner.cancel)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.version_combo.currentTextChanged.connect(self.settings.set_tacz_version)
        self.search_field.textChanged.connect(self.proxy.set_text)
        for box in self.severity_boxes.values():
            box.toggled.connect(self._severity_changed)
        self.table.selectionModel().selectionChanged.connect(self._show_details)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.output_button.clicked.connect(self.choose_output_directory)
        self.csv_button.clicked.connect(lambda: self.export("csv"))
        self.md_button.clicked.connect(lambda: self.export("md"))

        self.runner.progressed.connect(self._on_progress)
        self.runner.finished.connect(self._on_finished)
        self.runner.failed.connect(self._on_failed)

    def _restore_state(self) -> None:
        index = self.language_combo.findData(self.locale)
        if index >= 0:
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(index)
            self.language_combo.blockSignals(False)

        version = self.settings.tacz_version(DEFAULT_VERSION)
        if version in available_versions():
            self.version_combo.setCurrentText(version)

        self.output_field.setText(self.settings.output_directory())

        stored = self.settings.visible_severities()
        if stored is not None:
            for label, box in self.severity_boxes.items():
                box.setChecked(label in stored)

        # QSettings hands geometry back as a QByteArray, but the exact type
        # depends on the backend (registry on Windows, ini elsewhere), so a
        # stale or oddly typed value must never stop the window from opening.
        geometry = self.settings.geometry()
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except (TypeError, ValueError):
                pass

        last = self.settings.last_pack()
        if last and os.path.exists(last):
            self.set_pack(last)

    # -- translation ---------------------------------------------------------

    def tr_(self, key: str, **params) -> str:
        return render(Message(key, params), self.locale)

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr_("gui.title"))
        self.pack_box.setTitle(self.tr_("gui.pack"))
        self.pack_field.setPlaceholderText(self.tr_("gui.drop_hint"))
        self.browse_zip_button.setText(self.tr_("gui.browse_zip"))
        self.browse_folder_button.setText(self.tr_("gui.browse_folder"))
        self.clear_button.setText(self.tr_("gui.clear"))
        self.version_label.setText(self.tr_("gui.tacz_version"))
        self.language_label.setText(self.tr_("gui.language"))
        self.validate_button.setText(self.tr_("gui.validate"))
        self.cancel_button.setText(self.tr_("gui.cancel"))
        self.show_label.setText(self.tr_("gui.show"))
        self.search_field.setPlaceholderText(self.tr_("gui.search"))
        self.output_box.setTitle(self.tr_("gui.output_folder"))
        self.output_button.setText(self.tr_("gui.choose_output"))
        self.csv_button.setText(self.tr_("gui.save_csv"))
        self.md_button.setText(self.tr_("gui.save_md"))
        self.model.set_locale(self.locale)
        self._update_summary()
        self._show_details()
        if not self.runner.running:
            self.status_label.setText(self.tr_("gui.status_ready"))

    def _language_changed(self, index: int) -> None:
        locale = self.language_combo.itemData(index)
        if not locale or locale == self.locale:
            return
        self.locale = locale
        # Remembered from now on: the OS language only decides the first launch.
        self.settings.set_language(locale)
        self.retranslate()

    # -- pack selection ------------------------------------------------------

    def choose_zip(self) -> None:
        start = os.path.dirname(self.pack_path) if self.pack_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr_("gui.select_zip_dialog"), start, self.tr_("gui.zip_filter")
        )
        if path:
            self.set_pack(path)

    def choose_folder(self) -> None:
        start = self.pack_path if os.path.isdir(self.pack_path) else ""
        path = QFileDialog.getExistingDirectory(self, self.tr_("gui.select_pack_dialog"), start)
        if path:
            self.set_pack(path)

    def set_pack(self, path: str) -> None:
        self.pack_path = path
        self.pack_field.setText(path)
        self.settings.set_last_pack(path)

    def clear_pack(self) -> None:
        self.pack_path = ""
        self.pack_field.clear()
        self.report = None
        self.model.set_results([])
        self._update_summary()
        self.details.clear()

    # -- drag and drop -------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if self._dropped_path(event) is not None:
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if self._dropped_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        path = self._dropped_path(event)
        if path is None:
            return
        event.acceptProposedAction()
        self.set_pack(path)
        self.start_validation()

    @staticmethod
    def _dropped_path(event) -> Optional[str]:
        """A dropped folder, or a dropped .zip -- anything else is refused."""
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if os.path.isdir(path) or path.lower().endswith(".zip"):
                return path
        return None

    # -- running -------------------------------------------------------------

    def current_settings(self) -> ValidatorSettings:
        return ValidatorSettings(
            version=self.version_combo.currentText() or DEFAULT_VERSION,
            locale=self.locale,
        )

    def start_validation(self) -> None:
        if self.runner.running:
            return
        if not self.pack_path:
            QMessageBox.information(self, self.tr_("gui.title"), self.tr_("gui.no_pack"))
            return
        self.model.set_results([])
        self.details.clear()
        self.validate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText(self.tr_("gui.status_scanning"))
        self.runner.start(self.pack_path, self.current_settings())

    def _on_progress(self, progress: Progress) -> None:
        if progress.stage == "parse":
            self.progress.setRange(0, progress.total)
            self.progress.setValue(progress.current)
            self.status_label.setText(
                self.tr_("gui.status_parsing", current=progress.current, total=progress.total)
            )
        elif progress.stage == "scan":
            self.status_label.setText(self.tr_("gui.status_scanning"))
        elif progress.stage != "done":
            self.progress.setRange(0, progress.total)
            self.progress.setValue(progress.current)
            self.status_label.setText(self.tr_("gui.status_checking", stage=progress.stage))

    def _on_finished(self, report: ValidationReport) -> None:
        self.report = report
        self.model.set_results(report.sorted_results())
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._finish_run()
        self.status_label.setText(
            self.tr_("gui.status_cancelled")
            if report.cancelled
            else self.tr_("gui.status_done", seconds=report.duration_seconds)
        )
        self._update_summary()

    def _on_failed(self, message: str) -> None:
        self._finish_run()
        self.status_label.setText(self.tr_("gui.status_ready"))
        QMessageBox.critical(self, self.tr_("gui.error_title"), message)

    def _finish_run(self) -> None:
        self.validate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(False)

    # -- results -------------------------------------------------------------

    def _severity_changed(self) -> None:
        visible = {label for label, box in self.severity_boxes.items() if box.isChecked()}
        self.proxy.set_severities(visible)
        self.settings.set_visible_severities(sorted(visible))

    def _show_details(self, *args) -> None:
        result = self._selected_result()
        if result is None:
            self.details.clear()
            return
        lines = [
            "[{}] {}  {}".format(result.severity.label, result.code, result.location),
            "",
            result.text(self.locale),
        ]
        suggestion = result.suggestion_text(self.locale)
        if suggestion:
            lines += ["", "→ " + suggestion]
        self.details.setPlainText("\n".join(lines))

    def _selected_result(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.model.result_at(self.proxy.mapToSource(indexes[0]).row())

    def _show_context_menu(self, position) -> None:
        result = self._selected_result()
        if result is None:
            return
        menu = QMenu(self)
        copy_action = QAction(self.tr_("gui.copy_row"), self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(lambda: self._copy(result))
        menu.addAction(copy_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _copy(self, result) -> None:
        text = "{}\t{}\t{}\t{}\t{}".format(
            result.severity.label,
            result.code,
            result.location,
            result.text(self.locale),
            result.suggestion_text(self.locale),
        )
        QGuiApplication.clipboard().setText(text)

    # -- export --------------------------------------------------------------

    def choose_output_directory(self) -> None:
        start = self.output_field.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, self.tr_("gui.select_output_dialog"), start)
        if path:
            self.output_field.setText(path)
            self.settings.set_output_directory(path)

    def export(self, fmt: str) -> None:
        if self.report is None or not self.report.results:
            QMessageBox.information(self, self.tr_("gui.title"), self.tr_("gui.no_results"))
            return
        directory = self.output_field.text()
        if not directory:
            self.choose_output_directory()
            directory = self.output_field.text()
            if not directory:
                return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(self.pack_path.rstrip("/\\")) or "gunpack"
        if base.lower().endswith(".zip"):
            base = base[: -len(".zip")]
        filename = "{}_{}.{}".format(_safe(base), stamp, fmt)
        path = os.path.join(directory, filename)
        try:
            write(self.report, path, fmt, self.locale)
        except OSError as exc:
            QMessageBox.critical(self, self.tr_("gui.error_title"), str(exc))
            return
        self.status_label.setText(self.tr_("gui.saved", path=path))

    # -- window --------------------------------------------------------------

    def _update_summary(self) -> None:
        if self.report is None:
            self.summary_label.setText("")
            return
        self.summary_label.setText(
            self.tr_(
                "gui.summary",
                errors=self.report.errors,
                warnings=self.report.warnings,
                infos=self.report.infos,
                files=self.report.scanned_files,
                seconds=self.report.duration_seconds,
            )
            + ("    " + self.tr_("gui.clean") if not self.report.results else "")
        )

    def closeEvent(self, event) -> None:
        self.settings.set_geometry(self.saveGeometry())
        self.runner.cancel()
        super().closeEvent(event)


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
