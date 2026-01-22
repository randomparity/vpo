"""Phase executor package.

This package provides the PhaseExecutor class and related types for executing
user-defined phases in phased policies.

Re-exports for backward compatibility:
- PhaseExecutor: Main executor class
- OperationResult: Result of a single operation
- PhaseExecutionState: Mutable state during phase execution
"""

from .executor import PhaseExecutor
from .types import OperationResult, PhaseExecutionState

__all__ = [
    "OperationResult",
    "PhaseExecutionState",
    "PhaseExecutor",
]
