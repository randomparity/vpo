"""Formatting utilities.

This module provides pure functions for formatting data for display.
These utilities are used across the codebase for consistent presentation.
"""


def get_resolution_label(width: int | None, height: int | None) -> str:
    """Map video dimensions to human-readable resolution label.

    Args:
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Resolution label (e.g., "1080p", "4K") or "\u2014" if unknown.
    """
    if width is None or height is None:
        return "\u2014"

    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    elif height > 0:
        return f"{height}p"
    else:
        return "\u2014"


def format_audio_languages(languages_csv: str | None) -> str:
    """Format comma-separated language codes for display.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more").
    """
    if not languages_csv:
        return "\u2014"

    languages = [lang.strip() for lang in languages_csv.split(",") if lang.strip()]

    if not languages:
        return "\u2014"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted string (e.g., "4.2 GB", "128 MB", "1.5 KB").
    """
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


def truncate_filename(filename: str, max_length: int = 40) -> str:
    """Truncate filename preserving start and extension.

    If truncation is needed, shows: beginning…extension
    Uses single ellipsis character (U+2026).

    Args:
        filename: The filename to truncate.
        max_length: Maximum length of the result (default 40).

    Returns:
        Truncated filename or original if short enough.

    Examples:
        >>> truncate_filename("some-very-long-movie-name.mkv", 25)
        'some-very-long-mov….mkv'
        >>> truncate_filename("short.mp4", 40)
        'short.mp4'
        >>> truncate_filename("no-extension", 10)
        'no-extens…'
    """
    if not filename or len(filename) <= max_length:
        return filename

    # Find extension (last dot)
    dot_index = filename.rfind(".")
    if dot_index > 0:
        extension = filename[dot_index:]  # includes the dot
        base = filename[:dot_index]
    else:
        extension = ""
        base = filename

    # Calculate space for base (1 char for ellipsis)
    available_for_base = max_length - len(extension) - 1

    # Edge case: extension too long, just truncate everything
    if available_for_base < 1:
        return filename[: max_length - 1] + "…"

    return base[:available_for_base] + "…" + extension
