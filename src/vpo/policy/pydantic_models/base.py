"""Base components for policy Pydantic models.

This module contains:
- PolicyValidationError exception
- Reserved names and pattern constants
- Shared validator helpers
"""

import re


class PolicyValidationError(Exception):
    """Error during policy validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)


# Reserved phase names that cannot be used as user-defined phase names
RESERVED_PHASE_NAMES = frozenset({"config", "schema_version", "phases"})

# Phase name validation pattern: starts with letter, alphanumeric + hyphen + underscore
PHASE_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$"

# Valid audio codecs for synthesis
VALID_SYNTHESIS_CODECS = frozenset({"eac3", "aac", "ac3", "opus", "flac"})

# Valid channel configurations
VALID_CHANNEL_CONFIGS = frozenset({"mono", "stereo", "5.1", "7.1"})


def _validate_language_codes(languages: list[str], field_name: str) -> list[str]:
    """Validate a list of language codes."""
    pattern = re.compile(r"^[a-z]{2,3}$")
    for idx, lang in enumerate(languages):
        if not pattern.match(lang):
            raise ValueError(
                f"Invalid language code '{lang}' at {field_name}[{idx}]. "
                "Use ISO 639-2 codes (e.g., 'eng', 'jpn')."
            )
    return languages
