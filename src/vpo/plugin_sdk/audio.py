"""Audio extraction utilities for transcription plugin authors.

This module provides functions to extract audio from media files for
transcription processing. All functions use VPO's configured tool paths.

Example:
    from vpo.plugin_sdk import (
        extract_audio_stream,
        get_file_duration,
        is_ffmpeg_available,
    )

    if is_ffmpeg_available():
        duration = get_file_duration(Path("/path/to/video.mkv"))
        audio_data = extract_audio_stream(
            Path("/path/to/video.mkv"),
            track_index=1,
            sample_duration=30,
        )
        # Process audio_data with transcription plugin...
"""

# Re-export from transcription module for plugin authors
# The implementation lives in transcription.audio_extractor to avoid
# circular imports between plugin_sdk and transcription modules.
from vpo.transcription.audio_extractor import (
    AudioExtractionError,
    extract_audio_stream,
    get_file_duration,
    is_ffmpeg_available,
)

__all__ = [
    "AudioExtractionError",
    "extract_audio_stream",
    "get_file_duration",
    "is_ffmpeg_available",
]
