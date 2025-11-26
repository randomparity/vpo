"""Channel downmix filter generation for audio synthesis.

This module provides FFmpeg filter expressions for downmixing audio
from higher channel counts to lower ones. All filters preserve LFE
content appropriately mixed into the output channels.

Key functions:
    get_downmix_filter: Generate FFmpeg filter for channel conversion
    normalize_channel_layout: Standardize channel layout strings
    get_channel_count: Extract channel count from layout string
"""

import logging
import re

logger = logging.getLogger(__name__)


# Standard channel layout normalization
# Maps various FFmpeg channel layout strings to canonical forms
LAYOUT_NORMALIZATION: dict[str, str] = {
    # Stereo variants
    "stereo": "stereo",
    "2.0": "stereo",
    "2": "stereo",
    # 5.1 variants
    "5.1": "5.1",
    "5.1(side)": "5.1",
    "5.1(back)": "5.1",
    "5point1": "5.1",
    "6": "5.1",
    # 7.1 variants
    "7.1": "7.1",
    "7.1(wide)": "7.1",
    "7.1(side)": "7.1",
    "7point1": "7.1",
    "8": "7.1",
    # Mono
    "mono": "mono",
    "1.0": "mono",
    "1": "mono",
}


def normalize_channel_layout(layout: str | None) -> str | None:
    """Normalize a channel layout string to a canonical form.

    Args:
        layout: FFmpeg channel layout string (e.g., '5.1(side)', 'stereo').

    Returns:
        Normalized layout string or None if unknown.
    """
    if layout is None:
        return None

    layout_lower = layout.lower().strip()
    return LAYOUT_NORMALIZATION.get(layout_lower, layout_lower)


def get_channel_count(layout: str | None, channels: int | None = None) -> int | None:
    """Get channel count from layout string or explicit count.

    Args:
        layout: FFmpeg channel layout string.
        channels: Explicit channel count (used if layout is ambiguous).

    Returns:
        Number of audio channels, or None if unknown.
    """
    # Use explicit channel count if provided
    if channels is not None:
        return channels

    if layout is None:
        return None

    normalized = normalize_channel_layout(layout)

    # Map normalized layouts to channel counts
    counts = {
        "mono": 1,
        "stereo": 2,
        "5.1": 6,
        "7.1": 8,
    }

    if normalized in counts:
        return counts[normalized]

    # Try to parse numeric layout
    if normalized and normalized.isdigit():
        return int(normalized)

    # Extract from patterns like "5.1(side)" or "7point1"
    match = re.match(r"(\d+)\.(\d+)", normalized or "")
    if match:
        main, lfe = int(match.group(1)), int(match.group(2))
        return main + lfe

    return None


def get_downmix_filter(
    source_channels: int,
    target_channels: int,
    source_layout: str | None = None,
) -> str | None:
    """Generate FFmpeg pan filter for downmixing channels.

    Generates filters that preserve LFE content appropriately mixed
    into the output channels rather than discarding it.

    Args:
        source_channels: Number of source audio channels.
        target_channels: Number of target audio channels.
        source_layout: Source channel layout (for 7.1 variants).

    Returns:
        FFmpeg filter expression, or None if no filter needed
        (same channel count).

    Raises:
        ValueError: If attempting to upmix (target > source).
    """
    if target_channels > source_channels:
        raise ValueError(
            f"Cannot upmix from {source_channels} to {target_channels} channels. "
            "Synthesis only supports downmixing."
        )

    if target_channels == source_channels:
        return None  # No filter needed

    # Determine the filter based on source and target
    filter_key = (source_channels, target_channels)
    filter_map = _get_filter_map()

    if filter_key in filter_map:
        return filter_map[filter_key]

    # Handle edge cases with more generic filter
    logger.warning(
        "No predefined downmix filter for %d→%d channels, using basic",
        source_channels,
        target_channels,
    )
    return f"pan={target_channels}c"


def _get_filter_map() -> dict[tuple[int, int], str]:
    """Get the filter mapping for standard downmix conversions.

    Returns:
        Dict mapping (source_channels, target_channels) to filter expression.
    """
    return {
        # 7.1 (8ch) → 5.1 (6ch)
        # Mix rear surrounds into side/back channels
        (8, 6): (
            "pan=5.1|"
            "FL=FL|"
            "FR=FR|"
            "FC=FC|"
            "LFE=LFE|"
            "BL=0.707*BL+0.707*SL|"
            "BR=0.707*BR+0.707*SR"
        ),
        # 7.1 (8ch) → Stereo (2ch)
        # Full downmix with LFE
        (8, 2): (
            "pan=stereo|"
            "FL=FL+0.707*FC+0.5*SL+0.5*BL+0.5*LFE|"
            "FR=FR+0.707*FC+0.5*SR+0.5*BR+0.5*LFE"
        ),
        # 7.1 (8ch) → Mono (1ch)
        (8, 1): (
            "pan=mono|"
            "c0=0.25*FL+0.25*FR+0.353*FC+0.125*SL+0.125*SR+"
            "0.125*BL+0.125*BR+0.25*LFE"
        ),
        # 5.1 (6ch) → Stereo (2ch)
        # Standard downmix with LFE preservation
        (6, 2): (
            "pan=stereo|FL=FL+0.707*FC+0.707*BL+0.5*LFE|FR=FR+0.707*FC+0.707*BR+0.5*LFE"
        ),
        # 5.1 (6ch) → Mono (1ch)
        (6, 1): ("pan=mono|c0=0.333*FL+0.333*FR+0.471*FC+0.236*BL+0.236*BR+0.333*LFE"),
        # Stereo (2ch) → Mono (1ch)
        (2, 1): "pan=mono|c0=0.5*FL+0.5*FR",
    }


def validate_downmix(source_channels: int, target_channels: int) -> tuple[bool, str]:
    """Validate that a downmix operation is possible.

    Args:
        source_channels: Number of source channels.
        target_channels: Number of target channels.

    Returns:
        Tuple of (is_valid, message) where message explains any issue.
    """
    if target_channels > source_channels:
        return (
            False,
            f"Cannot upmix from {source_channels} to {target_channels} channels",
        )

    if target_channels < 1:
        return (False, "Target must have at least 1 channel")

    if source_channels > 8:
        return (False, f"Source has too many channels: {source_channels}")

    return (True, "")


def get_output_layout(channels: int) -> str:
    """Get the FFmpeg channel layout string for an output channel count.

    Args:
        channels: Number of output channels.

    Returns:
        FFmpeg channel layout string.
    """
    layouts = {
        1: "mono",
        2: "stereo",
        6: "5.1",
        8: "7.1",
    }
    return layouts.get(channels, f"{channels}c")
