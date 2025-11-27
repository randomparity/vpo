"""Environment variable reader with dependency injection support.

This module provides the EnvReader class for reading and parsing environment
variables with type conversion and validation. It supports dependency injection
for testing by accepting an optional env mapping.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)


class EnvReader:
    """Environment variable reader with type conversion and validation.

    Provides methods to read environment variables with automatic type
    conversion (str, int, float, bool, Path) and sensible defaults.

    Supports dependency injection by accepting an optional env mapping,
    making it easy to test code that depends on environment variables
    without modifying os.environ.

    Example:
        # Production usage (reads from os.environ)
        reader = EnvReader()
        port = reader.get_int("VPO_SERVER_PORT", 8321)

        # Testing usage (inject custom env)
        test_env = {"VPO_SERVER_PORT": "9000"}
        reader = EnvReader(env=test_env)
        port = reader.get_int("VPO_SERVER_PORT", 8321)  # Returns 9000
    """

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        """Initialize the environment reader.

        Args:
            env: Optional mapping to use instead of os.environ.
                 If None, reads from os.environ. Useful for testing.
        """
        self._env: Mapping[str, str] = env if env is not None else os.environ

    def get_str(self, var: str, default: str | None = None) -> str | None:
        """Get a string from environment variable.

        Args:
            var: Environment variable name.
            default: Default value if not set. Defaults to None.

        Returns:
            The environment variable value, or default if not set.
        """
        value = self._env.get(var)
        if value is None:
            return default
        return value

    def get_int(self, var: str, default: int | None = None) -> int | None:
        """Get an integer from environment variable.

        Args:
            var: Environment variable name.
            default: Default value if not set or invalid.

        Returns:
            Parsed integer value, or default if not set or invalid.
            Logs a warning if the value is set but cannot be parsed.
        """
        value = self._env.get(var)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning("Invalid integer value for %s: %s", var, value)
            return default

    def get_float(self, var: str, default: float | None = None) -> float | None:
        """Get a float from environment variable.

        Args:
            var: Environment variable name.
            default: Default value if not set or invalid.

        Returns:
            Parsed float value, or default if not set or invalid.
            Logs a warning if the value is set but cannot be parsed.
        """
        value = self._env.get(var)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning("Invalid float value for %s: %s", var, value)
            return default

    def get_bool(self, var: str, default: bool | None = None) -> bool | None:
        """Get a boolean from environment variable.

        Recognizes the following true values (case-insensitive):
        - "true", "1", "yes", "on"

        All other non-empty values are treated as false.

        Args:
            var: Environment variable name.
            default: Default value if not set.

        Returns:
            Boolean value, or default if not set.
        """
        value = self._env.get(var)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    def get_path(
        self, var: str, must_exist: bool = True, default: Path | None = None
    ) -> Path | None:
        """Get a path from environment variable.

        Args:
            var: Environment variable name.
            must_exist: If True, validate that the path exists and log a
                       warning if it doesn't. Defaults to True.
            default: Default value if not set or path doesn't exist.

        Returns:
            Path object, or default if not set (or if must_exist=True
            and path doesn't exist).
        """
        value = self._env.get(var)
        if value is None:
            return default

        path = Path(value).expanduser()
        if must_exist and not path.exists():
            logger.warning(
                "Environment variable %s points to non-existent path: %s",
                var,
                value,
            )
            return default
        return path

    def get_path_list(
        self, var: str, separator: str = ":", default: list[Path] | None = None
    ) -> list[Path]:
        """Get a list of paths from environment variable.

        Parses a separator-delimited string into a list of Path objects.
        Each path is expanded (tilde expansion).

        Args:
            var: Environment variable name.
            separator: Delimiter between paths. Defaults to ":".
            default: Default value if not set. Defaults to empty list.

        Returns:
            List of Path objects. Empty paths are filtered out.
        """
        value = self._env.get(var)
        if value is None:
            return default if default is not None else []

        paths: list[Path] = []
        for part in value.split(separator):
            part = part.strip()
            if part:
                paths.append(Path(part).expanduser())
        return paths
