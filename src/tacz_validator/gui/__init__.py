"""The desktop interface."""

from __future__ import annotations

import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    """Launch the window. ``tacz-validate-gui`` and the .exe both land here."""
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow
    from .settings import APPLICATION, ORGANISATION

    application = QApplication(argv if argv is not None else sys.argv)
    application.setOrganizationName(ORGANISATION)
    application.setApplicationName(APPLICATION)

    window = MainWindow()
    # A path on the command line (or a pack dropped onto the .exe) opens straight away.
    arguments = (argv if argv is not None else sys.argv)[1:]
    if arguments:
        window.set_pack(arguments[0])
    window.show()
    return application.exec()


__all__ = ["main"]
