"""Core utilities package.

This package contains pure utility functions with no external dependencies.
These utilities are used across the codebase for common operations like
datetime parsing, formatting, and validation.
"""

from vpo.core.datetime_utils import (
    calculate_duration_seconds,
    mtime_to_utc_iso,
    parse_iso_timestamp,
)
from vpo.core.formatting import (
    format_audio_languages,
    format_file_size,
    get_resolution_label,
)
from vpo.core.validation import is_valid_uuid

__all__ = [
    # datetime_utils
    "parse_iso_timestamp",
    "calculate_duration_seconds",
    "mtime_to_utc_iso",
    # formatting
    "format_file_size",
    "get_resolution_label",
    "format_audio_languages",
    # validation
    "is_valid_uuid",
]
