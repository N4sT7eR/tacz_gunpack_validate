"""Layer 1: the file has to parse before anything else can be checked."""

from __future__ import annotations

from typing import Iterable

from ..core import jsonc
from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.result import Code, ValidationResult
from ..core.validator import Validator, register

_ISSUE_CODES = {
    "trailing_comma": Code.JSON_TRAILING_COMMA,
    "duplicate_key": Code.JSON_DUPLICATE_KEY,
    "non_standard_number": Code.JSON_NON_STANDARD_NUMBER,
}


@register
class JsonSyntaxValidator(Validator):
    name = "json-syntax"
    description = "JSON/JSONC syntax, duplicate keys and other lenient constructs"
    order = 10

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        for document in context.index.documents():
            if document.error is not None:
                yield context.error(
                    Code.JSON_SYNTAX,
                    Message("json.invalid", {"detail": document.error.message}),
                    file=document.relative_path,
                    line=document.error.position.line,
                    column=document.error.position.column,
                )
                continue

            for issue in document.issues:
                yield context.warning(
                    _ISSUE_CODES.get(issue.kind, Code.JSON_SYNTAX),
                    issue.message,
                    file=document.relative_path,
                    line=issue.position.line,
                    column=issue.position.column,
                )

            if context.settings.strict_json:
                yield from self._check_strict(context, document)

    @staticmethod
    def _check_strict(context: ValidationContext, document) -> Iterable[ValidationResult]:
        """Report comments when the user asked for standard JSON.

        TaCZ itself accepts them -- the official pack is full of them -- so this
        is opt-in, for authors who want their pack readable by plain parsers.
        """
        try:
            jsonc.parse(document.text, allow_comments=False, allow_trailing_comma=False)
        except jsonc.JsonSyntaxError as exc:
            yield context.warning(
                Code.JSON_SYNTAX,
                Message("json.not_standard", {"detail": exc.message}),
                file=document.relative_path,
                line=exc.position.line,
                column=exc.position.column,
            )
