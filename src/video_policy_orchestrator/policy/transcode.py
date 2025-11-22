"""Audio codec matching and transcoding policy evaluation.

This module provides functions for matching audio codecs against preservation rules
and determining how each audio track should be handled during transcoding.
"""

import fnmatch
from dataclasses import dataclass
from enum import Enum

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.models import (
    AudioPreservationRule,
    TranscodePolicyConfig,
)


class AudioAction(Enum):
    """Action to take for an audio track."""

    COPY = "copy"  # Stream copy (preserve as-is)
    TRANSCODE = "transcode"  # Transcode to target codec
    REMOVE = "remove"  # Remove the track


@dataclass
class AudioTrackPlan:
    """Plan for handling a single audio track."""

    track_index: int
    stream_index: int  # FFmpeg stream index (0-based within audio streams)
    codec: str | None
    language: str | None
    channels: int | None
    channel_layout: str | None
    action: AudioAction
    target_codec: str | None = None  # Only for TRANSCODE
    target_bitrate: str | None = None  # Only for TRANSCODE
    reason: str = ""  # Explanation for the action


@dataclass
class AudioPlan:
    """Complete plan for handling all audio tracks in a file."""

    tracks: list[AudioTrackPlan]
    downmix_track: AudioTrackPlan | None = None  # Additional stereo downmix

    @property
    def has_changes(self) -> bool:
        """True if any audio work is needed."""
        if self.downmix_track:
            return True
        return any(t.action != AudioAction.COPY for t in self.tracks)


# Common codec name aliases for matching
CODEC_ALIASES: dict[str, tuple[str, ...]] = {
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


def normalize_codec_name(codec: str) -> str:
    """Normalize a codec name for comparison.

    Args:
        codec: Codec name from ffprobe or policy.

    Returns:
        Normalized lowercase codec name.
    """
    if codec is None:
        return ""
    # Remove common suffixes and normalize
    normalized = codec.lower().strip()
    # Handle dts variants
    if "dts-hd" in normalized or "dtshd" in normalized:
        if "ma" in normalized.lower():
            return "dts-hd"
        return "dts-hd"
    if "truehd" in normalized:
        return "truehd"
    return normalized


def codec_matches(codec: str, pattern: str) -> bool:
    """Check if a codec matches a pattern.

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

    normalized_codec = normalize_codec_name(codec)
    normalized_pattern = pattern.lower().strip()

    # Direct match
    if normalized_codec == normalized_pattern:
        return True

    # Check aliases
    for alias_group, variants in CODEC_ALIASES.items():
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


def match_codec_to_rule(
    codec: str | None, rules: list[AudioPreservationRule]
) -> AudioPreservationRule | None:
    """Find the first matching rule for a codec.

    Args:
        codec: Codec name to check.
        rules: List of rules to check against.

    Returns:
        First matching rule, or None if no match.
    """
    if codec is None:
        return None

    for rule in rules:
        if codec_matches(codec, rule.codec_pattern):
            return rule
    return None


def should_preserve_codec(codec: str | None, preserve_list: tuple[str, ...]) -> bool:
    """Check if a codec should be preserved (stream-copied).

    Args:
        codec: Codec name to check.
        preserve_list: Tuple of codec patterns to preserve.

    Returns:
        True if the codec should be preserved.
    """
    if codec is None:
        return False

    for pattern in preserve_list:
        if codec_matches(codec, pattern):
            return True
    return False


def evaluate_audio_track(
    track: TrackInfo, policy: TranscodePolicyConfig
) -> AudioTrackPlan:
    """Evaluate how to handle a single audio track.

    Args:
        track: Audio track info.
        policy: Transcode policy configuration.

    Returns:
        AudioTrackPlan with the action to take.
    """
    codec = track.codec
    stream_index = track.index  # Will be re-indexed by caller

    # Check if codec should be preserved
    if should_preserve_codec(codec, policy.audio_preserve_codecs):
        return AudioTrackPlan(
            track_index=track.index,
            stream_index=stream_index,
            codec=codec,
            language=track.language,
            channels=track.channels,
            channel_layout=track.channel_layout,
            action=AudioAction.COPY,
            reason=f"Codec '{codec}' is in preservation list",
        )

    # If no preservation list is specified and no audio settings, copy everything
    if not policy.audio_preserve_codecs and not policy.has_audio_settings:
        return AudioTrackPlan(
            track_index=track.index,
            stream_index=stream_index,
            codec=codec,
            language=track.language,
            channels=track.channels,
            channel_layout=track.channel_layout,
            action=AudioAction.COPY,
            reason="No audio policy specified",
        )

    # Transcode to target codec
    return AudioTrackPlan(
        track_index=track.index,
        stream_index=stream_index,
        codec=codec,
        language=track.language,
        channels=track.channels,
        channel_layout=track.channel_layout,
        action=AudioAction.TRANSCODE,
        target_codec=policy.audio_transcode_to,
        target_bitrate=policy.audio_transcode_bitrate,
        reason=f"Transcoding '{codec}' to '{policy.audio_transcode_to}'",
    )


def create_audio_plan(
    audio_tracks: list[TrackInfo], policy: TranscodePolicyConfig
) -> AudioPlan:
    """Create a complete audio handling plan for a file.

    Args:
        audio_tracks: List of audio tracks from introspection.
        policy: Transcode policy configuration.

    Returns:
        AudioPlan with actions for all tracks.
    """
    track_plans = []
    audio_stream_index = 0

    for track in audio_tracks:
        plan = evaluate_audio_track(track, policy)
        plan.stream_index = audio_stream_index
        track_plans.append(plan)
        audio_stream_index += 1

    # Handle downmix option
    downmix_track = None
    if policy.audio_downmix and audio_tracks:
        # Find the best source track for downmix
        # Prefer tracks with more channels
        source_track = max(
            audio_tracks,
            key=lambda t: t.channels or 0,
            default=audio_tracks[0] if audio_tracks else None,
        )
        if source_track and (source_track.channels or 0) > 2:
            target_channels = 2 if policy.audio_downmix == "stereo" else 6
            downmix_track = AudioTrackPlan(
                track_index=-1,  # Synthetic track
                stream_index=0,  # Will be the first audio track for downmix source
                codec=source_track.codec,
                language=source_track.language,
                channels=target_channels,
                channel_layout=policy.audio_downmix,
                action=AudioAction.TRANSCODE,
                target_codec=policy.audio_transcode_to,
                target_bitrate=policy.audio_transcode_bitrate,
                reason=f"Downmix to {policy.audio_downmix}",
            )

    return AudioPlan(tracks=track_plans, downmix_track=downmix_track)


def describe_audio_plan(plan: AudioPlan) -> list[str]:
    """Generate human-readable descriptions of the audio plan.

    Args:
        plan: Audio plan to describe.

    Returns:
        List of description strings.
    """
    descriptions = []

    for track in plan.tracks:
        codec_str = track.codec or "unknown"
        lang_str = f" ({track.language})" if track.language else ""
        channels_str = f" {track.channel_layout}" if track.channel_layout else ""

        if track.action == AudioAction.COPY:
            descriptions.append(
                f"Audio #{track.stream_index}: "
                f"{codec_str}{channels_str}{lang_str} → copy"
            )
        elif track.action == AudioAction.TRANSCODE:
            descriptions.append(
                f"Audio #{track.stream_index}: {codec_str}{channels_str}{lang_str} → "
                f"{track.target_codec} @ {track.target_bitrate}"
            )
        elif track.action == AudioAction.REMOVE:
            descriptions.append(
                f"Audio #{track.stream_index}: "
                f"{codec_str}{channels_str}{lang_str} → remove"
            )

    if plan.downmix_track:
        descriptions.append(
            f"Audio (downmix): → {plan.downmix_track.channel_layout} "
            f"{plan.downmix_track.target_codec} @ {plan.downmix_track.target_bitrate}"
        )

    return descriptions
