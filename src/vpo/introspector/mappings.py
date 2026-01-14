"""Pure mapping functions for ffprobe to VPO type conversions.

These functions have no side effects and no external dependencies,
making them trivially testable.
"""

# Track type mapping from ffprobe codec_type to VPO track type
FFPROBE_TO_VPO_TRACK_TYPE: dict[str, str] = {
    "video": "video",
    "audio": "audio",
    "subtitle": "subtitle",
    "attachment": "attachment",
}


def map_track_type(codec_type: str) -> str:
    """Map ffprobe codec_type to VPO track type.

    Args:
        codec_type: The codec_type from ffprobe.

    Returns:
        VPO track type string ("video", "audio", "subtitle", "attachment", "other").
    """
    return FFPROBE_TO_VPO_TRACK_TYPE.get(codec_type, "other")


# Channel layout mapping from count to human-readable label
CHANNEL_LAYOUT_NAMES: dict[int, str] = {
    1: "mono",
    2: "stereo",
    4: "quad",
    5: "5.0",
    6: "5.1",
    8: "7.1",
}


def map_channel_layout(channels: int) -> str:
    """Map channel count to human-readable label.

    Args:
        channels: Number of audio channels.

    Returns:
        Human-readable channel layout string.
    """
    return CHANNEL_LAYOUT_NAMES.get(channels, f"{channels}ch")
