"""Layer 7: the Lua scripts a pack ships, checked without a Lua VM.

TaCZ runs these through a sandboxed LuaJ 3.0 (Lua 5.2), and Lua is forgiving in
exactly the wrong way for a data pack: a mistyped constant is ``nil``, a missing
library is ``nil``, and a module that forgets to return itself simply loads as
nothing.  None of that surfaces until the gun misbehaves in game, which is what
this checker exists to move forward in time.

Parsing needs ``luaparser``.  It is an optional extra, so when it is absent the
syntax-dependent checks report themselves as skipped rather than silently
passing -- an unchecked script must never look like a clean one.
"""

from __future__ import annotations

import contextlib
import difflib
import io
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..core.context import ValidationContext
from ..core.i18n import Message
from ..core.result import Code, Severity, ValidationResult
from ..core.validator import Validator, register

#: Only these two resource kinds are Lua; both are declared in the rule set.
_SCRIPT_KINDS = ("client_script", "server_script")


def _load_parser():
    """Return the ``luaparser.ast`` module, or ``None`` when it is not installed."""
    try:
        from luaparser import ast  # noqa: F401  (imported for its side effect too)

        return ast
    except ImportError:
        return None


@register
class LuaScriptValidator(Validator):
    name = "lua-script"
    description = "Lua syntax, undefined globals, sandbox limits and module exports"
    order = 70

    def validate(self, context: ValidationContext) -> Iterable[ValidationResult]:
        scripts = self._script_files(context)
        if not scripts:
            return

        parser = _load_parser()
        if parser is None:
            # One note for the run, not one per file: the user has a single
            # thing to do about it, and a wall of identical notes buries the
            # findings that do have a fix.
            yield context.info(
                Code.LUA_PARSER_MISSING,
                Message("lua.parser_missing", {"count": len(scripts)}),
                suggestion=Message("suggestion.install_luaparser"),
            )
            return

        known = context.rules.lua_known_globals
        unavailable = context.rules.lua_unavailable_globals
        constants = context.rules.lua_constants
        replacements = context.rules.lua_replacements

        for relative in scripts:
            text = self._read(context, relative)
            if text is None:
                # TaCZ decodes scripts as UTF-8, so a file saved as Shift-JIS
                # is broken in game. Reporting beats skipping: a script nobody
                # mentions looks like a script nobody found fault with.
                yield context.error(
                    Code.LUA_ENCODING,
                    Message("lua.encoding"),
                    file=relative,
                    suggestion=Message("suggestion.save_as_utf8"),
                )
                continue
            try:
                tree = _parse_quietly(parser, text)
            except Exception as exc:  # luaparser raises SyntaxException and friends
                line, column, message, suggestion = _diagnose(parser, text, exc)
                yield context.error(
                    Code.LUA_SYNTAX,
                    message,
                    file=relative,
                    line=line,
                    column=column,
                    suggestion=suggestion,
                )
                continue  # every later check needs an AST

            analysis = _analyse(parser, tree)
            positions = _positions(parser, text)

            # One finding per name per file, anchored at its first use: a
            # constant left undeclared is one mistake to fix however many times
            # the script goes on to read it.
            for name in sorted(analysis.free_names):
                if name in known:
                    continue
                line = positions.first(name)
                if name in unavailable:
                    yield context.error(
                        Code.LUA_UNAVAILABLE_LIBRARY,
                        Message("lua.unavailable_library", {"name": name}),
                        file=relative,
                        line=line,
                        suggestion=_library_advice(name, replacements.get(name)),
                    )
                    continue
                yield context.warning(
                    Code.LUA_UNDEFINED_GLOBAL,
                    Message("lua.undefined_global", {"name": name}),
                    file=relative,
                    line=line,
                    suggestion=_suggest(name, constants),
                )

            if not analysis.returns_value:
                # Naming the table the script actually built beats telling the
                # author to "return M" when their table is called something else.
                module = analysis.module_name
                yield context.error(
                    Code.LUA_NO_MODULE_RETURN,
                    Message("lua.no_module_return"),
                    file=relative,
                    line=positions.first(module) if module else None,
                    suggestion=Message(
                        "suggestion.return_module", {"name": module or "M"}
                    ),
                )

            for module in sorted(analysis.requires):
                yield from self._check_require(
                    context, relative, module, positions.first_string(module)
                )

    # -- collecting ----------------------------------------------------------

    @staticmethod
    def _script_files(context: ValidationContext) -> List[str]:
        """Every ``.lua`` in a directory the rule set calls a script directory."""
        directories = []
        for name in _SCRIPT_KINDS:
            kind = context.rules.kind(name)
            if kind is None:
                continue
            for namespace in sorted(context.index.namespaces):
                directories.append(kind.directory_for(namespace) + "/")
        return sorted(
            path
            for path in context.index.files
            if path.endswith(".lua") and any(path.startswith(d) for d in directories)
        )

    @staticmethod
    def _read(context: ValidationContext, relative: str) -> Optional[str]:
        try:
            return context.index.source.read_bytes(relative).decode("utf-8")
        except (OSError, KeyError, UnicodeDecodeError):
            return None

    # -- require -------------------------------------------------------------

    def _check_require(
        self, context: ValidationContext, relative: str, module: str, line: Optional[int]
    ) -> Iterable[ValidationResult]:
        """``require("ns_some_script")`` must name a script this pack ships.

        TaCZ registers each script as ``<namespace>_<path>``, so the module name
        is the resource id with its punctuation flattened -- and because that
        flattening is lossy, the namespace is found by trying each one the pack
        declares rather than by splitting on the first underscore.
        """
        for namespace in sorted(context.index.namespaces):
            prefix = namespace + "_"
            if not module.startswith(prefix):
                continue
            path = module[len(prefix):]
            for name in _SCRIPT_KINDS:
                kind = context.rules.kind(name)
                if kind is None:
                    continue
                for candidate in kind.relative_paths(namespace, path):
                    if context.index.exists(candidate):
                        return
        if any(module.startswith(ns + "_") for ns in context.rules.known_namespaces):
            return  # tacz_default_state_machine and friends live in the mod
        if any(module.startswith(ns + "_") for ns in context.settings.external_namespaces):
            return
        yield context.error(
            Code.LUA_REQUIRE_UNRESOLVED,
            Message("lua.require_unresolved", {"module": module}),
            file=relative,
            line=line,
            suggestion=Message("suggestion.require_format"),
        )


def _suggest(name: str, constants: List[str]) -> Message:
    """The closest TaCZ constant when it looks like a typo, advice otherwise.

    Always something: "this is nil at runtime" with no next step leaves the
    reader to work out whether they mistyped a constant or forgot a local.
    """
    close = difflib.get_close_matches(name, constants, n=1, cutoff=0.8)
    if close:
        return Message("suggestion.did_you_mean", {"value": close[0]})
    return Message("suggestion.lua_declare_or_check", {"name": name})


_POSITION = re.compile(r"line (\d+):(\d+)")

#: ANTLR's wording -> what to tell the author, and what to do about it.
#: Ordered: the specific readings come before the general ones they would
#: otherwise be swallowed by.
_SYNTAX_RULES = (
    # Anything left over once the file should have ended: a spare "end" is the
    # most common, and by far the most common way a hand-edited state machine
    # stops parsing at all.
    (
        re.compile(r"^mismatched input '(?P<found>.*)' expecting <EOF>", re.S),
        "lua.syntax_extra_token",
        "suggestion.lua_remove_token",
    ),
    # "if a = 2" -- Lua assigns with = and compares with ==, and the parser
    # complains about the missing "then" rather than about the operator.
    (
        re.compile(r"^mismatched input '=' expecting"),
        "lua.syntax_assign_in_condition",
        "suggestion.lua_use_double_equals",
    ),
    (
        re.compile(r"^token recognition error at: '!'"),
        "lua.syntax_not_equal",
        "suggestion.lua_use_tilde_equals",
    ),
    (
        re.compile(r"""^token recognition error at: ['"]['"]?"""),
        "lua.syntax_unterminated_string",
        "suggestion.lua_close_string",
    ),
    (
        re.compile(r"^token recognition error at: '(?P<found>.*)'", re.S),
        "lua.syntax_bad_character",
        "suggestion.lua_remove_token",
    ),
    # An unclosed block is the commonest syntax error there is, and reads far
    # better as its own sentence than as "missing end before the end of file".
    (
        re.compile(r"^missing '?(?P<expected>[^']+?)'? at '<EOF>'"),
        "lua.syntax_unclosed",
        "suggestion.lua_insert_token",
    ),
    (
        re.compile(r"^missing '?(?P<expected>[^']+?)'? at '(?P<found>.*)'", re.S),
        "lua.syntax_missing",
        "suggestion.lua_insert_token",
    ),
    (
        re.compile(r"^extraneous input '(?P<found>.*)' expecting", re.S),
        "lua.syntax_extraneous",
        "suggestion.lua_remove_token",
    ),
    (
        re.compile(r"^mismatched input '(?P<found>.*)' expecting (?P<expected>.+)$", re.S),
        "lua.syntax_mismatched",
        "suggestion.lua_check_this_line",
    ),
    (
        re.compile(r"^no viable alternative", re.S),
        "lua.syntax_unparseable",
        "suggestion.lua_check_this_line",
    ),
)


def _readable(token: str):
    """Tidy one token for display.

    ANTLR names the end of the file ``<EOF>`` and quotes the tokens it expected;
    neither is what a pack author typed. The end-of-file marker becomes a nested
    message so it still reads as a phrase in both languages.
    """
    token = (token or "").strip()
    if token == "<EOF>":
        return Message("lua.token_eof")
    if len(token) > 1 and token[0] == token[-1] and token[0] in "'\"":
        token = token[1:-1]
    return token


def _explain(detail: str) -> Tuple[Message, Optional[Message]]:
    """Turn one ANTLR diagnostic into a sentence and, where there is one, a fix."""
    for pattern, key, suggestion_key in _SYNTAX_RULES:
        match = pattern.match(detail)
        if match is None:
            continue
        params = {name: _readable(value or "") for name, value in match.groupdict().items()}
        suggestion = Message(suggestion_key, dict(params)) if suggestion_key else None
        return Message(key, params), suggestion
    # Unmapped wording is still worth showing verbatim: a diagnostic nobody
    # translated beats no diagnostic at all.
    return Message("lua.syntax", {"detail": detail}), None


def _parse_quietly(parser, text: str):
    """Parse, without luaparser printing ANTLR's wording to the terminal.

    luaparser attaches a console listener to its lexer, so a script with an
    unterminated string writes "token recognition error at ..." to stderr behind
    the report -- the raw diagnostic this checker exists to replace. The listener
    is created inside parse(), so the only way to silence it from outside is to
    take stderr for the duration of the call.

    Redirecting is process-wide, and validation runs on a worker thread in the
    GUI, so this deliberately wraps the single call rather than the whole run:
    the window is one parse, and what it could swallow is another thread's
    logging, never a finding.
    """
    with contextlib.redirect_stderr(io.StringIO()):
        return parser.parse(text)


def _diagnose(parser, text: str, exc: Exception):
    """Locate and explain the first syntax error in ``text``.

    luaparser parses with ANTLR's bail strategy, which is fast but throws away
    the position for most parser errors -- half the ways a script can break came
    back as "syntax errors: None". Re-parsing with the default strategy, only
    for a file already known to be broken, recovers a line and column for every
    case at no cost to the files that are fine.
    """
    line, column, detail = _reparse(parser, text)
    if detail is None:
        line, column, detail = _from_message(exc)
    message, suggestion = _explain(detail)
    return line, column, message, suggestion


def _reparse(parser, text: str):
    """Run ANTLR again with error recovery on, and keep the first complaint."""
    try:
        found = []

        class Collect(parser.ErrorListener):
            def syntaxError(self, recognizer, symbol, line, column, message, error):
                found.append((line, column, message))

        collector = Collect()
        lexer = parser.LuaLexer(parser.InputStream(text))
        lexer.removeErrorListeners()
        lexer.addErrorListener(collector)
        antlr = parser.LuaParser(parser.CommonTokenStream(lexer))
        antlr.removeErrorListeners()
        antlr.addErrorListener(collector)
        antlr.start_()
    except Exception:  # pragma: no cover - falls back to the thrown message
        return None, None, None
    if not found:
        return None, None, None
    line, column, detail = found[0]
    # ANTLR counts columns from zero; every other position this tool reports
    # counts from one, and a report that mixes both is worse than useless.
    return line, column + 1, detail


def _from_message(exc: Exception) -> Tuple[Optional[int], Optional[int], str]:
    """Last resort: luaparser embeds a position in some of its messages."""
    text = str(exc).strip()
    match = _POSITION.search(text)
    if match is None:
        return None, None, text
    detail = text[match.end():].lstrip(": ").strip() or text
    return int(match.group(1)), int(match.group(2)) + 1, detail


def _library_advice(name: str, replacement: Optional[str]) -> Message:
    if replacement:
        return Message("suggestion.lua_use_instead", {"name": name, "replacement": replacement})
    return Message("suggestion.lua_remove_library", {"name": name})


class _Analysis:
    __slots__ = ("bound", "free_names", "requires", "returns_value", "module_name")

    def __init__(self, bound, free_names, requires, returns_value, module_name):
        self.bound = bound  # type: Set[str]
        self.free_names = free_names  # type: Set[str]
        self.requires = requires  # type: Set[str]
        self.returns_value = returns_value  # type: bool
        #: The local this script builds its module table in, when it has one.
        self.module_name = module_name  # type: Optional[str]


class _Positions:
    """Where each identifier and string literal first appears.

    luaparser fills ``Node.line`` in only for some nodes, so positions come from
    a second pass over its lexer's token stream instead -- which also keeps
    comments and string bodies from being mistaken for code.
    """

    __slots__ = ("names", "strings")

    def __init__(self, names, strings):
        self.names = names  # type: Dict[str, int]
        self.strings = strings  # type: Dict[str, int]

    def first(self, name: str) -> Optional[int]:
        return self.names.get(name)

    def first_string(self, value: str) -> Optional[int]:
        return self.strings.get(value)


def _positions(parser, source: str) -> _Positions:
    from luaparser.parser.LuaLexer import LuaLexer

    names = {}  # type: Dict[str, int]
    strings = {}  # type: Dict[str, int]
    try:
        stream = parser.get_token_stream(source)
        stream.fill()
        tokens = stream.tokens
    except Exception:  # pragma: no cover - the source already parsed once
        return _Positions(names, strings)

    labels = LuaLexer.symbolicNames
    for token in tokens:
        label = labels[token.type] if 0 <= token.type < len(labels) else ""
        if label == "NAME":
            names.setdefault(token.text, token.line)
        elif label in ("NORMALSTRING", "CHARSTRING", "LONGSTRING"):
            strings.setdefault(token.text[1:-1], token.line)
    return _Positions(names, strings)


def _analyse(parser, tree) -> _Analysis:
    """Collect the facts the checks need from one parsed script.

    Scoping is deliberately flattened: a name bound anywhere in the file counts
    as bound everywhere.  That under-reports shadowing mistakes and over-reports
    nothing, which is the right way round for a checker whose findings a pack
    author is expected to trust.
    """
    from luaparser import astnodes

    skip = set()  # type: Set[int]   # id() of Name nodes that are not variable reads
    bound = set()  # type: Set[str]
    requires = set()  # type: Set[str]

    for node in parser.walk(tree):
        if isinstance(node, astnodes.Index) and isinstance(node.idx, astnodes.Name):
            skip.add(id(node.idx))  # a.b -- b is a field, not a variable
        elif isinstance(node, astnodes.Invoke) and isinstance(node.func, astnodes.Name):
            skip.add(id(node.func))  # a:b() -- b is a method name
        elif isinstance(node, astnodes.Field) and isinstance(node.key, astnodes.Name):
            skip.add(id(node.key))  # {b = 1} -- b is a key
        elif isinstance(node, astnodes.Method) and isinstance(node.name, astnodes.Name):
            skip.add(id(node.name))

        for target in _targets(astnodes, node):
            if isinstance(target, astnodes.Name):
                bound.add(target.id)
                skip.add(id(target))
        if isinstance(node, astnodes.Method):
            bound.add("self")  # implicit first parameter of function t:m()

        if isinstance(node, astnodes.Call) and isinstance(node.func, astnodes.Name):
            if node.func.id == "require" and len(node.args) == 1:
                argument = node.args[0]
                if isinstance(argument, astnodes.String):
                    # luaparser hands string literals back as bytes.
                    raw = argument.s
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", "replace")
                    requires.add(raw)

    free = set()  # type: Set[str]
    for node in parser.walk(tree):
        if not isinstance(node, astnodes.Name) or id(node) in skip:
            continue
        if node.id not in bound:
            free.add(node.id)

    body = getattr(tree, "body", None)
    statements = getattr(body, "body", []) or []
    returns_value = any(
        isinstance(s, astnodes.Return) and s.values for s in statements
    )
    return _Analysis(bound, free, requires, returns_value, _module_name(astnodes, statements))


def _module_name(astnodes, statements) -> Optional[str]:
    """The top-level local holding a table -- the thing a module returns.

    Taken from the last such local rather than the first: a script that pulls in
    a default state machine assigns that first and builds its own table after.
    """
    found = None
    for statement in statements:
        if not isinstance(statement, astnodes.LocalAssign):
            continue
        for target, value in zip(statement.targets or [], statement.values or []):
            if isinstance(target, astnodes.Name) and isinstance(value, astnodes.Table):
                found = target.id
    return found


def _targets(astnodes, node):
    """The names a statement binds."""
    if isinstance(node, (astnodes.LocalAssign, astnodes.Assign)):
        return node.targets or []
    if isinstance(node, astnodes.Forin):
        return node.targets or []
    if isinstance(node, astnodes.Fornum):
        return [node.target]
    if isinstance(node, (astnodes.Function, astnodes.LocalFunction,
                         astnodes.AnonymousFunction, astnodes.Method)):
        targets = list(node.args or [])
        name = getattr(node, "name", None)
        if isinstance(name, astnodes.Name) and not isinstance(node, astnodes.Method):
            targets.append(name)
        return targets
    return []
