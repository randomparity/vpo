"""Unified CLI output formatting for JSON and human-readable output.

This module provides consistent error handling and output formatting
across all CLI commands, replacing scattered per-module implementations.
"""

from __future__ import annotations

import functools
import json
import sys
from typing import TYPE_CHECKING, NoReturn

import click

if TYPE_CHECKING:
    from .exit_codes import ExitCode


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


def format_option(func):
    """Unified --format/-f option with hidden --json backward compat.

    Replaces per-command ``--json`` flags with a single ``--format``
    option that accepts ``text`` or ``json``.  The old ``--json`` flag
    is kept as a hidden alias for backward compatibility.

    The decorated function receives ``output_format: str`` (either
    ``"text"`` or ``"json"``).
    """

    @click.option(
        "--format",
        "output_format",
        type=click.Choice(["text", "json"]),
        default="text",
        help="Output format.",
    )
    @click.option("--json", "json_compat", is_flag=True, hidden=True)
    @functools.wraps(func)
    def wrapper(*args, output_format, json_compat, **kwargs):
        if json_compat:
            output_format = "json"
        return func(*args, output_format=output_format, **kwargs)

    return wrapper
