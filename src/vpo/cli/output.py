"""Unified CLI output formatting for JSON and human-readable output.

This module provides consistent error handling and output formatting
across all CLI commands, replacing scattered per-module implementations.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NoReturn

import click

if TYPE_CHECKING:
    from .exit_codes import ExitCode


@dataclass
class CLIResult:
    """Result object for CLI operations.

    Provides consistent JSON serialization for command results.
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 0

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string with status, message, and optional data fields.
        """
        output: dict[str, Any] = {
            "status": "completed" if self.success else "failed",
        }
        if self.success:
            output["message"] = self.message
            output.update(self.data)
        else:
            # Import here to avoid circular imports at module load
            from .exit_codes import ExitCode

            # Get enum name if it's an ExitCode, otherwise use generic
            if isinstance(self.exit_code, ExitCode):
                code_name = self.exit_code.name
            else:
                code_name = "UNKNOWN_ERROR"

            output["error"] = {
                "code": code_name,
                "message": self.message,
            }
        return json.dumps(output, indent=2)


def error_exit(
    message: str,
    code: ExitCode | int,
    json_output: bool = False,
) -> NoReturn:
    """Exit with formatted error message.

    Provides consistent error output across all CLI commands,
    supporting both JSON and human-readable formats.

    Args:
        message: Error message to display.
        code: Exit code to use (ExitCode enum or int).
        json_output: Whether to format output as JSON.

    Note:
        This function never returns; it always calls sys.exit().
    """
    # Import here to avoid circular imports at module load
    from .exit_codes import ExitCode

    # Get the code name for JSON output
    if isinstance(code, ExitCode):
        code_name = code.name
        exit_value = int(code)
    else:
        code_name = "UNKNOWN_ERROR"
        exit_value = code

    if json_output:
        click.echo(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": code_name,
                        "message": message,
                    },
                }
            ),
            err=True,
        )
    else:
        click.echo(f"Error: {message}", err=True)

    sys.exit(exit_value)


def success_output(
    result: CLIResult,
    json_output: bool = False,
) -> None:
    """Output successful result in appropriate format.

    Args:
        result: The CLIResult to output.
        json_output: Whether to format output as JSON.
    """
    if json_output:
        click.echo(result.to_json())
    else:
        click.echo(result.message)


def warning_output(
    message: str,
    json_output: bool = False,
) -> None:
    """Output a warning message.

    Args:
        message: Warning message to display.
        json_output: Whether to suppress output (warnings typically not in JSON).
    """
    if not json_output:
        click.echo(f"Warning: {message}", err=True)
