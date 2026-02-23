"""Error types for the policy expression language."""

from __future__ import annotations


class ExpressionError(Exception):
    """Base class for expression language errors."""

    def __init__(
        self,
        message: str,
        source: str = "",
        position: int = 0,
        line: int = 1,
        column: int = 1,
    ) -> None:
        self.source = source
        self.position = position
        self.line = line
        self.column = column
        super().__init__(message)

    def format_error(self) -> str:
        """Format error with caret pointing at the problem position."""
        msg = str(self)
        if not self.source:
            return msg
        caret = " " * (self.column - 1) + "^"
        return f"{msg}\n  {self.source}\n  {caret}"


class LexError(ExpressionError):
    """Raised when tokenization fails."""


class ParseError(ExpressionError):
    """Raised when parsing fails."""
