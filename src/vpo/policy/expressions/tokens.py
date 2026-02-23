"""Token types and data structures for the expression lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """All token types in the expression language."""

    # Literals
    IDENT = auto()  # bare identifier: audio, eng, hevc
    STRING = auto()  # quoted string: "commentary", 'dts-hd'
    NUMBER = auto()  # integer or float: 42, 3.14
    SIZE_LITERAL = auto()  # number with size suffix: 15M, 1GB, 192k
    BOOLEAN = auto()  # true, false

    # Delimiters
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    COMMA = auto()  # ,

    # Comparison operators
    OP_EQ = auto()  # ==
    OP_NEQ = auto()  # !=
    OP_LT = auto()  # <
    OP_LTE = auto()  # <=
    OP_GT = auto()  # >
    OP_GTE = auto()  # >=

    # Keyword operators
    OP_IN = auto()  # in
    KW_AND = auto()  # and
    KW_OR = auto()  # or
    KW_NOT = auto()  # not

    # End of input
    EOF = auto()


# Keywords that map to specific token types
KEYWORDS: dict[str, TokenType] = {
    "and": TokenType.KW_AND,
    "or": TokenType.KW_OR,
    "not": TokenType.KW_NOT,
    "in": TokenType.OP_IN,
    "true": TokenType.BOOLEAN,
    "false": TokenType.BOOLEAN,
}


@dataclass(frozen=True)
class Token:
    """A single token produced by the lexer."""

    type: TokenType
    value: str
    position: int  # character offset in source
    line: int
    column: int
