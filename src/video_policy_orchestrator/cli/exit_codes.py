"""Centralized exit codes for all CLI commands.

This module provides a single source of truth for CLI exit codes,
replacing scattered per-module constants.

Exit code ranges:
    0: Success
    1-9: General errors
    10-19: Validation errors (policy, config, input)
    20-29: Target/file errors
    30-39: Tool/dependency errors
    40-49: Operation errors
    50-59: Analysis errors
    60-69: Warning states
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes for VPO CLI commands.

    Organized by category with reserved ranges for future expansion.
    """

    # Success (0)
    SUCCESS = 0

    # General errors (1-9)
    GENERAL_ERROR = 1
    INTERRUPTED = 2  # Ctrl+C / SIGINT (conventionally 130, but we use 2 for simplicity)

    # Validation errors (10-19)
    POLICY_VALIDATION_ERROR = 10
    CONFIG_ERROR = 11
    PROFILE_NOT_FOUND = 12

    # Target/file errors (20-29)
    TARGET_NOT_FOUND = 20
    FILE_NOT_IN_DATABASE = 21
    NO_TRACKS_FOUND = 22

    # Tool/dependency errors (30-39)
    TOOL_NOT_AVAILABLE = 30
    PLUGIN_UNAVAILABLE = 31
    FFPROBE_NOT_FOUND = 32

    # Operation errors (40-49)
    OPERATION_FAILED = 40
    FILE_LOCKED = 41
    DATABASE_ERROR = 42

    # Analysis errors (50-59)
    ANALYSIS_ERROR = 50
    PARSE_ERROR = 51

    # Warning states (60-69)
    WARNINGS = 60
    CRITICAL = 61


# Mapping tables for backwards compatibility with existing code
# These allow gradual migration while preserving existing contracts

# apply.py mappings (contracts/cli-apply.md)
APPLY_EXIT_CODES = {
    "EXIT_SUCCESS": ExitCode.SUCCESS,
    "EXIT_GENERAL_ERROR": ExitCode.GENERAL_ERROR,
    "EXIT_POLICY_VALIDATION_ERROR": ExitCode.POLICY_VALIDATION_ERROR,
    "EXIT_TARGET_NOT_FOUND": ExitCode.TARGET_NOT_FOUND,
    "EXIT_TOOL_NOT_AVAILABLE": ExitCode.TOOL_NOT_AVAILABLE,
    "EXIT_OPERATION_FAILED": ExitCode.OPERATION_FAILED,
}

# inspect.py mappings (contracts/cli-inspect.md)
INSPECT_EXIT_CODES = {
    "EXIT_SUCCESS": ExitCode.SUCCESS,
    "EXIT_FILE_NOT_FOUND": ExitCode.TARGET_NOT_FOUND,
    "EXIT_FFPROBE_NOT_INSTALLED": ExitCode.FFPROBE_NOT_FOUND,
    "EXIT_PARSE_ERROR": ExitCode.PARSE_ERROR,
    "EXIT_ANALYSIS_ERROR": ExitCode.ANALYSIS_ERROR,
}

# doctor.py mappings
DOCTOR_EXIT_CODES = {
    "EXIT_OK": ExitCode.SUCCESS,
    "EXIT_WARNINGS": ExitCode.WARNINGS,
    "EXIT_CRITICAL": ExitCode.CRITICAL,
}
