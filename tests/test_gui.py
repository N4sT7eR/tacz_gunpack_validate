"""Headless tests for the desktop interface.

Skipped when PySide6 is not installed, so the core test suite still runs on a
machine without Qt.
"""

import os
import shutil
import warnings
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QSettings, QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - Qt is an optional extra
    QApplication = None

import tacz_validator as tv
from tacz_validator.core.result import Severity

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BROKEN = os.path.join(DATA, "broken_pack")
VALID = os.path.join(DATA, "valid_pack")

_application = None
_settings_directory = None


def setUpModule():
    global _application, _settings_directory
    if QApplication is None:
        return
    # Keep the tests out of the real user configuration.
    _settings_directory = tempfile.mkdtemp()
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _settings_directory)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    _application = QApplication.instance() or QApplication([])


def tearDownModule():
    if _settings_directory:
        shutil.rmtree(_settings_directory, ignore_errors=True)


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class MainWindowTests(unittest.TestCase):
    def window(self):
        from tacz_validator.gui.main_window import MainWindow

        window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_starts_in_a_supported_language(self):
        window = self.window()
        self.assertIn(window.locale, ("en", "ja"))
        self.assertTrue(window.validate_button.text())

    def test_switching_language_retranslates_and_is_remembered(self):
        window = self.window()
        english = window.language_combo.findData("en")
        japanese = window.language_combo.findData("ja")

        window.language_combo.setCurrentIndex(english)
        english_button = window.validate_button.text()
        window.language_combo.setCurrentIndex(japanese)
        japanese_button = window.validate_button.text()

        self.assertNotEqual(english_button, japanese_button)
        # A fresh window must come up in the language that was chosen, not the OS one.
        self.assertEqual(self.window().locale, "ja")

    def test_validation_fills_the_table(self):
        window = self.window()
        window.set_pack(BROKEN)
        loop = QEventLoop()
        window.runner.finished.connect(lambda _report: loop.quit())
        QTimer.singleShot(20000, loop.quit)  # never hang the suite
        window.start_validation()
        loop.exec()

        self.assertIsNotNone(window.report)
        self.assertGreater(window.model.rowCount(), 0)
        self.assertFalse(window.cancel_button.isEnabled())
        self.assertTrue(window.validate_button.isEnabled())

    def test_severity_filter_hides_rows(self):
        window = self.window()
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())

        # State the precondition rather than inherit it: the count below is only
        # the error count while no category filter is narrowing the table.
        window.category_combo.setCurrentIndex(window.category_combo.findData(""))
        window.severity_boxes["WARNING"].setChecked(False)
        window.severity_boxes["INFO"].setChecked(False)
        self.assertEqual(window.proxy.rowCount(), window.report.errors)

        window.search_field.setText("zzzz-no-such-text")
        self.assertEqual(window.proxy.rowCount(), 0)

    def test_category_filter_narrows_to_one_category(self):
        window = self.window()
        # The picker is remembered across launches, and these tests share one
        # settings store on purpose (the language test relies on it), so a test
        # that changes the picker has to put it back.
        self.addCleanup(window.settings.set_visible_category, "")
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())

        counts = window.report.counts_by_category()
        target = next(iter(counts))
        index = window.category_combo.findData(target.value)
        self.assertGreaterEqual(index, 0)
        window.category_combo.setCurrentIndex(index)
        self.assertEqual(window.proxy.rowCount(), counts[target])

        window.category_combo.setCurrentIndex(window.category_combo.findData(""))
        self.assertEqual(window.proxy.rowCount(), len(window.report.results))

    def test_category_picker_survives_a_language_switch(self):
        window = self.window()
        self.addCleanup(window.settings.set_visible_category, "")
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())

        target = next(iter(window.report.counts_by_category()))
        window.category_combo.setCurrentIndex(window.category_combo.findData(target.value))
        before = window.proxy.rowCount()

        window.locale = "ja" if window.locale != "ja" else "en"
        window.retranslate()

        # The labels are rebuilt in the new language; the selection must not be
        # silently reset to "all" underneath the user.
        self.assertEqual(window.category_combo.currentData(), target.value)
        self.assertEqual(window.proxy.rowCount(), before)

    def test_summary_names_the_categories_found(self):
        window = self.window()
        window.report = tv.validate(BROKEN)
        window._update_summary()
        for category in window.report.counts_by_category():
            self.assertIn(category.label(window.locale), window.summary_label.text())

    def test_filtering_raises_no_deprecation_warning(self):
        """The replacement for invalidateFilter(), checked where Qt actually is.

        Nothing breaks if it comes back -- the warning is only noise -- but it
        is noise on every keystroke in the search box, and in every CI log.
        """
        window = self.window()
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            window.proxy.set_text("ref")
            window.proxy.set_severities({"ERROR"})
            window.proxy.set_category(None)

        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(
            [str(w.message) for w in deprecated], [], "filtering warned"
        )

    def test_export_writes_into_the_chosen_folder(self):
        window = self.window()
        window.set_pack(BROKEN)
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())

        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        window.output_field.setText(directory)

        window.export("csv")
        window.export("md")
        written = sorted(os.listdir(directory))
        self.assertEqual(len(written), 2)
        self.assertTrue(any(name.endswith(".csv") for name in written))
        self.assertTrue(any(name.endswith(".md") for name in written))
        self.assertTrue(all(name.startswith("broken_pack_") for name in written), written)

    def test_a_clean_pack_shows_the_clean_message(self):
        window = self.window()
        window.report = tv.validate(VALID)
        window._update_summary()
        self.assertIn(window.tr_("gui.clean"), window.summary_label.text())

    def test_details_pane_shows_the_suggested_fix(self):
        window = self.window()
        window.report = tv.validate(BROKEN)
        window.model.set_results(window.report.sorted_results())
        window.table.selectRow(0)
        self.assertTrue(window.details.toPlainText())


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class ModelTests(unittest.TestCase):
    def test_table_renders_in_the_selected_language(self):
        from tacz_validator.gui.model import FindingsModel, column_index

        report = tv.validate(BROKEN)
        model = FindingsModel("en")
        model.set_results(report.sorted_results())
        message = column_index("message")
        english = model.data(model.index(0, message))
        model.set_locale("ja")
        self.assertNotEqual(english, model.data(model.index(0, message)))

    def test_category_column_is_translated_too(self):
        from tacz_validator.gui.model import FindingsModel, column_index

        report = tv.validate(BROKEN)
        model = FindingsModel("en")
        model.set_results(report.sorted_results())
        category = column_index("category")
        english = model.data(model.index(0, category))
        self.assertTrue(english)
        model.set_locale("ja")
        self.assertNotEqual(english, model.data(model.index(0, category)))

    def test_headers_are_translated(self):
        from PySide6.QtCore import Qt

        from tacz_validator.gui.model import FindingsModel

        model = FindingsModel("ja")
        self.assertEqual(
            model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole), "重要度"
        )


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class DropTests(unittest.TestCase):
    def test_accepts_folders_and_zips_only(self):
        from PySide6.QtCore import QMimeData, QUrl

        from tacz_validator.gui.main_window import MainWindow

        class FakeEvent:
            def __init__(self, mime):
                self._mime = mime

            def mimeData(self):
                return self._mime

        def event_for(path):
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(path)])
            return FakeEvent(mime)

        # Qt returns a URL path, so on Windows the drop arrives as "D:/a/pack"
        # and has to come back in the native form the rest of the window uses.
        self.assertEqual(MainWindow._dropped_path(event_for(BROKEN)), BROKEN)

        # A .zip is accepted on its suffix, so this one need not exist -- but it
        # does have to be written the way the platform writes paths, or the test
        # is asserting that normalisation did not happen.
        archive = os.path.join(tempfile.gettempdir(), "pack.zip")
        self.assertEqual(MainWindow._dropped_path(event_for(archive)), archive)

        self.assertIsNone(
            MainWindow._dropped_path(event_for(os.path.join(tempfile.gettempdir(), "notes.txt")))
        )


if __name__ == "__main__":
    unittest.main()
