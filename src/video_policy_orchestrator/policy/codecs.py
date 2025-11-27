"""Unified codec matching and alias resolution.

This module provides canonical codec handling for both video and audio codecs,
consolidating the previously duplicated logic from executor/transcode.py and
policy/transcode.py.
"""

import fnmatch

# Video codec aliases for matching (from executor/transcode.py)
VIDEO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    "hevc": ("hevc", "h265", "x265"),
    "h265": ("hevc", "h265", "x265"),
    "h264": ("h264", "avc", "x264"),
    "avc": ("h264", "avc", "x264"),
    "vp9": ("vp9", "vp09"),
    "av1": ("av1", "av01", "libaom-av1"),
}

# Audio codec aliases for matching (from policy/transcode.py)
AUDIO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    "truehd": ("truehd", "dolby truehd"),
    "dts-hd": ("dts-hd ma", "dts-hd", "dtshd", "dts_hd"),
    "dts": ("dts", "dca"),
    "flac": ("flac",),
    "pcm": ("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm"),
    "aac": ("aac", "aac_latm"),
    "ac3": ("ac3", "ac-3", "a52"),
    "eac3": ("eac3", "e-ac-3", "ec3"),
    "opus": ("opus",),
    "mp3": ("mp3", "mp3float"),
    "vorbis": ("vorbis",),
}


def normalize_video_codec(codec: str | None) -> str:
    """Normalize a video codec name for comparison.

    Args:
        codec: Codec name from ffprobe.

    Returns:
        Normalized lowercase codec name.
    """
    if codec is None:
        return ""
    return codec.lower().strip()


def normalize_audio_codec(codec: str | None) -> str:
    """Normalize an audio codec name for comparison.

    Handles special cases like DTS-HD variants and TrueHD.

    Args:
        codec: Codec name from ffprobe or policy.

    Returns:
        Normalized lowercase codec name.
    """
    if codec is None:
        return ""
    normalized = codec.lower().strip()

    # Handle dts variants
    if "dts-hd" in normalized or "dtshd" in normalized:
        # All DTS-HD variants normalize to "dts-hd"
        return "dts-hd"
    if "truehd" in normalized:
        return "truehd"
    return normalized


def video_codec_matches(current_codec: str | None, target: str) -> bool:
    """Check if current video codec matches target (case-insensitive, alias-aware).

    Args:
        current_codec: Current video codec from ffprobe.
        target: Target codec to match against.

    Returns:
        True if codec matches.
    """
    if current_codec is None:
        return False

    current_lower = current_codec.lower()
    target_lower = target.lower()

    # Direct match
    if current_lower == target_lower:
        return True

    # Check target aliases
    target_aliases = VIDEO_CODEC_ALIASES.get(target_lower, ())
    if current_lower in target_aliases:
        return True

    # Check if current codec has aliases that match target
    current_aliases = VIDEO_CODEC_ALIASES.get(current_lower, ())
    if target_lower in current_aliases:
        return True

    return False


def video_codec_matches_any(
    current_codec: str | None, codec_patterns: tuple[str, ...] | None
) -> bool:
    """Check if current video codec matches any pattern.

    Args:
        current_codec: Current video codec (from ffprobe).
        codec_patterns: Tuple of codec patterns to match.

    Returns:
        True if codec matches any pattern.
    """
    if codec_patterns is None:
        return True  # No patterns = always passes
    if current_codec is None:
        return False

    for pattern in codec_patterns:
        if video_codec_matches(current_codec, pattern):
            return True

    return False


def audio_codec_matches(codec: str | None, pattern: str) -> bool:
    """Check if an audio codec matches a pattern.

    The pattern can be:
    - An exact codec name (e.g., "truehd")
    - A wildcard pattern (e.g., "pcm_*")
    - An alias group name (e.g., "dts" matches all DTS variants)

    Args:
        codec: Codec name to check (from ffprobe).
        pattern: Pattern to match against.

    Returns:
        True if the codec matches the pattern.
    """
    if codec is None:
        return False

    normalized_codec = normalize_audio_codec(codec)
    normalized_pattern = pattern.lower().strip()

    # Direct match
    if normalized_codec == normalized_pattern:
        return True

    # Check aliases
    for alias_group, variants in AUDIO_CODEC_ALIASES.items():
        if normalized_pattern == alias_group:
            # Pattern is an alias group name, check if codec is in variants
            for variant in variants:
                if normalized_codec == variant or normalized_codec.startswith(variant):
                    return True
            # Also check if codec starts with the alias
            if normalized_codec.startswith(alias_group):
                return True

    # Wildcard match (e.g., "pcm_*")
    if "*" in normalized_pattern or "?" in normalized_pattern:
        if fnmatch.fnmatch(normalized_codec, normalized_pattern):
            return True

    # Check if normalized codec contains the pattern (fuzzy match)
    if normalized_pattern in normalized_codec:
        return True

    return False


def audio_codec_matches_any(
    codec: str | None, patterns: tuple[str, ...] | None
) -> bool:
    """Check if an audio codec matches any pattern in a list.

    Args:
        codec: Codec name to check (from ffprobe).
        patterns: Tuple of patterns to match against.

    Returns:
        True if the codec matches any pattern.
    """
    if patterns is None:
        return False
    if codec is None:
        return False

    for pattern in patterns:
        if audio_codec_matches(codec, pattern):
            return True
    return False
