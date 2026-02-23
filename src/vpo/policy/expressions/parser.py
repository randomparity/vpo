"""Recursive descent parser for the policy expression language.

Parses expression strings into existing Condition dataclasses from
vpo.policy.types.conditions. The grammar is:

    expression = or_expr
    or_expr    = and_expr ('or' and_expr)*
    and_expr   = not_expr ('and' not_expr)*
    not_expr   = 'not' not_expr | atom
    atom       = '(' expression ')' | func_or_comparison
    func_or_comparison = IDENT '(' args? ')' (op value)?
    args       = arg (',' arg)*
    arg        = IDENT op value | IDENT
    op         = '==' | '!=' | '<' | '<=' | '>' | '>=' | 'in'
    value      = STRING | NUMBER | SIZE | IDENT | BOOLEAN | list
    list       = '[' value (',' value)* ']'
"""

from __future__ import annotations

from typing import Any

from vpo.policy.expressions.errors import ParseError
from vpo.policy.expressions.lexer import tokenize
from vpo.policy.expressions.tokens import Token, TokenType
from vpo.policy.types.conditions import (
    AndCondition,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    Condition,
    ContainerMetadataCondition,
    CountCondition,
    ExistsCondition,
    IsDubbedCondition,
    IsOriginalCondition,
    MetadataComparisonOperator,
    NotCondition,
    OrCondition,
    PluginMetadataCondition,
    TrackFilters,
)

# Mapping from expression operator tokens to ComparisonOperator
_COMPARISON_OPS: dict[TokenType, ComparisonOperator] = {
    TokenType.OP_EQ: ComparisonOperator.EQ,
    TokenType.OP_LT: ComparisonOperator.LT,
    TokenType.OP_LTE: ComparisonOperator.LTE,
    TokenType.OP_GT: ComparisonOperator.GT,
    TokenType.OP_GTE: ComparisonOperator.GTE,
}

# Token types that represent comparison operators
_OP_TOKENS = frozenset(
    {
        TokenType.OP_EQ,
        TokenType.OP_NEQ,
        TokenType.OP_LT,
        TokenType.OP_LTE,
        TokenType.OP_GT,
        TokenType.OP_GTE,
        TokenType.OP_IN,
    }
)

# Mapping from expression operator tokens to MetadataComparisonOperator
_METADATA_OPS: dict[TokenType, MetadataComparisonOperator] = {
    TokenType.OP_EQ: MetadataComparisonOperator.EQ,
    TokenType.OP_NEQ: MetadataComparisonOperator.NEQ,
    TokenType.OP_LT: MetadataComparisonOperator.LT,
    TokenType.OP_LTE: MetadataComparisonOperator.LTE,
    TokenType.OP_GT: MetadataComparisonOperator.GT,
    TokenType.OP_GTE: MetadataComparisonOperator.GTE,
}

# Filter name aliases: expression name -> TrackFilters field
_FILTER_ALIASES: dict[str, str] = {
    "lang": "language",
    "language": "language",
    "codec": "codec",
    "channels": "channels",
    "height": "height",
    "width": "width",
    "default": "is_default",
    "forced": "is_forced",
    "title": "title",
    "not_commentary": "not_commentary",
}

# Valid track types for exists()/count()
_VALID_TRACK_TYPES = frozenset({"video", "audio", "subtitle", "attachment"})


def parse_expression(source: str) -> Condition:
    """Parse an expression string into a Condition dataclass.

    Args:
        source: The expression string to parse.

    Returns:
        A Condition dataclass instance.

    Raises:
        ParseError: If the expression is invalid.
    """
    if not source or not source.strip():
        raise ParseError(
            "Empty expression",
            source=source,
            position=0,
        )

    tokens = tokenize(source)
    parser = _Parser(tokens, source)
    result = parser.parse_expression()

    # Ensure all tokens consumed
    if parser.current().type != TokenType.EOF:
        tok = parser.current()
        raise ParseError(
            f"Unexpected token '{tok.value}' after expression",
            source=source,
            position=tok.position,
            line=tok.line,
            column=tok.column,
        )

    return result


_MAX_DEPTH = 50  # Guard against pathological nesting


class _Parser:
    """Recursive descent parser for condition expressions."""

    def __init__(self, tokens: list[Token], source: str) -> None:
        self._tokens = tokens
        self._source = source
        self._pos = 0
        self._depth = 0

    def current(self) -> Token:
        """Return the current token without consuming it."""
        return self._tokens[self._pos]

    def advance(self) -> Token:
        """Consume and return the current token."""
        tok = self._tokens[self._pos]
        if tok.type != TokenType.EOF:
            self._pos += 1
        return tok

    def expect(self, token_type: TokenType) -> Token:
        """Consume the current token, raising if it doesn't match."""
        tok = self.current()
        if tok.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got '{tok.value}'",
                source=self._source,
                position=tok.position,
                line=tok.line,
                column=tok.column,
            )
        return self.advance()

    def _error(self, message: str) -> ParseError:
        """Create a ParseError at the current position."""
        tok = self.current()
        return ParseError(
            message,
            source=self._source,
            position=tok.position,
            line=tok.line,
            column=tok.column,
        )

    # --- Grammar productions ---

    def parse_expression(self) -> Condition:
        """expression = or_expr"""
        return self._parse_or_expr()

    def _parse_or_expr(self) -> Condition:
        """or_expr = and_expr ('or' and_expr)*"""
        left = self._parse_and_expr()
        parts = [left]
        while self.current().type == TokenType.KW_OR:
            self.advance()
            parts.append(self._parse_and_expr())
        if len(parts) == 1:
            return parts[0]
        return OrCondition(conditions=tuple(parts))

    def _parse_and_expr(self) -> Condition:
        """and_expr = not_expr ('and' not_expr)*"""
        left = self._parse_not_expr()
        parts = [left]
        while self.current().type == TokenType.KW_AND:
            self.advance()
            parts.append(self._parse_not_expr())
        if len(parts) == 1:
            return parts[0]
        return AndCondition(conditions=tuple(parts))

    def _parse_not_expr(self) -> Condition:
        """not_expr = 'not' not_expr | atom"""
        if self.current().type == TokenType.KW_NOT:
            self.advance()
            inner = self._parse_not_expr()
            return NotCondition(inner=inner)
        return self._parse_atom()

    def _parse_atom(self) -> Condition:
        """atom = '(' expression ')' | func_or_comparison"""
        tok = self.current()

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._depth += 1
            if self._depth > _MAX_DEPTH:
                raise self._error(
                    f"Expression nesting exceeds maximum depth of {_MAX_DEPTH}"
                )
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            self._depth -= 1
            return expr

        # Function call (IDENT followed by LPAREN)
        if tok.type == TokenType.IDENT:
            return self._parse_func_or_comparison()

        raise self._error(f"Expected function call or '(', got '{tok.value}'")

    def _parse_func_or_comparison(self) -> Condition:
        """func_or_comparison = IDENT '(' args? ')' (op value)?"""
        name_tok = self.advance()
        name = name_tok.value.lower()

        self.expect(TokenType.LPAREN)

        # Parse arguments
        args: list[tuple[str, Any]] = []  # (name, value) pairs
        positional: list[str] = []

        if self.current().type != TokenType.RPAREN:
            self._parse_args(args, positional)

        self.expect(TokenType.RPAREN)

        # Check for trailing comparison: func(...) op value
        trailing_op: TokenType | None = None
        trailing_value: Any = None
        if self.current().type in _OP_TOKENS:
            trailing_op = self.current().type
            self.advance()
            trailing_value = self._parse_value()

        # Dispatch to condition builder
        return self._build_condition(
            name, name_tok, positional, args, trailing_op, trailing_value
        )

    def _parse_args(
        self,
        named: list[tuple[str, Any]],
        positional: list[str],
    ) -> None:
        """Parse function arguments: positional identifiers and named filters."""
        self._parse_single_arg(named, positional)
        while self.current().type == TokenType.COMMA:
            self.advance()
            self._parse_single_arg(named, positional)

    def _parse_single_arg(
        self,
        named: list[tuple[str, Any]],
        positional: list[str],
    ) -> None:
        """Parse a single argument: IDENT op value | IDENT"""
        tok = self.current()

        if tok.type == TokenType.IDENT:
            # Look ahead: if next token is an operator, this is a named arg
            next_tok = (
                self._tokens[self._pos + 1]
                if self._pos + 1 < len(self._tokens)
                else None
            )
            if next_tok and next_tok.type in _OP_TOKENS:
                # Named argument: IDENT op value
                name = self.advance().value.lower()
                op_tok = self.advance()
                value = self._parse_value()
                named.append((name, (op_tok.type, value)))
                return
            # Bare identifier (positional)
            positional.append(self.advance().value)
            return

        # Could be a value in some contexts
        raise self._error(f"Expected identifier, got '{tok.value}'")

    def _parse_value(self) -> Any:
        """Parse a value: STRING | NUMBER | SIZE | IDENT | BOOLEAN | list"""
        tok = self.current()

        if tok.type == TokenType.STRING:
            self.advance()
            return tok.value

        if tok.type == TokenType.NUMBER:
            self.advance()
            if "." in tok.value:
                return float(tok.value)
            return int(tok.value)

        if tok.type == TokenType.SIZE_LITERAL:
            self.advance()
            return tok.value

        if tok.type == TokenType.BOOLEAN:
            self.advance()
            return tok.value.lower() == "true"

        if tok.type == TokenType.IDENT:
            self.advance()
            return tok.value

        if tok.type == TokenType.LBRACKET:
            return self._parse_list()

        raise self._error(f"Expected value, got '{tok.value}'")

    def _parse_list(self) -> list[Any]:
        """Parse a list value: '[' value (',' value)* ']'"""
        self.expect(TokenType.LBRACKET)
        values = [self._parse_value()]
        while self.current().type == TokenType.COMMA:
            self.advance()
            values.append(self._parse_value())
        self.expect(TokenType.RBRACKET)
        return values

    # --- Condition builders ---

    # Class-level dispatch map: function name -> builder method name.
    # Avoids rebuilding a dict of bound methods on every _build_condition call.
    _BUILDER_METHODS: dict[str, str] = {
        "exists": "_build_exists",
        "count": "_build_count",
        "multi_language": "_build_multi_language",
        "plugin": "_build_plugin",
        "container_meta": "_build_container_meta",
        "is_original": "_build_is_original",
        "is_dubbed": "_build_is_dubbed",
    }

    def _build_condition(
        self,
        func_name: str,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> Condition:
        """Dispatch to the appropriate condition builder based on function name."""
        method_name = self._BUILDER_METHODS.get(func_name)
        if method_name is None:
            raise ParseError(
                f"Unknown function: '{func_name}'",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        builder = getattr(self, method_name)
        return builder(name_tok, positional, named, trailing_op, trailing_value)

    def _build_exists(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> ExistsCondition:
        """Build ExistsCondition from exists(track_type, filters...)."""
        if not positional:
            raise ParseError(
                "exists() requires a track type argument"
                " (video, audio, subtitle, attachment)",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        track_type = positional[0].lower()
        if track_type not in _VALID_TRACK_TYPES:
            raise ParseError(
                f"Invalid track type: '{track_type}'. "
                f"Expected one of: {', '.join(sorted(_VALID_TRACK_TYPES))}",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        if trailing_op is not None:
            raise ParseError(
                "exists() does not support trailing comparison operators",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        filters = self._build_track_filters(named, name_tok)
        return ExistsCondition(track_type=track_type, filters=filters)

    def _build_count(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> CountCondition:
        """Build CountCondition from count(track_type, filters...) op value."""
        if not positional:
            raise ParseError(
                "count() requires a track type argument",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        track_type = positional[0].lower()
        if track_type not in _VALID_TRACK_TYPES:
            raise ParseError(
                f"Invalid track type: '{track_type}'",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        if trailing_op is None:
            raise ParseError(
                "count() requires a trailing comparison (e.g., count(audio) >= 2)",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        if trailing_op not in _COMPARISON_OPS:
            raise ParseError(
                "count() only supports ==, <, <=, >, >="
                f" operators (not {trailing_op.name})",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        if not isinstance(trailing_value, int):
            raise ParseError(
                "count() comparison value must be an integer,"
                f" got {type(trailing_value).__name__}",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        filters = self._build_track_filters(named, name_tok)
        return CountCondition(
            track_type=track_type,
            filters=filters,
            operator=_COMPARISON_OPS[trailing_op],
            value=trailing_value,
        )

    def _build_multi_language(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> AudioIsMultiLanguageCondition:
        """Build AudioIsMultiLanguageCondition from multi_language(...)."""
        kwargs: dict[str, Any] = {}
        for name, (op, value) in named:
            if op != TokenType.OP_EQ:
                raise ParseError(
                    "multi_language() only supports == for named arguments",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )
            if name == "threshold":
                try:
                    kwargs["threshold"] = float(value)
                except (TypeError, ValueError) as e:
                    raise ParseError(
                        f"Invalid threshold value: {value!r} ({e})",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    ) from e
            elif name == "track_index":
                try:
                    kwargs["track_index"] = int(value)
                except (TypeError, ValueError) as e:
                    raise ParseError(
                        f"Invalid track_index value: {value!r} ({e})",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    ) from e
            elif name == "primary_language":
                kwargs["primary_language"] = str(value)
            else:
                raise ParseError(
                    f"Unknown multi_language() argument: '{name}'",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )
        return AudioIsMultiLanguageCondition(**kwargs)

    def _build_plugin(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> PluginMetadataCondition:
        """Build PluginMetadataCondition from plugin(name, field) op value."""
        if len(positional) < 2:
            raise ParseError(
                "plugin() requires two positional arguments: plugin(name, field)",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        plugin_name = positional[0].lower()
        field_name = positional[1].lower()

        if trailing_op is None:
            # No trailing op means exists check
            return PluginMetadataCondition(
                plugin=plugin_name,
                field=field_name,
                operator=MetadataComparisonOperator.EXISTS,
            )

        op = _METADATA_OPS.get(trailing_op)
        if op is None:
            if trailing_op == TokenType.OP_IN:
                raise ParseError(
                    "plugin() does not support 'in' operator",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )
            raise ParseError(
                f"Unsupported operator for plugin(): {trailing_op.name}",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        return PluginMetadataCondition(
            plugin=plugin_name,
            field=field_name,
            value=trailing_value,
            operator=op,
        )

    def _build_container_meta(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> ContainerMetadataCondition:
        """Build ContainerMetadataCondition from container_meta(field) op value."""
        if not positional:
            raise ParseError(
                "container_meta() requires a field name argument",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        field_name = positional[0].lower()

        if trailing_op is None:
            return ContainerMetadataCondition(
                field=field_name,
                operator=MetadataComparisonOperator.EXISTS,
            )

        op = _METADATA_OPS.get(trailing_op)
        if op is None:
            raise ParseError(
                "Unsupported operator for container_meta()",
                source=self._source,
                position=name_tok.position,
                line=name_tok.line,
                column=name_tok.column,
            )

        return ContainerMetadataCondition(
            field=field_name,
            value=trailing_value,
            operator=op,
        )

    def _build_is_original(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> IsOriginalCondition:
        """Build IsOriginalCondition from is_original(...)."""
        return self._build_original_dubbed(
            IsOriginalCondition, name_tok, named, "is_original"
        )

    def _build_is_dubbed(
        self,
        name_tok: Token,
        positional: list[str],
        named: list[tuple[str, Any]],
        trailing_op: TokenType | None,
        trailing_value: Any,
    ) -> IsDubbedCondition:
        """Build IsDubbedCondition from is_dubbed(...)."""
        return self._build_original_dubbed(
            IsDubbedCondition, name_tok, named, "is_dubbed"
        )

    def _build_original_dubbed(
        self,
        cls: type,
        name_tok: Token,
        named: list[tuple[str, Any]],
        func_name: str,
    ) -> IsOriginalCondition | IsDubbedCondition:
        """Build IsOriginalCondition or IsDubbedCondition."""
        kwargs: dict[str, Any] = {}
        for name, (op, value) in named:
            if op != TokenType.OP_EQ:
                raise ParseError(
                    f"{func_name}() only supports == for named"
                    " arguments except 'confidence'",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )
            if name in ("lang", "language"):
                kwargs["language"] = str(value)
            elif name in ("confidence", "min_confidence"):
                kwargs["min_confidence"] = float(value)
            elif name == "value":
                kwargs["value"] = (
                    bool(value) if isinstance(value, bool) else value == "true"
                )
            else:
                raise ParseError(
                    f"Unknown {func_name}() argument: '{name}'",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )
        return cls(**kwargs)

    def _build_track_filters(
        self,
        named: list[tuple[str, Any]],
        name_tok: Token,
    ) -> TrackFilters:
        """Build TrackFilters from named arguments like lang == eng, height >= 2160."""
        kwargs: dict[str, Any] = {}

        for name, (op, value) in named:
            field = _FILTER_ALIASES.get(name)
            if field is None:
                raise ParseError(
                    f"Unknown filter: '{name}'. Expected one of:"
                    f" {', '.join(sorted(_FILTER_ALIASES))}",
                    source=self._source,
                    position=name_tok.position,
                    line=name_tok.line,
                    column=name_tok.column,
                )

            if field in ("language", "codec"):
                # String or list values, support both == and 'in'
                if op == TokenType.OP_IN:
                    if isinstance(value, list):
                        kwargs[field] = tuple(str(v) for v in value)
                    else:
                        kwargs[field] = (str(value),)
                elif op == TokenType.OP_EQ:
                    kwargs[field] = str(value)
                else:
                    raise ParseError(
                        f"Filter '{name}' only supports == and 'in' operators",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    )

            elif field in ("channels", "height", "width"):
                # Numeric: exact value or comparison
                if op == TokenType.OP_EQ:
                    kwargs[field] = int(value)
                elif op in _COMPARISON_OPS:
                    kwargs[field] = Comparison(
                        operator=_COMPARISON_OPS[op],
                        value=int(value),
                    )
                else:
                    raise ParseError(
                        f"Filter '{name}' does not support operator {op.name}",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    )

            elif field in ("is_default", "is_forced", "not_commentary"):
                # Boolean
                if op != TokenType.OP_EQ:
                    raise ParseError(
                        f"Filter '{name}' only supports == operator",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    )
                if isinstance(value, bool):
                    kwargs[field] = value
                else:
                    kwargs[field] = str(value).lower() == "true"

            elif field == "title":
                # String match
                if op == TokenType.OP_EQ:
                    kwargs[field] = str(value)
                else:
                    raise ParseError(
                        "Filter 'title' only supports == operator",
                        source=self._source,
                        position=name_tok.position,
                        line=name_tok.line,
                        column=name_tok.column,
                    )

        return TrackFilters(**kwargs)
