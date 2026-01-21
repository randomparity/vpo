"""Audio argument building for FFmpeg transcoding.

This module provides functions for building FFmpeg audio-related arguments,
including track handling, encoding, and downmix filters.
"""

from vpo.policy.transcode import AudioAction, AudioPlan, AudioTrackPlan
from vpo.policy.types import TranscodePolicyConfig


def build_audio_args(audio_plan: AudioPlan, policy: TranscodePolicyConfig) -> list[str]:
    """Build FFmpeg arguments for audio track handling.

    Note: When AudioAction.REMOVE is present, explicit -map is used
    in build_ffmpeg_command() to exclude those tracks. This function
    only needs to specify codecs for remaining tracks, using output
    stream indices (which may differ from input indices if tracks were removed).

    Args:
        audio_plan: The audio handling plan.
        policy: Transcode policy configuration.

    Returns:
        List of FFmpeg arguments for audio.
    """
    args = []

    # Track output stream index (may differ from input if tracks removed)
    output_stream_idx = 0

    # Process each audio track
    for track in audio_plan.tracks:
        if track.action == AudioAction.COPY:
            # Stream copy this track
            args.extend([f"-c:a:{output_stream_idx}", "copy"])
            output_stream_idx += 1
        elif track.action == AudioAction.TRANSCODE:
            # Transcode this track
            target = track.target_codec or policy.audio_transcode_to
            encoder = get_audio_encoder(target)
            args.extend([f"-c:a:{output_stream_idx}", encoder])

            # Set bitrate for the track
            bitrate = track.target_bitrate or policy.audio_transcode_bitrate
            if bitrate:
                args.extend([f"-b:a:{output_stream_idx}", bitrate])
            output_stream_idx += 1
        elif track.action == AudioAction.REMOVE:
            # Track excluded by -map, no codec args needed
            # Do NOT increment output_stream_idx
            pass

    # Handle downmix as an additional output stream
    if audio_plan.downmix_track:
        downmix = audio_plan.downmix_track
        # Add filter for downmix
        # This creates a new stereo track from the first audio stream
        downmix_filter = build_downmix_filter(downmix)
        if downmix_filter:
            args.extend(["-filter_complex", downmix_filter])
            # The downmixed stream will be added by the filter

    return args


def get_audio_encoder(codec: str) -> str:
    """Get FFmpeg audio encoder name for a codec."""
    encoders = {
        "aac": "aac",
        "ac3": "ac3",
        "eac3": "eac3",
        "flac": "flac",
        "opus": "libopus",
        "mp3": "libmp3lame",
        "vorbis": "libvorbis",
        "pcm_s16le": "pcm_s16le",
        "pcm_s24le": "pcm_s24le",
    }
    return encoders.get(codec.casefold(), "aac")


def build_downmix_filter(downmix_track: AudioTrackPlan) -> str | None:
    """Build FFmpeg filter for audio downmix.

    Args:
        downmix_track: The downmix track plan.

    Returns:
        Filter string or None if no filter needed.
    """
    # Use the track's actual stream index, not hardcoded 0
    source_index = downmix_track.stream_index

    if downmix_track.channel_layout == "stereo":
        # Downmix to stereo using Dolby Pro Logic II encoding
        return (
            f"[0:a:{source_index}]aresample=matrix_encoding=dplii,"
            f"pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR[downmix]"
        )
    elif downmix_track.channel_layout == "5.1":
        # Downmix to 5.1 (usually from 7.1)
        return (
            f"[0:a:{source_index}]pan=5.1|FL=FL|FR=FR|FC=FC|LFE=LFE|"
            f"BL=0.5*BL+0.5*SL|BR=0.5*BR+0.5*SR[downmix]"
        )
    return None
