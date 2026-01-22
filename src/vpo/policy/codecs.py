"""Unified codec matching and alias resolution.

This module provides backward-compatible exports for codec handling.
All functionality has been centralized in vpo.core.codecs.

For new code, prefer importing directly from vpo.core.codecs.
"""

# Re-export everything from core.codecs for backward compatibility
from vpo.core.codecs import (
    AUDIO_CODEC_ALIASES as _AUDIO_CODEC_ALIASES,
)
from vpo.core.codecs import (
    VIDEO_CODEC_ALIASES as _VIDEO_CODEC_ALIASES,
)
from vpo.core.codecs import (
    audio_codec_matches,
    audio_codec_matches_any,
    video_codec_matches,
    video_codec_matches_any,
)
from vpo.core.codecs import (
    normalize_codec as normalize_audio_codec,
)
from vpo.core.codecs import (
    normalize_codec as normalize_video_codec,
)

# Convert frozensets back to tuples for backward compatibility
# (existing code may rely on tuple behavior)
VIDEO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    k: tuple(v) for k, v in _VIDEO_CODEC_ALIASES.items()
}

AUDIO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    k: tuple(v) for k, v in _AUDIO_CODEC_ALIASES.items()
}

__all__ = [
    "VIDEO_CODEC_ALIASES",
    "AUDIO_CODEC_ALIASES",
    "normalize_video_codec",
    "normalize_audio_codec",
    "video_codec_matches",
    "video_codec_matches_any",
    "audio_codec_matches",
    "audio_codec_matches_any",
]
