"""Command line entry point: ``python -m tacz_validator.cli <pack>``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .. import __version__
from ..core.context import ValidatorSettings
from ..core.i18n import DEFAULT_LOCALE, supported_locales
from ..core.pipeline import Progress, validate
from ..core.result import Code, Severity
from ..core.source import PackSourceError
from ..core.validator import all_validators
from ..reporting import FORMATS, render_text, write
from ..rules import DEFAULT_VERSION, available_versions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tacz-validate",
        description="Validate a TaCZ gunpack (a folder or a .zip) without launching Minecraft.",
    )
    parser.add_argument("pack", nargs="?", help="Path to the gunpack folder or .zip")
    parser.add_argument("--version", action="version", version="tacz-validate {}".format(__version__))
    parser.add_argument(
        "--tacz-version",
        default=DEFAULT_VERSION,
        choices=available_versions(),
        help="TaCZ rule set to validate against (default: %(default)s)",
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LOCALE,
        choices=supported_locales(),
        help="Language of the report (default: %(default)s)",
    )
    parser.add_argument(
        "--severity",
        default="info",
        choices=["error", "warning", "info"],
        help="Lowest severity to report (default: %(default)s)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="CODE",
        help="Suppress a finding code, e.g. --ignore LANG001 (repeatable)",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="CHECK",
        help="Skip a whole check, e.g. --disable localization (repeatable)",
    )
    parser.add_argument(
        "--external",
        action="append",
        default=[],
        metavar="NAMESPACE",
        help="Treat a namespace as provided by another pack (repeatable)",
    )
    parser.add_argument("--strict-json", action="store_true", help="Also report comments and trailing commas")
    parser.add_argument("--unused", action="store_true", help="Report unused localization keys")
    parser.add_argument(
        "--format", default="text", choices=FORMATS, help="Output format (default: %(default)s)"
    )
    parser.add_argument("-o", "--output", metavar="FILE", help="Write the report to FILE instead of stdout")
    parser.add_argument("--quiet", action="store_true", help="Print only the summary line")
    parser.add_argument("--no-progress", action="store_true", help="Do not print progress to stderr")
    parser.add_argument("--list-checks", action="store_true", help="List the available checks and exit")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_checks:
        for validator in all_validators():
            print("{:<16} {}".format(validator.name, validator.description))
        return 0

    if not args.pack:
        parser.error("the pack argument is required")

    settings = ValidatorSettings(
        version=args.tacz_version,
        locale=args.lang,
        minimum_severity=Severity.from_name(args.severity),
        ignored_codes=set(args.ignore),
        disabled_validators=set(args.disable),
        external_namespaces=set(args.external),
        strict_json=args.strict_json,
        check_unused_assets=args.unused,
    )

    def show_progress(progress: Progress) -> None:
        if args.no_progress or not sys.stderr.isatty():
            return
        sys.stderr.write("\r\033[K{} {}/{}".format(progress.stage, progress.current, progress.total))
        sys.stderr.flush()

    try:
        report = validate(args.pack, settings, progress=show_progress)
    except PackSourceError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    finally:
        if not args.no_progress and sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

    findings = report.filtered(settings.minimum_severity, settings.ignored_codes)

    if args.output:
        write(report, args.output, args.format, args.lang)
        print("{} findings written to {}".format(len(findings), args.output))
    elif args.quiet:
        print(render_text(report, args.lang, results=[], colour=False).splitlines()[-1])
    elif args.format == "text":
        print(render_text(report, args.lang, results=findings, colour=sys.stdout.isatty()))
    else:
        import tempfile, os

        handle, temporary = tempfile.mkstemp(suffix="." + args.format)
        os.close(handle)
        try:
            write(report, temporary, args.format, args.lang)
            with open(temporary, encoding="utf-8-sig") as source:
                sys.stdout.write(source.read())
        finally:
            os.unlink(temporary)

    return 1 if any(f.severity is Severity.ERROR for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
