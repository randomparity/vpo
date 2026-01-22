"""Centralized codec registry and utilities.

This module provides the single source of truth for codec knowledge throughout
VPO, including:
- Codec alias groups for matching/normalization
- Container compatibility matrices
- Transcode defaults
- Validation sets

All other modules should import codec constants and functions from here or
from vpo.policy.codecs (which re-exports from here for backward compatibility).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass

# =============================================================================
# Codec Alias Groups
# =============================================================================
# These define groups of equivalent codec identifiers that should be treated
# as matching in policy evaluation.

VIDEO_CODEC_ALIASES: dict[str, frozenset[str]] = {
    "hevc": frozenset({"hevc", "h265", "h.265", "x265", "hvc1", "hev1"}),
    "h265": frozenset({"hevc", "h265", "h.265", "x265", "hvc1", "hev1"}),
    "h264": frozenset({"h264", "h.264", "avc", "avc1", "x264"}),
    "avc": frozenset({"h264", "h.264", "avc", "avc1", "x264"}),
    "vp9": frozenset({"vp9", "vp09"}),
    "av1": frozenset({"av1", "av01", "libaom-av1"}),
    "mpeg4": frozenset({"mpeg4", "mp4v"}),
}

AUDIO_CODEC_ALIASES: dict[str, frozenset[str]] = {
    "truehd": frozenset({"truehd", "dolby truehd", "mlp"}),
    "dts-hd": frozenset({"dts-hd ma", "dts-hd", "dtshd", "dts_hd", "dts-hd.ma"}),
    "dts": frozenset({"dts", "dca"}),
    "flac": frozenset({"flac"}),
    "pcm": frozenset({"pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm"}),
    "aac": frozenset({"aac", "aac_latm", "mp4a"}),
    "ac3": frozenset({"ac3", "ac-3", "a52"}),
    "eac3": frozenset({"eac3", "e-ac-3", "ec3"}),
    "opus": frozenset({"opus"}),
    "mp3": frozenset({"mp3", "mp3float"}),
    "vorbis": frozenset({"vorbis"}),
    "alac": frozenset({"alac"}),
}

SUBTITLE_CODEC_ALIASES: dict[str, frozenset[str]] = {
    "subrip": frozenset({"subrip", "srt"}),
    "ass": frozenset({"ass", "ssa"}),
    "pgs": frozenset({"hdmv_pgs_subtitle", "pgssub", "pgs"}),
    "dvdsub": frozenset({"dvd_subtitle", "dvdsub", "vobsub"}),
    "mov_text": frozenset({"mov_text", "tx3g"}),
    "webvtt": frozenset({"webvtt"}),
}


# =============================================================================
# Container Compatibility Matrices
# =============================================================================
# These define which codecs are compatible with which containers.

MP4_COMPATIBLE_VIDEO_CODECS: frozenset[str] = frozenset(
    {
        "h264",
        "avc",
        "avc1",
        "hevc",
        "h265",
        "hvc1",
        "hev1",
        "av1",
        "av01",
        "mpeg4",
        "mp4v",
        "vp9",
    }
)

MP4_COMPATIBLE_AUDIO_CODECS: frozenset[str] = frozenset(
    {
        "aac",
        "mp4a",
        "ac3",
        "eac3",
        "mp3",
        "mp3float",
        "flac",
        "opus",
        "alac",
    }
)

MP4_COMPATIBLE_SUBTITLE_CODECS: frozenset[str] = frozenset(
    {
        "mov_text",
        "tx3g",
        "webvtt",
    }
)

# Text-based subtitle codecs that can be converted to mov_text for MP4
# Note: webvtt is already MP4-compatible, so it's not in this set
MP4_CONVERTIBLE_SUBTITLE_CODECS: frozenset[str] = frozenset(
    {"subrip", "srt", "ass", "ssa"}
)

# Bitmap subtitle codecs that cannot be converted (would require OCR)
BITMAP_SUBTITLE_CODECS: frozenset[str] = frozenset(
    {"hdmv_pgs_subtitle", "dvd_subtitle", "dvdsub", "pgssub", "pgs", "vobsub"}
)

# All MP4-incompatible codecs (for validation/documentation purposes)
MP4_INCOMPATIBLE_CODECS: frozenset[str] = frozenset(
    {
        # Lossless audio codecs
        "truehd",
        "dts-hd ma",
        "dts-hd.ma",
        "dtshd",
        "mlp",
        # Subtitle formats not supported in MP4
        "hdmv_pgs_subtitle",
        "pgssub",
        "pgs",
        "dvd_subtitle",
        "dvdsub",
        "vobsub",
        # Advanced subtitle formats (need conversion)
        "ass",
        "ssa",
        "subrip",  # SRT needs conversion to mov_text
        # Attachment types (not supported in MP4)
        "ttf",
        "otf",
        "application/x-truetype-font",
    }
)


# =============================================================================
# Transcode Defaults
# =============================================================================


@dataclass(frozen=True)
class TranscodeTarget:
    """Target codec configuration for transcoding."""

    codec: str
    bitrate: str | None = None


# Default transcoding targets for incompatible audio codecs when converting to MP4
MP4_AUDIO_TRANSCODE_DEFAULTS: dict[str, TranscodeTarget] = {
    "truehd": TranscodeTarget(codec="aac", bitrate="256k"),
    "dts": TranscodeTarget(codec="aac", bitrate="256k"),
    "dts-hd ma": TranscodeTarget(codec="aac", bitrate="320k"),
    "dts-hd": TranscodeTarget(codec="aac", bitrate="320k"),
    "vorbis": TranscodeTarget(codec="aac", bitrate="192k"),
    "pcm_s16le": TranscodeTarget(codec="aac", bitrate="192k"),
    "pcm_s24le": TranscodeTarget(codec="aac", bitrate="192k"),
    "pcm_s32le": TranscodeTarget(codec="aac", bitrate="192k"),
}

# Default target for unknown incompatible audio codecs
DEFAULT_AUDIO_TRANSCODE_TARGET = TranscodeTarget(codec="aac", bitrate="192k")


# =============================================================================
# Validation Sets
# =============================================================================
# Valid codec sets for policy validation (what can be specified in policies).

VALID_TRANSCODE_VIDEO_CODECS: frozenset[str] = frozenset({"h264", "hevc", "vp9", "av1"})

VALID_TRANSCODE_AUDIO_CODECS: frozenset[str] = frozenset(
    {
        "aac",
        "ac3",
        "eac3",
        "flac",
        "opus",
        "mp3",
        "truehd",
        "dts",
        "pcm_s16le",
        "pcm_s24le",
    }
)


# =============================================================================
# Normalization Functions
# =============================================================================


def normalize_codec(codec: str | None) -> str:
    """Normalize a codec name for comparison.

    Args:
        codec: Codec name from ffprobe or policy.

    Returns:
        Normalized lowercase codec name.
    """
    if codec is None:
        return ""
    normalized = codec.casefold().strip()

    # Handle DTS variants
    if "dts-hd" in normalized or "dtshd" in normalized:
        return "dts-hd"
    if "truehd" in normalized:
        return "truehd"

    return normalized


def get_canonical_codec(codec: str, track_type: str) -> str:
    """Get the canonical name for a codec.

    Args:
        codec: Codec name to canonicalize.
        track_type: One of 'video', 'audio', 'subtitle'.

    Returns:
        Canonical codec name (the alias group key), or original if not found.
    """
    normalized = normalize_codec(codec)
    if not normalized:
        return normalized

    aliases: dict[str, frozenset[str]]
    if track_type == "video":
        aliases = VIDEO_CODEC_ALIASES
    elif track_type == "audio":
        aliases = AUDIO_CODEC_ALIASES
    elif track_type == "subtitle":
        aliases = SUBTITLE_CODEC_ALIASES
    else:
        return normalized

    # Find which alias group this codec belongs to
    for canonical, variants in aliases.items():
        if normalized in variants or normalized == canonical:
            return canonical

    return normalized


# =============================================================================
# Matching Functions
# =============================================================================


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

    current_lower = current_codec.casefold()
    target_lower = target.casefold()

    # Direct match
    if current_lower == target_lower:
        return True

    # Check target aliases
    target_aliases = VIDEO_CODEC_ALIASES.get(target_lower, frozenset())
    if current_lower in target_aliases:
        return True

    # Check if current codec has aliases that match target
    current_aliases = VIDEO_CODEC_ALIASES.get(current_lower, frozenset())
    if target_lower in current_aliases:
        return True

    return False


def video_codec_matches_any(
    current_codec: str | None, codec_patterns: tuple[str, ...] | list[str] | None
) -> bool:
    """Check if current video codec matches any pattern.

    Args:
        current_codec: Current video codec (from ffprobe).
        codec_patterns: Patterns to match against.

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

    normalized_codec = normalize_codec(codec)
    normalized_pattern = pattern.casefold().strip()

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
    codec: str | None, patterns: tuple[str, ...] | list[str] | None
) -> bool:
    """Check if an audio codec matches any pattern in a list.

    Args:
        codec: Codec name to check (from ffprobe).
        patterns: Patterns to match against.

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


def codec_matches(codec: str | None, target: str, track_type: str) -> bool:
    """Generic codec matching for any track type.

    Args:
        codec: Codec name to check.
        target: Target codec/pattern to match.
        track_type: One of 'video', 'audio', 'subtitle'.

    Returns:
        True if codec matches target.
    """
    if track_type == "video":
        return video_codec_matches(codec, target)
    elif track_type == "audio":
        return audio_codec_matches(codec, target)
    elif track_type == "subtitle":
        # Subtitle matching uses similar logic to audio
        if codec is None:
            return False
        normalized = normalize_codec(codec)
        target_lower = target.casefold().strip()

        if normalized == target_lower:
            return True

        # Check subtitle aliases
        target_aliases = SUBTITLE_CODEC_ALIASES.get(target_lower, frozenset())
        if normalized in target_aliases:
            return True

        current_aliases = SUBTITLE_CODEC_ALIASES.get(normalized, frozenset())
        if target_lower in current_aliases:
            return True

        return False

    return False


# =============================================================================
# Container Compatibility Functions
# =============================================================================


def is_codec_mp4_compatible(codec: str, track_type: str) -> bool:
    """Check if a codec is compatible with MP4 container.

    Args:
        codec: Codec name (e.g., 'hevc', 'truehd').
        track_type: Track type ('video', 'audio', 'subtitle').

    Returns:
        True if codec is compatible with MP4.
    """
    normalized = codec.casefold().strip()

    if track_type == "video":
        return normalized in MP4_COMPATIBLE_VIDEO_CODECS
    elif track_type == "audio":
        return normalized in MP4_COMPATIBLE_AUDIO_CODECS
    elif track_type == "subtitle":
        return normalized in MP4_COMPATIBLE_SUBTITLE_CODECS

    # Unknown track types (data, attachment) - not compatible
    return False


def is_codec_compatible(codec: str, container: str, track_type: str) -> bool:
    """Check if a codec is compatible with a container.

    Args:
        codec: Codec name.
        container: Target container format ('mp4', 'mkv', etc.).
        track_type: Track type ('video', 'audio', 'subtitle').

    Returns:
        True if codec is compatible with container.
    """
    container_lower = container.casefold().strip()

    if container_lower == "mp4":
        return is_codec_mp4_compatible(codec, track_type)
    elif container_lower == "mkv":
        # MKV accepts all codecs
        return True

    # Unknown container - assume compatible
    return True


def get_transcode_default(codec: str, container: str) -> TranscodeTarget | None:
    """Get the default transcode target for an incompatible audio codec.

    This function only provides defaults for audio codecs. Video codecs
    require explicit transcode configuration via the transcode phase.

    Args:
        codec: Source audio codec name.
        container: Target container format.

    Returns:
        TranscodeTarget with default settings, or None if no default available.
    """
    if container.casefold() != "mp4":
        return None

    normalized = normalize_codec(codec)

    # Check exact match first (only applies to audio codecs)
    if normalized in MP4_AUDIO_TRANSCODE_DEFAULTS:
        return MP4_AUDIO_TRANSCODE_DEFAULTS[normalized]

    # Only provide a fallback for audio codecs that are known to be incompatible.
    # We can't determine track type from codec name alone, so we check if the
    # codec is in the known audio incompatible set.
    # Video codecs should return None - they require explicit transcode config.
    audio_incompatible = {
        "truehd",
        "dts-hd",
        "dts-hd ma",
        "dts",
        "dca",
        "vorbis",
        "pcm_s16le",
        "pcm_s24le",
        "pcm_s32le",
        "pcm_f32le",
        "pcm",
    }
    if normalized in audio_incompatible or any(
        normalized.startswith(prefix) for prefix in ("pcm_", "dts")
    ):
        return DEFAULT_AUDIO_TRANSCODE_TARGET

    return None


# =============================================================================
# Subtitle Classification Functions
# =============================================================================


def is_text_subtitle(codec: str) -> bool:
    """Check if a subtitle codec is text-based (can be converted to mov_text).

    Args:
        codec: Subtitle codec name.

    Returns:
        True if the codec is a text-based subtitle format.
    """
    normalized = normalize_codec(codec)
    return normalized in MP4_CONVERTIBLE_SUBTITLE_CODECS


def is_bitmap_subtitle(codec: str) -> bool:
    """Check if a subtitle codec is bitmap-based (cannot be converted).

    Args:
        codec: Subtitle codec name.

    Returns:
        True if the codec is a bitmap-based subtitle format.
    """
    normalized = normalize_codec(codec)
    return normalized in BITMAP_SUBTITLE_CODECS
