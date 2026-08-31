"""JSONC (JSON with comments) parser that records the source position of every node.

TaCZ gunpacks are parsed by Gson in lenient mode, and the official default pack
uses ``//`` line comments and ``/* */`` block comments extensively -- often to
disable whole blocks of settings.  ``json.loads`` cannot read those files, and it
also throws away the position of every value, which this tool needs in order to
point at the offending line.

The parser therefore returns plain ``dict``/``list`` subclasses that carry the
source position of each key and value, plus a list of lenient constructs (trailing
commas, duplicate keys, ``NaN``) that TaCZ tolerates but that are worth reporting.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, NamedTuple, Optional

from .i18n import Message, render

__all__ = [
    "Position",
    "LineMap",
    "JsonObject",
    "JsonArray",
    "JsonSyntaxError",
    "LenientIssue",
    "ParsedDocument",
    "parse",
    "parse_fast",
    "strip_comments",
]

_WHITESPACE = " \t\n\r"
_NUMBER_START = "-0123456789"
_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class Position(NamedTuple):
    """A 1-based line/column pair plus the raw character offset."""

    line: int
    column: int
    offset: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "{}:{}".format(self.line, self.column)


class LineMap:
    """Turns a character offset into a line/column pair, on demand.

    Computing this during parsing is what made an early version crawl: a Bedrock
    model has hundreds of thousands of numbers, and every one of them paid for a
    binary search it never used.  Parsing now stores raw offsets, and only the
    handful of positions that end up in a finding are ever resolved.
    """

    __slots__ = ("_text", "_line_starts")

    def __init__(self, text: str) -> None:
        self._text = text
        self._line_starts = None  # type: Optional[List[int]]

    def _ensure(self) -> List[int]:
        if self._line_starts is None:
            starts = [0]
            append = starts.append
            index = self._text.find("\n")
            while index != -1:
                append(index + 1)
                index = self._text.find("\n", index + 1)
            self._line_starts = starts
        return self._line_starts

    def position(self, offset: int) -> Position:
        starts = self._ensure()
        low, high = 0, len(starts) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if starts[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return Position(low + 1, offset - starts[low] + 1, offset)


_EMPTY_LINE_MAP = LineMap("")


class JsonObject(dict):
    """``dict`` that remembers where each key and value came from."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offset = 0
        self.key_offsets = {}  # type: Dict[str, int]
        self.value_offsets = {}  # type: Dict[str, int]
        self.line_map = _EMPTY_LINE_MAP  # type: LineMap

    @property
    def position(self) -> Position:
        return self.line_map.position(self.offset)

    def key_position(self, key: str) -> Optional[Position]:
        offset = self.key_offsets.get(key)
        return None if offset is None else self.line_map.position(offset)

    def value_position(self, key: str) -> Optional[Position]:
        offset = self.value_offsets.get(key)
        return None if offset is None else self.line_map.position(offset)

    def position_of(self, key: str) -> Position:
        """Position of ``key``'s value, falling back to the key, then the object."""
        offset = self.value_offsets.get(key)
        if offset is None:
            offset = self.key_offsets.get(key, self.offset)
        return self.line_map.position(offset)


class JsonArray(list):
    """``list`` that remembers where each element came from."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offset = 0
        self.item_offsets = []  # type: List[int]
        self.line_map = _EMPTY_LINE_MAP  # type: LineMap

    @property
    def position(self) -> Position:
        return self.line_map.position(self.offset)

    def position_of(self, index: int) -> Position:
        if 0 <= index < len(self.item_offsets):
            return self.line_map.position(self.item_offsets[index])
        return self.position


class JsonSyntaxError(Exception):
    """Raised when the document cannot be parsed at all.

    The reason travels as a :class:`~.i18n.Message` so the same error can be
    shown in either language; ``str()`` renders the English form for logs.
    """

    def __init__(self, message: Message, position: Position) -> None:
        super().__init__(
            "{} (line {}, column {})".format(render(message), position.line, position.column)
        )
        self.message = message
        self.position = position

    def text(self, locale: str = "en") -> str:
        return render(self.message, locale)


class LenientIssue(NamedTuple):
    """A construct TaCZ's parser accepts but that is still worth reporting."""

    kind: str  # trailing_comma | duplicate_key | non_standard_number | ...
    message: Message
    position: Position


class ParsedDocument(NamedTuple):
    value: Any
    issues: List[LenientIssue]


#: Matches a JSON string, a line comment, or a block comment.  Putting the string
#: alternative first is what keeps ``"http://example.com"`` from being eaten.
_COMMENT_OR_STRING = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def strip_comments(text: str) -> str:
    """Blank out comments while keeping every other character at its offset.

    Offsets are preserved so that a position reported by ``json.loads`` against
    the stripped text still points at the right place in the original file.
    """

    def replace(match):
        chunk = match.group(0)
        if chunk.startswith('"'):
            return chunk
        # Keep newlines so line numbers survive; blank everything else.
        return "".join("\n" if ch == "\n" else " " for ch in chunk)

    return _COMMENT_OR_STRING.sub(replace, text)


class _Parser:
    def __init__(self, text: str, allow_comments: bool = True, allow_trailing_comma: bool = True) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0
        self.allow_comments = allow_comments
        self.allow_trailing_comma = allow_trailing_comma
        self.issues = []  # type: List[LenientIssue]
        self.line_map = LineMap(text)

    # -- position bookkeeping ------------------------------------------------

    def position_at(self, offset: int) -> Position:
        return self.line_map.position(offset)

    def fail(self, message_key: str, offset: Optional[int] = None, **params) -> "JsonSyntaxError":
        position = self.position_at(offset if offset is not None else self.index)
        return JsonSyntaxError(Message(message_key, params), position)

    def note(self, kind: str, message_key: str, offset: int, **params) -> None:
        self.issues.append(LenientIssue(kind, Message(message_key, params), self.position_at(offset)))

    # -- scanning ------------------------------------------------------------

    def skip_insignificant(self) -> None:
        """Skip whitespace and comments."""
        text, length = self.text, self.length
        while self.index < length:
            ch = text[self.index]
            if ch in _WHITESPACE:
                self.index += 1
                continue
            if ch == "/" and self.index + 1 < length:
                nxt = text[self.index + 1]
                if nxt == "/":
                    self._skip_line_comment()
                    continue
                if nxt == "*":
                    self._skip_block_comment()
                    continue
            if ch == "\ufeff":  # stray BOM in the middle of a document
                self.index += 1
                continue
            return

    def _skip_line_comment(self) -> None:
        start = self.index
        if not self.allow_comments:
            raise self.fail("json.comments_not_allowed", start)
        end = self.text.find("\n", self.index)
        self.index = self.length if end == -1 else end + 1

    def _skip_block_comment(self) -> None:
        start = self.index
        if not self.allow_comments:
            raise self.fail("json.comments_not_allowed", start)
        end = self.text.find("*/", self.index + 2)
        if end == -1:
            raise self.fail("json.unterminated_block_comment", start)
        self.index = end + 2

    def peek(self) -> str:
        return self.text[self.index] if self.index < self.length else ""

    # -- grammar -------------------------------------------------------------

    def parse_document(self) -> Any:
        if self.text.startswith("\ufeff"):
            self.index = 1
        self.skip_insignificant()
        if self.index >= self.length:
            raise self.fail("json.empty_document", 0)
        value = self.parse_value()
        self.skip_insignificant()
        if self.index < self.length:
            raise self.fail("json.trailing_content", char=repr(self.peek()))
        return value

    def parse_value(self) -> Any:
        self.skip_insignificant()
        ch = self.peek()
        if ch == "":
            raise self.fail("json.unexpected_eof_value")
        if ch == "{":
            return self.parse_object()
        if ch == "[":
            return self.parse_array()
        if ch == '"':
            return self.parse_string()
        if ch in _NUMBER_START:
            return self.parse_number()
        if self.text.startswith("true", self.index):
            self.index += 4
            return True
        if self.text.startswith("false", self.index):
            self.index += 5
            return False
        if self.text.startswith("null", self.index):
            self.index += 4
            return None
        for literal in ("NaN", "Infinity", "-Infinity"):
            if self.text.startswith(literal, self.index):
                self.note("non_standard_number", "json.non_standard_number", self.index, literal=literal)
                self.index += len(literal)
                return float(literal)
        if ch == "'":
            raise self.fail("json.single_quotes")
        raise self.fail("json.unexpected_char", char=repr(ch))

    def parse_object(self) -> JsonObject:
        start = self.index
        self.index += 1  # consume '{'
        obj = JsonObject()
        obj.offset = start
        obj.line_map = self.line_map
        expecting_value = False
        last_comma = -1
        while True:
            self.skip_insignificant()
            ch = self.peek()
            if ch == "":
                raise self.fail("json.missing_brace", start)
            if ch == "}":
                if expecting_value:
                    if not self.allow_trailing_comma:
                        raise self.fail("json.trailing_comma", last_comma, closer="'}'")
                    self.note("trailing_comma", "json.trailing_comma", last_comma, closer="'}'")
                self.index += 1
                return obj
            if obj and not expecting_value:
                raise self.fail("json.expected_comma_object")
            if ch != '"':
                raise self.fail("json.key_not_string")
            key_offset = self.index
            key = self.parse_string()
            self.skip_insignificant()
            if self.peek() != ":":
                raise self.fail("json.expected_colon", key=repr(key))
            self.index += 1
            self.skip_insignificant()
            value_offset = self.index
            value = self.parse_value()
            if key in obj:
                self.note("duplicate_key", "json.duplicate_key", key_offset, key=repr(key))
            obj[key] = value
            obj.key_offsets[key] = key_offset
            obj.value_offsets[key] = value_offset
            self.skip_insignificant()
            if self.peek() == ",":
                last_comma = self.index
                self.index += 1
                expecting_value = True
            else:
                expecting_value = False

    def parse_array(self) -> JsonArray:
        start = self.index
        self.index += 1  # consume '['
        arr = JsonArray()
        arr.offset = start
        arr.line_map = self.line_map
        append_offset = arr.item_offsets.append
        expecting_value = False
        last_comma = -1
        while True:
            self.skip_insignificant()
            ch = self.peek()
            if ch == "":
                raise self.fail("json.missing_bracket", start)
            if ch == "]":
                if expecting_value:
                    if not self.allow_trailing_comma:
                        raise self.fail("json.trailing_comma", last_comma, closer="']'")
                    self.note("trailing_comma", "json.trailing_comma", last_comma, closer="']'")
                self.index += 1
                return arr
            if arr and not expecting_value:
                raise self.fail("json.expected_comma_array")
            item_offset = self.index
            arr.append(self.parse_value())
            append_offset(item_offset)
            self.skip_insignificant()
            if self.peek() == ",":
                last_comma = self.index
                self.index += 1
                expecting_value = True
            else:
                expecting_value = False

    def parse_string(self) -> str:
        start = self.index
        index = start + 1  # skip opening quote
        text, length = self.text, self.length
        # Fast path: no escapes means one slice instead of a per-character loop.
        end = text.find('"', index)
        while end != -1:
            backslashes = 0
            probe = end - 1
            while probe >= index and text[probe] == "\\":
                backslashes += 1
                probe -= 1
            if backslashes % 2 == 0:
                chunk = text[index:end]
                if "\n" in chunk:
                    raise self.fail("json.string_linebreak", start)
                self.index = end + 1
                if "\\" not in chunk:
                    return chunk
                return self._unescape(chunk, start)
            end = text.find('"', end + 1)
        raise self.fail("json.unterminated_string", start)

    def _unescape(self, chunk: str, start: int) -> str:
        out = []  # type: List[str]
        i = 0
        length = len(chunk)
        while i < length:
            ch = chunk[i]
            if ch != "\\":
                out.append(ch)
                i += 1
                continue
            i += 1
            if i >= length:
                raise self.fail("json.unterminated_escape", start)
            esc = chunk[i]
            if esc in _ESCAPES:
                out.append(_ESCAPES[esc])
                i += 1
                continue
            if esc == "u":
                if i + 5 > length:
                    raise self.fail("json.truncated_unicode", start)
                digits = chunk[i + 1 : i + 5]
                try:
                    code = int(digits, 16)
                except ValueError:
                    raise self.fail("json.invalid_unicode", start, digits=digits)
                i += 5
                if 0xD800 <= code <= 0xDBFF and chunk[i : i + 2] == "\\u":
                    try:
                        low = int(chunk[i + 2 : i + 6], 16)
                    except ValueError:
                        low = -1
                    if 0xDC00 <= low <= 0xDFFF:
                        i += 6
                        out.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
                        continue
                out.append(chr(code))
                continue
            raise self.fail("json.invalid_escape", start, escape=esc)
        return "".join(out)

    def parse_number(self) -> Any:
        start = self.index
        text, length = self.text, self.length
        if text[self.index] == "-":
            self.index += 1
            if text.startswith("Infinity", self.index):
                self.note("non_standard_number", "json.non_standard_number", start, literal="-Infinity")
                self.index += len("Infinity")
                return float("-inf")
        digits_start = self.index
        while self.index < length and text[self.index].isdigit():
            self.index += 1
        if self.index == digits_start:
            raise self.fail("json.expected_digit", start)
        if text[digits_start] == "0" and self.index - digits_start > 1:
            self.note("non_standard_number", "json.leading_zero", start)
        is_float = False
        if self.index < length and text[self.index] == ".":
            is_float = True
            self.index += 1
            fraction_start = self.index
            while self.index < length and text[self.index].isdigit():
                self.index += 1
            if self.index == fraction_start:
                raise self.fail("json.expected_digit_fraction", start)
        if self.index < length and text[self.index] in ("e", "E"):
            is_float = True
            self.index += 1
            if self.index < length and text[self.index] in ("+", "-"):
                self.index += 1
            exponent_start = self.index
            while self.index < length and text[self.index].isdigit():
                self.index += 1
            if self.index == exponent_start:
                raise self.fail("json.expected_digit_exponent", start)
        raw = text[start : self.index]
        return float(raw) if is_float else int(raw)


def parse(text: str, allow_comments: bool = True, allow_trailing_comma: bool = True) -> ParsedDocument:
    """Parse ``text``, recording the source position of every key and element.

    Raises :class:`JsonSyntaxError` if the document cannot be parsed.
    """
    parser = _Parser(text, allow_comments=allow_comments, allow_trailing_comma=allow_trailing_comma)
    value = parser.parse_document()
    return ParsedDocument(value=value, issues=parser.issues)


def parse_fast(text: str) -> ParsedDocument:
    """Parse without position tracking, for documents we only need to load.

    Bedrock models and animations are megabytes of numbers that no validator
    inspects key-by-key, so they go through ``json.loads`` after comments are
    blanked out.  Anything the C parser rejects -- a trailing comma, say, which
    TaCZ's own parser tolerates -- falls back to the full parser so the message
    and the lenient-construct handling stay identical.
    """
    stripped = strip_comments(text.lstrip("\ufeff"))
    try:
        return ParsedDocument(value=json.loads(stripped), issues=[])
    except ValueError:
        return parse(text)
