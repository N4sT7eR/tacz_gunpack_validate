"""PyInstaller entry point for the command line executable."""

import sys

from tacz_validator.cli import main

if __name__ == "__main__":
    sys.exit(main())
