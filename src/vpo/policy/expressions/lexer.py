"""Lexer (tokenizer) for the policy expression language.

Converts a source string into a list of tokens via a single-pass
character scanner.
"""

from __future__ import annotations

import re

from vpo.policy.expressions.errors import LexError
from vpo.policy.expressions.tokens import KEYWORDS, Token, TokenType

# Size suffix pattern: digits optionally followed by a decimal,
# then a size unit. Matched BEFORE plain numbers during lexing.
_SIZE_SUFFIX_RE = re.compile(r"\d+(\.\d+)?(GB|MB|TB|KB|gb|mb|tb|kb|[kKmMgGtT])\b")

# Lookup tables for operator and punctuation tokens
_TWO_CHAR_OPS: dict[str, TokenType] = {
    "==": TokenType.OP_EQ,
    "!=": TokenType.OP_NEQ,
    "<=": TokenType.OP_LTE,
    ">=": TokenType.OP_GTE,
}

_SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "<": TokenType.OP_LT,
    ">": TokenType.OP_GT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
}


def tokenize(source: str) -> list[Token]:
    """Tokenize a policy expression string.

    Args:
        source: The expression string to tokenize.

    Returns:
        List of tokens, always ending with an EOF token.

    Raises:
        LexError: On invalid characters or unterminated strings.
    """
    tokens: list[Token] = []
    pos = 0
    line = 1
    col = 1
    length = len(source)

    while pos < length:
        ch = source[pos]

        # Skip whitespace
        if ch in " \t\r\n":
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        start_pos = pos
        start_col = col

        # Two-character operators (check before single-char)
        if pos + 1 < length:
            two = source[pos : pos + 2]
            two_type = _TWO_CHAR_OPS.get(two)
            if two_type is not None:
                tokens.append(Token(two_type, two, start_pos, line, start_col))
                pos += 2
                col += 2
                continue

        # Single-character tokens
        single_type = _SINGLE_CHAR_TOKENS.get(ch)
        if single_type is not None:
            tokens.append(Token(single_type, ch, start_pos, line, start_col))
            pos += 1
            col += 1
            continue

        # Quoted strings
        if ch in ('"', "'"):
            token = _scan_string(source, pos, line, start_col)
            tokens.append(token)
            consumed = len(token.value) + 2  # +2 for quotes
            pos += consumed
            col += consumed
            continue

        # Numbers and size literals (digits first)
        if ch.isdigit():
            token = _scan_number_or_size(source, pos, line, start_col)
            tokens.append(token)
            consumed = len(token.value)
            pos += consumed
            col += consumed
            continue

        # Identifiers and keywords
        if ch.isalpha() or ch == "_":
            token = _scan_identifier(source, pos, line, start_col)
            tokens.append(token)
            consumed = len(token.value)
            pos += consumed
            col += consumed
            continue

        raise LexError(
            f"Unexpected character: '{ch}'",
            source=source,
            position=start_pos,
            line=line,
            column=start_col,
        )

    tokens.append(Token(TokenType.EOF, "", pos, line, col))
    return tokens


def _scan_string(source: str, pos: int, line: int, col: int) -> Token:
    """Scan a quoted string starting at pos."""
    quote = source[pos]
    start = pos + 1
    end = start
    while end < len(source):
        if source[end] == quote:
            value = source[start:end]
            return Token(TokenType.STRING, value, pos, line, col)
        end += 1
    raise LexError(
        f"Unterminated string starting with {quote}",
        source=source,
        position=pos,
        line=line,
        column=col,
    )


def _scan_number_or_size(source: str, pos: int, line: int, col: int) -> Token:
    """Scan a number or size literal starting at pos.

    Size literals are numbers followed by a size suffix (k, M, G, etc.).
    """
    # Try size literal match first (greedy)
    m = _SIZE_SUFFIX_RE.match(source, pos)
    if m:
        value = m.group(0)
        return Token(TokenType.SIZE_LITERAL, value, pos, line, col)

    # Plain number (integer or float)
    end = pos
    has_dot = False
    while end < len(source) and (source[end].isdigit() or source[end] == "."):
        if source[end] == ".":
            if has_dot:
                break
            has_dot = True
        end += 1

    # Check if followed by alpha (possible size suffix we missed)
    if end < len(source) and source[end].isalpha():
        suffix_start = end
        while end < len(source) and source[end].isalpha():
            end += 1
        suffix = source[suffix_start:end].lower()
        valid_suffixes = {"k", "kb", "m", "mb", "g", "gb", "t", "tb"}
        if suffix not in valid_suffixes:
            raise LexError(
                f"Invalid size suffix: '{source[suffix_start:end]}'"
                f" (expected one of: {', '.join(sorted(valid_suffixes))})",
                source=source,
                position=pos,
                line=line,
                column=col,
            )
        value = source[pos:end]
        return Token(TokenType.SIZE_LITERAL, value, pos, line, col)

    value = source[pos:end]
    return Token(TokenType.NUMBER, value, pos, line, col)


def _scan_identifier(source: str, pos: int, line: int, col: int) -> Token:
    """Scan an identifier or keyword starting at pos.

    Identifiers: [a-zA-Z_][a-zA-Z0-9_-]*
    Keywords: and, or, not, in, true, false
    """
    end = pos
    while end < len(source) and (source[end].isalnum() or source[end] in ("_", "-")):
        end += 1
    value = source[pos:end]

    # Check for keywords
    keyword_type = KEYWORDS.get(value.lower())
    if keyword_type is not None and value == value.lower():
        return Token(keyword_type, value, pos, line, col)

    return Token(TokenType.IDENT, value, pos, line, col)
