"""Evaluation exception classes.

This module defines exception classes used during policy evaluation.
"""

from __future__ import annotations


class EvaluationError(Exception):
    """Base class for evaluation errors."""

    pass


class NoTracksError(EvaluationError):
    """File has no tracks to evaluate."""

    pass


class UnsupportedContainerError(EvaluationError):
    """Container format not supported for requested operations."""

    def __init__(self, container: str, operation: str) -> None:
        self.container = container
        self.operation = operation
        super().__init__(
            f"Container '{container}' does not support {operation}. "
            "Consider converting to MKV for full track manipulation support."
        )
