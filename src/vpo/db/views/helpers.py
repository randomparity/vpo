"""Pagination helpers for view query functions."""

# Default page size for view queries when no limit is specified
DEFAULT_PAGE_SIZE = 50

# Maximum allowed page size to prevent memory exhaustion
MAX_PAGE_SIZE = 1000


def _clamp_limit(limit: int | None, max_limit: int = MAX_PAGE_SIZE) -> int:
    """Clamp limit to valid range [1, max_limit], defaulting to DEFAULT_PAGE_SIZE.

    Args:
        limit: Requested limit, or None for default.
        max_limit: Maximum allowed limit (default MAX_PAGE_SIZE).

    Returns:
        Clamped limit value.
    """
    if limit is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(max_limit, limit))
