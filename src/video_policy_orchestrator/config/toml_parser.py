"""TOML parsing with explicit fallback handling.

This module provides TOML parsing functionality with a documented fallback
parser for environments where tomllib (Python 3.11+) or tomli are unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BasicTomlParser:
    """Limited TOML parser for basic key=value configs.

    This is a fallback parser used when tomllib (Python 3.11+) and tomli
    are both unavailable. It handles only a subset of TOML syntax.

    Supported features:
    - [section] headers
    - [section.subsection] nested headers
    - key = "value" pairs (strings with quotes)
    - key = 'value' pairs (strings with single quotes)
    - key = value pairs (unquoted strings)
    - key = true/false (booleans)
    - key = 123 (integers)
    - Comments starting with #

    Limitations (NOT supported):
    - Arrays: [1, 2, 3]
    - Inline tables: {key = "value"}
    - Multiline strings: '''...''' or \"\"\"...\"\"\"
    - Dates and times
    - Escape sequences in strings
    - Dotted keys: key.subkey = "value"

    Example:
        parser = BasicTomlParser()
        config = parser.parse('''
        [server]
        port = 8080
        host = "localhost"
        enabled = true
        ''')
        # Returns: {"server": {"port": 8080, "host": "localhost", "enabled": True}}
    """

    def parse(self, content: str) -> dict[str, Any]:
        """Parse TOML content into a dictionary.

        Args:
            content: TOML file content.

        Returns:
            Parsed dictionary. Nested sections become nested dicts.
        """
        result: dict[str, Any] = {}
        current_section: dict[str, Any] | None = None

        for line in content.split("\n"):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Section header: [section] or [section.subsection]
            if line.startswith("[") and line.endswith("]"):
                section_path = line[1:-1].strip()
                parts = section_path.split(".")

                # Navigate/create nested sections
                current = result
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current_section = current
                continue

            # Key = value
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Parse the value
                parsed_value = self._parse_value(value)

                target = current_section if current_section is not None else result
                target[key] = parsed_value

        return result

    def _parse_value(self, value: str) -> Any:
        """Parse a TOML value string into a Python object.

        Args:
            value: The value part of a key=value line.

        Returns:
            Parsed value (str, int, bool, or original string).
        """
        # Remove inline comments
        if " #" in value:
            value = value.split(" #", 1)[0].strip()

        # String with double quotes
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]

        # String with single quotes
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]

        # Boolean true
        if value.lower() == "true":
            return True

        # Boolean false
        if value.lower() == "false":
            return False

        # Integer (including negative)
        if value.lstrip("-").isdigit():
            return int(value)

        # Float (basic check)
        try:
            if "." in value:
                return float(value)
        except ValueError:
            pass

        # Unquoted string (return as-is)
        return value


def parse_toml(content: str) -> dict[str, Any]:
    """Parse TOML content using the best available parser.

    Tries parsers in this order:
    1. tomllib (Python 3.11+ standard library)
    2. tomli (third-party package)
    3. BasicTomlParser (limited fallback)

    Args:
        content: TOML file content as a string.

    Returns:
        Parsed dictionary.

    Note:
        When using the fallback parser, a warning is logged suggesting
        to install tomli for full TOML support.
    """
    # Try tomllib (Python 3.11+)
    try:
        import tomllib

        return tomllib.loads(content)
    except ImportError:
        pass

    # Try tomli (third-party)
    try:
        import tomli

        return tomli.loads(content)
    except ImportError:
        pass

    # Fall back to basic parser
    logger.debug(
        "Using basic TOML parser. For full TOML support, "
        "upgrade to Python 3.11+ or install tomli."
    )
    return BasicTomlParser().parse(content)


def load_toml_file(path: Path) -> dict[str, Any]:
    """Load and parse a TOML file.

    Args:
        path: Path to the TOML file.

    Returns:
        Parsed dictionary. Returns empty dict if file doesn't exist
        or cannot be parsed.
    """
    if not path.exists():
        logger.debug("TOML file not found: %s", path)
        return {}

    try:
        content = path.read_text()
        config = parse_toml(content)
        logger.debug("Loaded TOML config from %s", path)
        return config
    except Exception as e:
        logger.warning("Failed to load TOML file %s: %s", path, e)
        return {}
