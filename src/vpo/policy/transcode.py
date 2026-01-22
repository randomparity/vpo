"""Audio transcoding policy evaluation and skip condition handling.

This module provides functions for:
- Determining how each audio track should be handled during transcoding
- Evaluating skip conditions for video transcoding (V6 policies)
- Creating audio plans from policy configurations

Audio codec matching is delegated to policy/codecs.py.
"""

from dataclasses import dataclass
from enum import Enum

from vpo.domain import TrackInfo
from vpo.policy.codecs import (
    audio_codec_matches_any,
    video_codec_matches_any,
)
from vpo.policy.types import (
    RESOLUTION_MAP,
    AudioTranscodeConfig,
    SkipCondition,
    TranscodePolicyConfig,
    parse_bitrate,
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
    if audio_codec_matches_any(codec, policy.audio_preserve_codecs):
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


# =============================================================================
# V6 Audio Planning Functions
# =============================================================================


def evaluate_audio_track_v6(
    track: TrackInfo,
    audio_config: AudioTranscodeConfig,
) -> AudioTrackPlan:
    """Evaluate how to handle a single audio track using V6 AudioTranscodeConfig.

    Args:
        track: Audio track info.
        audio_config: V6 audio transcode configuration.

    Returns:
        AudioTrackPlan with the action to take.
    """
    codec = track.codec
    stream_index = track.index  # Will be re-indexed by caller

    # Check if codec should be preserved (stream-copied)
    if audio_codec_matches_any(codec, audio_config.preserve_codecs):
        return AudioTrackPlan(
            track_index=track.index,
            stream_index=stream_index,
            codec=codec,
            language=track.language,
            channels=track.channels,
            channel_layout=track.channel_layout,
            action=AudioAction.COPY,
            reason=f"Codec '{codec}' is in preservation list (lossless)",
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
        target_codec=audio_config.transcode_to,
        target_bitrate=audio_config.transcode_bitrate,
        reason=f"Transcoding '{codec}' to '{audio_config.transcode_to}'",
    )


def create_audio_plan_v6(
    audio_tracks: list[TrackInfo],
    audio_config: AudioTranscodeConfig | None,
) -> AudioPlan:
    """Create a complete audio handling plan using V6 AudioTranscodeConfig.

    Args:
        audio_tracks: List of audio tracks from introspection.
        audio_config: V6 audio transcode configuration, or None for copy-all.

    Returns:
        AudioPlan with actions for all tracks.
    """
    track_plans = []
    audio_stream_index = 0

    for track in audio_tracks:
        if audio_config is not None:
            plan = evaluate_audio_track_v6(track, audio_config)
        else:
            # No audio config - copy all audio tracks
            plan = AudioTrackPlan(
                track_index=track.index,
                stream_index=track.index,
                codec=track.codec,
                language=track.language,
                channels=track.channels,
                channel_layout=track.channel_layout,
                action=AudioAction.COPY,
                reason="No audio transcode config - preserving all",
            )
        plan.stream_index = audio_stream_index
        track_plans.append(plan)
        audio_stream_index += 1

    return AudioPlan(tracks=track_plans, downmix_track=None)


# =============================================================================
# Skip Condition Evaluation (V6)
# =============================================================================


@dataclass(frozen=True)
class SkipEvaluationResult:
    """Result of skip condition evaluation.

    This dataclass provides a structured result for skip condition evaluation,
    including the skip decision and a human-readable reason.
    """

    skip: bool
    """True if transcoding should be skipped."""

    reason: str | None = None
    """Human-readable reason for the skip decision."""


def _resolution_within_threshold(
    width: int | None,
    height: int | None,
    resolution_within: str | None,
) -> bool:
    """Check if resolution is within the specified threshold.

    Args:
        width: Current video width.
        height: Current video height.
        resolution_within: Resolution preset (e.g., '1080p', '4k').

    Returns:
        True if resolution is at or below threshold.
    """
    if resolution_within is None:
        return True  # No threshold = always passes
    if width is None or height is None:
        return True  # Unknown resolution = can't evaluate, pass

    max_dims = RESOLUTION_MAP.get(resolution_within.casefold())
    if max_dims is None:
        return True  # Invalid preset = pass (validation should catch this earlier)

    max_width, max_height = max_dims
    return width <= max_width and height <= max_height


def _bitrate_under_threshold(
    current_bitrate: int | None,
    bitrate_under: str | None,
) -> bool:
    """Check if bitrate is under the specified threshold.

    Args:
        current_bitrate: Current video bitrate in bits per second.
        bitrate_under: Threshold bitrate string (e.g., '10M', '5000k').

    Returns:
        True if bitrate is under threshold.
    """
    if bitrate_under is None:
        return True  # No threshold = always passes
    if current_bitrate is None:
        return True  # Unknown bitrate = can't evaluate, pass

    threshold = parse_bitrate(bitrate_under)
    if threshold is None:
        return True  # Invalid threshold = pass

    return current_bitrate < threshold


def evaluate_skip_condition(
    skip_if: SkipCondition | None,
    video_codec: str | None,
    video_width: int | None,
    video_height: int | None,
    video_bitrate: int | None,
) -> SkipEvaluationResult:
    """Evaluate skip conditions for video transcoding.

    All specified conditions must pass for skip (AND logic).
    Unspecified conditions (None) are not evaluated and pass by default.

    This is the policy-layer implementation of skip condition evaluation,
    delegating codec matching to the unified policy/codecs.py module.

    Args:
        skip_if: Skip condition configuration.
        video_codec: Current video codec.
        video_width: Current video width.
        video_height: Current video height.
        video_bitrate: Current video bitrate in bits per second.

    Returns:
        SkipEvaluationResult with skip decision and reason.
    """
    if skip_if is None:
        return SkipEvaluationResult(skip=False, reason=None)

    # Check codec condition (uses unified codec matching from policy/codecs.py)
    codec_matches = video_codec_matches_any(video_codec, skip_if.codec_matches)
    if not codec_matches:
        return SkipEvaluationResult(
            skip=False,
            reason=f"Codec '{video_codec}' not in skip list {skip_if.codec_matches}",
        )

    # Check resolution condition
    resolution_ok = _resolution_within_threshold(
        video_width, video_height, skip_if.resolution_within
    )
    if not resolution_ok:
        return SkipEvaluationResult(
            skip=False,
            reason=(
                f"Resolution {video_width}x{video_height} exceeds "
                f"{skip_if.resolution_within} threshold"
            ),
        )

    # Check bitrate condition
    bitrate_ok = _bitrate_under_threshold(video_bitrate, skip_if.bitrate_under)
    if not bitrate_ok:
        threshold = parse_bitrate(skip_if.bitrate_under) or 0
        return SkipEvaluationResult(
            skip=False,
            reason=(
                f"Bitrate {video_bitrate} exceeds "
                f"{skip_if.bitrate_under} ({threshold}) threshold"
            ),
        )

    # All conditions passed - build skip reason
    reasons = []
    if skip_if.codec_matches:
        reasons.append(f"codec is {video_codec}")
    if skip_if.resolution_within:
        res_str = f"{video_width}x{video_height}"
        reasons.append(f"resolution {res_str} within {skip_if.resolution_within}")
    if skip_if.bitrate_under:
        reasons.append(f"bitrate under {skip_if.bitrate_under}")

    reason = (
        "Already compliant: " + ", ".join(reasons) if reasons else "All conditions met"
    )
    return SkipEvaluationResult(skip=True, reason=reason)
