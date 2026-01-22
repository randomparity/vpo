"""Filter configuration types for policy.

This module contains types for track filtering, pre-processing actions,
container conversion, default flag handling, and transcription options.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TranscriptionPolicyOptions:
    """Policy options for transcription-based operations.

    Controls automatic language detection and updates via transcription analysis.
    """

    enabled: bool = False  # Enable transcription analysis during policy application
    update_language_from_transcription: bool = False  # Update track language tags
    confidence_threshold: float = 0.8  # Min confidence for updates (0.0-1.0)
    detect_commentary: bool = False  # Enable commentary detection
    reorder_commentary: bool = False  # Move commentary tracks to end

    def __post_init__(self) -> None:
        """Validate transcription policy options."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, "
                f"got {self.confidence_threshold}"
            )
        if self.reorder_commentary and not self.detect_commentary:
            raise ValueError("reorder_commentary requires detect_commentary to be true")


@dataclass(frozen=True)
class DefaultFlagsConfig:
    """Configuration for default and forced flag behavior in a policy."""

    set_first_video_default: bool = True
    set_preferred_audio_default: bool = True
    set_preferred_subtitle_default: bool = False
    clear_other_defaults: bool = True
    set_subtitle_default_when_audio_differs: bool = False
    set_subtitle_forced_when_audio_differs: bool = False
    """If True, set forced flag on preferred subtitle when default audio
    language differs from audio_language_preference. Useful for ensuring
    subtitles display automatically for foreign language content."""


@dataclass(frozen=True)
class LanguageFallbackConfig:
    """Configuration for fallback when preferred languages aren't found.

    This controls what happens when track filtering would remove all tracks
    because none match the preferred languages.
    """

    mode: Literal["content_language", "keep_all", "keep_first", "error"]
    """Fallback mode:
    - content_language: Keep tracks matching the content's original language
    - keep_all: Keep all tracks (disable filtering)
    - keep_first: Keep first N tracks to meet minimum
    - error: Fail with InsufficientTracksError
    """


@dataclass(frozen=True)
class AudioFilterConfig:
    """Configuration for filtering audio tracks.

    Audio filtering removes tracks whose language doesn't match the preferred
    languages list. A minimum of 1 audio track is always enforced to prevent
    creating audio-less files.

    V10: Added support for music, sfx, and non-speech track handling.
    """

    languages: tuple[str, ...]
    """ISO 639-2/B language codes to keep (e.g., ('eng', 'und', 'jpn')).
    Tracks with languages not in this list will be removed."""

    fallback: LanguageFallbackConfig | None = None
    """Fallback behavior when no tracks match preferred languages."""

    minimum: int = 1
    """Minimum number of audio tracks that must remain.
    If filtering would leave fewer tracks, fallback is triggered."""

    # V10: Music track handling
    keep_music_tracks: bool = True
    """If True, keep music tracks (score, soundtrack) even if not in languages list."""

    exclude_music_from_language_filter: bool = True
    """If True, music tracks bypass language filtering entirely."""

    # V10: SFX track handling
    keep_sfx_tracks: bool = True
    """If True, keep SFX tracks (sound effects) even if not in languages list."""

    exclude_sfx_from_language_filter: bool = True
    """If True, SFX tracks bypass language filtering entirely."""

    # V10: Non-speech track handling (unlabeled tracks detected as no speech)
    keep_non_speech_tracks: bool = True
    """If True, keep non-speech tracks (unlabeled tracks with no dialog)."""

    exclude_non_speech_from_language_filter: bool = True
    """If True, non-speech tracks bypass language filtering entirely."""

    def __post_init__(self) -> None:
        """Validate audio filter configuration."""
        if not self.languages:
            raise ValueError("languages cannot be empty")
        if self.minimum < 1:
            raise ValueError("minimum must be at least 1 for audio tracks")


@dataclass(frozen=True)
class SubtitleFilterConfig:
    """Configuration for filtering subtitle tracks.

    Subtitle filtering can remove tracks by language, remove all subtitles,
    or preserve forced subtitles regardless of language.
    """

    languages: tuple[str, ...] | None = None
    """ISO 639-2/B language codes to keep. If None, no language filtering."""

    preserve_forced: bool = False
    """If True, forced subtitle tracks are preserved regardless of language."""

    remove_all: bool = False
    """If True, remove all subtitle tracks. Overrides other settings."""


@dataclass(frozen=True)
class AttachmentFilterConfig:
    """Configuration for filtering attachment tracks.

    Attachments typically include fonts (for styled subtitles) and cover art.
    Removing fonts may affect rendering of ASS/SSA subtitles.
    """

    remove_all: bool = False
    """If True, remove all attachment tracks (fonts, cover art, etc.)."""


@dataclass(frozen=True)
class AudioActionsConfig:
    """Pre-processing actions for audio tracks.

    Actions are applied BEFORE filtering, allowing cleanup of misconfigured
    metadata before filter decisions are made. Use these to normalize track
    flags before applying language-based filtering.

    Example use case: Clear all forced flags on audio tracks, then use
    conditional rules to set the appropriate forced track.
    """

    clear_all_forced: bool = False
    """If True, clear forced flag from all audio tracks before filtering."""

    clear_all_default: bool = False
    """If True, clear default flag from all audio tracks before filtering."""

    clear_all_titles: bool = False
    """If True, clear title from all audio tracks before filtering."""


@dataclass(frozen=True)
class SubtitleActionsConfig:
    """Pre-processing actions for subtitle tracks.

    Actions are applied BEFORE filtering, allowing cleanup of misconfigured
    metadata before filter decisions are made. This is particularly useful
    when multiple subtitle tracks are incorrectly marked as forced.

    Example use case: Clear all forced flags, then use conditional rules
    to set the correct track as forced based on language or title.
    """

    clear_all_forced: bool = False
    """If True, clear forced flag from all subtitle tracks before filtering."""

    clear_all_default: bool = False
    """If True, clear default flag from all subtitle tracks before filtering."""

    clear_all_titles: bool = False
    """If True, clear title from all subtitle tracks before filtering."""


@dataclass(frozen=True)
class ContainerConfig:
    """Configuration for container format conversion.

    Container conversion performs lossless remuxing to the target format.
    Some codecs may be incompatible with certain containers.
    """

    target: Literal["mkv", "mp4"]
    """Target container format."""

    on_incompatible_codec: Literal["error", "skip", "transcode"] = "error"
    """Behavior when source contains codecs incompatible with target:
    - error: Fail with IncompatibleCodecError listing problematic tracks
    - skip: Skip the entire file with a warning
    - transcode: Transcode incompatible tracks (requires transcode config)
    """


@dataclass(frozen=True)
class FileTimestampConfig:
    """Configuration for file timestamp handling after processing.

    Controls whether file modification timestamps are preserved, set to
    release dates from external metadata (Radarr/Sonarr), or left as-is.
    """

    mode: Literal["preserve", "release_date", "now"] = "preserve"
    """Timestamp handling mode:
    - preserve: Restore original mtime after processing
    - release_date: Set to release/air date from plugin metadata
    - now: Use current time (default OS behavior, essentially a no-op)
    """

    fallback: Literal["preserve", "now", "skip"] = "preserve"
    """Fallback behavior when release_date mode has no date available:
    - preserve: Keep original mtime
    - now: Use current time
    - skip: Skip timestamp operation (leave as modified by processing)
    """

    date_source: Literal["auto", "radarr", "sonarr"] = "auto"
    """Source for release date:
    - auto: Auto-detect from external_source field in plugin metadata
    - radarr: Use only Radarr metadata
    - sonarr: Use only Sonarr metadata
    """
