"""Validation on a background thread, so the window never freezes."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from ..core.context import ValidatorSettings
from ..core.pipeline import Progress, validate
from ..core.result import ValidationReport


class ValidationWorker(QObject):
    """Runs one validation and reports back through signals."""

    progressed = Signal(object)  # Progress
    finished = Signal(object)  # ValidationReport
    failed = Signal(str)

    def __init__(self, path: str, settings: ValidatorSettings) -> None:
        super().__init__()
        self._path = path
        self._settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            report = validate(
                self._path,
                self._settings,
                progress=self.progressed.emit,
                is_cancelled=self.is_cancelled,
            )
        except Exception as exc:  # surfaced in a dialog rather than a traceback
            self.failed.emit(str(exc))
            return
        self.finished.emit(report)


class ValidationRunner(QObject):
    """Owns the worker and its thread, and cleans both up afterwards."""

    progressed = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread = None  # type: QThread
        self._worker = None  # type: ValidationWorker

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, path: str, settings: ValidatorSettings) -> None:
        if self.running:
            return
        self._thread = QThread(self)
        self._worker = ValidationWorker(path, settings)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progressed.connect(self.progressed)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _shutdown(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        self._worker = None

    def _on_finished(self, report: ValidationReport) -> None:
        self._shutdown()
        self.finished.emit(report)

    def _on_failed(self, message: str) -> None:
        self._shutdown()
        self.failed.emit(message)
