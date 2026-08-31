"""PyInstaller entry point for the GUI.

PyInstaller runs its target file as ``__main__``, which makes the relative
imports inside ``tacz_validator/gui/__main__.py`` fail.  This launcher uses an
absolute import instead, so the frozen executable behaves like ``python -m``.
"""

import sys

from tacz_validator.gui import main

if __name__ == "__main__":
    sys.exit(main())
