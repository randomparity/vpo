"""Data models for audio synthesis configuration and planning.

This module defines dataclasses and enums for:
- Synthesis track definitions from policy YAML
- Source track preferences and selection results
- Synthesis operations and plans
- Skip reasons for dry-run output
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TrackInfo
    from video_policy_orchestrator.policy.models import Condition


class AudioCodec(str, Enum):
    """Supported target audio codecs for synthesis.

    Each codec maps to a specific FFmpeg encoder. Some encoders
    may not be available depending on FFmpeg build options.
    """

    EAC3 = "eac3"  # Dolby Digital Plus
    AAC = "aac"  # Advanced Audio Coding
    AC3 = "ac3"  # Dolby Digital
    OPUS = "opus"  # Opus (modern, efficient)
    FLAC = "flac"  # Free Lossless Audio Codec


class ChannelConfig(str, Enum):
    """Preset channel configurations.

    Standard layouts for mono, stereo, and surround audio.
    """

    MONO = "mono"  # 1 channel
    STEREO = "stereo"  # 2 channels
    SURROUND_51 = "5.1"  # 6 channels
    SURROUND_71 = "7.1"  # 8 channels

    @property
    def channel_count(self) -> int:
        """Return the number of audio channels for this config."""
        return {
            ChannelConfig.MONO: 1,
            ChannelConfig.STEREO: 2,
            ChannelConfig.SURROUND_51: 6,
            ChannelConfig.SURROUND_71: 8,
        }[self]


class Position(str, Enum):
    """Track position specifiers for synthesized tracks.

    Determines where in the audio track order the new track is placed.
    """

    AFTER_SOURCE = "after_source"  # Immediately after source track
    END = "end"  # Append to end of audio tracks


class SkipReason(str, Enum):
    """Reasons why a synthesis operation was skipped.

    Used in dry-run output to explain why a track wasn't created.
    """

    CONDITION_NOT_MET = "condition_not_met"
    NO_SOURCE_AVAILABLE = "no_source_available"
    WOULD_UPMIX = "would_upmix"
    ENCODER_UNAVAILABLE = "encoder_unavailable"
    ALREADY_EXISTS = "already_exists"


class ChannelPreference(str, Enum):
    """Preferences for source track channel count selection."""

    MAX = "max"  # Prefer highest channel count
    MIN = "min"  # Prefer lowest channel count


@dataclass(frozen=True)
class PreferenceCriterion:
    """Single criterion for source track preference scoring.

    Each criterion adds points to tracks that match. Multiple criteria
    are evaluated in order and scores are accumulated.
    """

    language: str | tuple[str, ...] | None = None
    """Preferred language(s). Tracks matching get +100 points."""

    not_commentary: bool | None = None
    """If True, non-commentary tracks get +80 points."""

    channels: ChannelPreference | int | None = None
    """Channel preference. 'max' adds +10 per channel, 'min' penalizes."""

    codec: str | tuple[str, ...] | None = None
    """Preferred codec(s). Matching tracks get +20 points."""


@dataclass(frozen=True)
class SourcePreferences:
    """Ordered preferences for selecting the source track.

    Source selection evaluates each criterion and scores all audio tracks.
    The highest-scoring track is selected. If no tracks score above 0,
    the first audio track is used as fallback.
    """

    prefer: tuple[PreferenceCriterion, ...]
    """Ordered preference criteria for scoring tracks."""


@dataclass(frozen=True)
class SynthesisTrackDefinition:
    """Policy-defined specification for a track to be synthesized.

    Loaded from the audio_synthesis.tracks section of a policy YAML file.
    Each definition describes one audio track to potentially create.
    """

    name: str
    """Human-readable identifier for this synthesis definition."""

    codec: AudioCodec
    """Target codec for the synthesized track."""

    channels: ChannelConfig | int
    """Target channel configuration or count."""

    source: SourcePreferences
    """Preferences for selecting the source track."""

    bitrate: str | None = None
    """Target bitrate (e.g., '640k'). Uses codec default if None."""

    create_if: "Condition | None" = None
    """Condition that must be true for synthesis to occur."""

    title: str | Literal["inherit"] = "inherit"
    """Track title. 'inherit' copies from source track."""

    language: str | Literal["inherit"] = "inherit"
    """Language tag. 'inherit' copies from source track."""

    position: Position | int = Position.END
    """Where to place synthesized track in audio track order."""

    @property
    def target_channels(self) -> int:
        """Return the target channel count as an integer."""
        if isinstance(self.channels, ChannelConfig):
            return self.channels.channel_count
        return self.channels


@dataclass(frozen=True)
class SourceTrackSelection:
    """Result of evaluating source preferences against file tracks.

    Contains the selected track and metadata about why it was chosen,
    useful for dry-run output and debugging.
    """

    track_index: int
    """Selected track index (0-based global index)."""

    track_info: "TrackInfo"
    """Full track information from database."""

    score: int
    """Preference matching score (higher is better)."""

    is_fallback: bool
    """True if no criteria matched, using first audio track."""

    match_reasons: tuple[str, ...]
    """Human-readable match reasons for dry-run output."""


@dataclass(frozen=True)
class SynthesisOperation:
    """Single synthesis operation to be executed.

    Represents a fully-resolved track synthesis with all parameters
    determined and ready for FFmpeg execution.
    """

    definition_name: str
    """Name from SynthesisTrackDefinition."""

    source_track: SourceTrackSelection
    """Selected source track with selection metadata."""

    target_codec: AudioCodec
    """Output codec."""

    target_channels: int
    """Output channel count."""

    target_bitrate: int | None
    """Output bitrate in bits per second, or None for lossless."""

    target_title: str
    """Final track title."""

    target_language: str
    """Final track language (ISO 639-2/B)."""

    target_position: int
    """Final audio track index (0-based, after position resolution)."""

    downmix_filter: str | None
    """FFmpeg filter for channel conversion, or None if same channels."""


@dataclass(frozen=True)
class SkippedSynthesis:
    """Record of a synthesis that was skipped.

    Provides information for dry-run output about why a defined
    synthesis track was not created.
    """

    definition_name: str
    """Name from SynthesisTrackDefinition."""

    reason: SkipReason
    """Why synthesis was skipped."""

    details: str
    """Human-readable explanation."""


@dataclass(frozen=True)
class TrackOrderEntry:
    """Entry in the projected final track order.

    Used by SynthesisPlan to show the expected audio track order
    after synthesis completes.
    """

    index: int
    """Position in final audio track order (0-based)."""

    track_type: Literal["original", "synthesized"]
    """Whether this is an existing or newly created track."""

    codec: str
    """Codec name."""

    channels: int
    """Channel count."""

    language: str
    """Language tag."""

    title: str | None
    """Track title, if any."""

    original_index: int | None = None
    """Original track index if this is an existing track."""

    synthesis_name: str | None = None
    """Synthesis definition name if this is a new track."""


@dataclass
class SynthesisPlan:
    """Complete plan for all synthesis operations on a file.

    This is the output of the synthesis planner, containing all
    operations to execute and skipped tracks with reasons.
    """

    file_id: str
    """UUID of the media file."""

    file_path: Path
    """Path to the media file."""

    operations: tuple[SynthesisOperation, ...] = ()
    """Tracks to create."""

    skipped: tuple[SkippedSynthesis, ...] = ()
    """Tracks skipped with reasons."""

    final_track_order: tuple[TrackOrderEntry, ...] = field(default_factory=tuple)
    """Projected final audio track order."""

    audio_tracks: tuple["TrackInfo", ...] = ()
    """Audio tracks from the file, needed for correct FFmpeg stream mapping."""

    @property
    def has_operations(self) -> bool:
        """True if there are operations to execute."""
        return len(self.operations) > 0

    @property
    def is_empty(self) -> bool:
        """True if no operations and nothing was skipped."""
        return len(self.operations) == 0 and len(self.skipped) == 0


# =============================================================================
# Default bitrates by codec and channel configuration
# =============================================================================

DEFAULT_BITRATES: dict[AudioCodec, dict[int, int]] = {
    AudioCodec.EAC3: {
        2: 384_000,  # Stereo: 384 kbps
        6: 640_000,  # 5.1: 640 kbps
        8: 768_000,  # 7.1: 768 kbps
    },
    AudioCodec.AAC: {
        2: 192_000,  # Stereo: 192 kbps
        6: 384_000,  # 5.1: 384 kbps
        8: 512_000,  # 7.1: 512 kbps
    },
    AudioCodec.AC3: {
        2: 192_000,  # Stereo: 192 kbps
        6: 448_000,  # 5.1: 448 kbps
        # AC3 doesn't support 7.1
    },
    AudioCodec.OPUS: {
        2: 128_000,  # Stereo: 128 kbps
        6: 256_000,  # 5.1: 256 kbps
        8: 384_000,  # 7.1: 384 kbps
    },
    # FLAC is lossless, no bitrate
    AudioCodec.FLAC: {},
}


def get_default_bitrate(codec: AudioCodec, channels: int) -> int | None:
    """Get default bitrate for a codec and channel count.

    Args:
        codec: Target codec.
        channels: Number of audio channels.

    Returns:
        Default bitrate in bits per second, or None for lossless codecs.
    """
    codec_rates = DEFAULT_BITRATES.get(codec, {})
    if not codec_rates:
        return None  # Lossless codec

    # Find the closest supported channel count
    if channels in codec_rates:
        return codec_rates[channels]

    # Find nearest supported channel count
    supported = sorted(codec_rates.keys())
    for ch in supported:
        if ch >= channels:
            return codec_rates[ch]

    # Use highest available
    return codec_rates[supported[-1]] if supported else None
