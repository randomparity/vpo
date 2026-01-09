"""Subprocess utilities for external tool invocation.

This module provides a standard subprocess wrapper used across the codebase
for consistent timeout handling, encoding, and error handling when invoking
external tools like ffmpeg, ffprobe, mkvpropedit, etc.
"""

from __future__ import annotations

import logging
import subprocess  # nosec B404 - subprocess is required for FFmpeg invocation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_command(
    args: list[str | Path],
    timeout: int = 120,
    capture_output: bool = True,
    text: bool = True,
    errors: str = "replace",
    **kwargs: Any,
) -> tuple[str, str, int]:
    """Run external command with standard error handling.

    This function wraps subprocess.run with VPO's standard patterns:
    - Explicit UTF-8 encoding with error replacement
    - Configurable timeout (default 2 minutes)
    - Consistent return format

    Args:
        args: Command and arguments. Path objects are converted to strings.
        timeout: Timeout in seconds (default 120).
        capture_output: Capture stdout/stderr (default True).
        text: Return text instead of bytes (default True).
        errors: Error handling mode for text decoding (default "replace").
        **kwargs: Additional subprocess.run arguments.

    Returns:
        Tuple of (stdout, stderr, returncode).

    Raises:
        subprocess.TimeoutExpired: If command times out. Note: subprocess.run()
            automatically kills the child process before raising this exception
            (Python 3.7+ behavior), so no zombie processes are left behind.

    Example:
        >>> stdout, stderr, rc = run_command(["ffprobe", "-version"])
        >>> if rc == 0:
        ...     print(f"FFprobe version: {stdout}")
    """
    str_args = [str(arg) for arg in args]

    try:
        result = subprocess.run(  # nosec B603 - caller validates args
            str_args,
            capture_output=capture_output,
            text=text,
            errors=errors,
            timeout=timeout,
            **kwargs,
        )
        return result.stdout or "", result.stderr or "", result.returncode
    except subprocess.TimeoutExpired:
        logger.warning(
            "Command timed out after %ds: %s",
            timeout,
            " ".join(str_args[:3]) + ("..." if len(str_args) > 3 else ""),
        )
        raise
