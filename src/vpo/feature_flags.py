"""Feature flags for gradual rollout of new behavior.

Feature flags are controlled via environment variables of the form
VPO_FEATURE_{FLAG_NAME}. Setting the variable to "1" enables the flag.

This module provides a simple, zero-dependency feature flag system
suitable for toggling experimental features or gradual rollouts.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Registry of known flags (for documentation and log_enabled_flags).
# Add new flags here as they are introduced.
_KNOWN_FLAGS: dict[str, str] = {}


def is_enabled(flag: str) -> bool:
    """Check whether a feature flag is enabled.

    A flag is enabled when the environment variable VPO_FEATURE_{FLAG}
    is set to "1". All other values (including unset) are treated as
    disabled.

    Args:
        flag: Flag name (e.g., "PARALLEL_SCAN"). Case-insensitive.

    Returns:
        True if the flag is enabled.
    """
    var = f"VPO_FEATURE_{flag.upper()}"
    return os.environ.get(var) == "1"


def log_enabled_flags() -> None:
    """Log all currently enabled feature flags at INFO level.

    Useful at startup to make active flags visible in logs.
    If no known flags are enabled, logs nothing.
    """
    enabled = [name for name in sorted(_KNOWN_FLAGS) if is_enabled(name)]
    if enabled:
        logger.info("Enabled feature flags: %s", ", ".join(enabled))
