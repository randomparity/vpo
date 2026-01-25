"""Core utilities package.

This package contains pure utility functions with no external dependencies.
These utilities are used across the codebase for common operations like
datetime parsing, formatting, validation, string manipulation, subprocess
invocation, and codec handling.
"""

from vpo.core.codecs import (
    AUDIO_CODEC_ALIASES,
    BITMAP_SUBTITLE_CODECS,
    DEFAULT_AUDIO_TRANSCODE_TARGET,
    MP4_AUDIO_TRANSCODE_DEFAULTS,
    MP4_COMPATIBLE_AUDIO_CODECS,
    MP4_COMPATIBLE_SUBTITLE_CODECS,
    MP4_COMPATIBLE_VIDEO_CODECS,
    MP4_CONVERTIBLE_SUBTITLE_CODECS,
    MP4_INCOMPATIBLE_CODECS,
    SUBTITLE_CODEC_ALIASES,
    VALID_TRANSCODE_AUDIO_CODECS,
    VALID_TRANSCODE_VIDEO_CODECS,
    VIDEO_CODEC_ALIASES,
    TranscodeTarget,
    audio_codec_matches,
    audio_codec_matches_any,
    codec_matches,
    is_codec_compatible,
    is_codec_mp4_compatible,
    normalize_codec,
    video_codec_matches,
    video_codec_matches_any,
)
from vpo.core.datetime_utils import (
    calculate_duration_seconds,
    parse_iso_timestamp,
    parse_relative_or_iso_time,
    parse_relative_time,
    parse_relative_time_iso,
)
from vpo.core.file_utils import (
    FileTimestampError,
    copy_file_mtime,
    get_file_mtime,
    set_file_mtime,
)
from vpo.core.formatting import (
    format_audio_languages,
    format_file_size,
    get_resolution_label,
    truncate_filename,
)
from vpo.core.json_utils import (
    JsonParseResult,
    parse_json_safe,
    parse_json_with_schema,
    serialize_json_safe,
)
from vpo.core.string_utils import (
    compare_strings_ci,
    contains_ci,
    normalize_string,
)
from vpo.core.subprocess_utils import run_command
from vpo.core.validation import is_valid_uuid

__all__ = [
    # codecs - constants
    "VIDEO_CODEC_ALIASES",
    "AUDIO_CODEC_ALIASES",
    "SUBTITLE_CODEC_ALIASES",
    "MP4_COMPATIBLE_VIDEO_CODECS",
    "MP4_COMPATIBLE_AUDIO_CODECS",
    "MP4_COMPATIBLE_SUBTITLE_CODECS",
    "MP4_CONVERTIBLE_SUBTITLE_CODECS",
    "BITMAP_SUBTITLE_CODECS",
    "MP4_INCOMPATIBLE_CODECS",
    "MP4_AUDIO_TRANSCODE_DEFAULTS",
    "DEFAULT_AUDIO_TRANSCODE_TARGET",
    "VALID_TRANSCODE_VIDEO_CODECS",
    "VALID_TRANSCODE_AUDIO_CODECS",
    "TranscodeTarget",
    # codecs - functions
    "normalize_codec",
    "video_codec_matches",
    "video_codec_matches_any",
    "audio_codec_matches",
    "audio_codec_matches_any",
    "codec_matches",
    "is_codec_mp4_compatible",
    "is_codec_compatible",
    # datetime_utils
    "parse_iso_timestamp",
    "calculate_duration_seconds",
    "parse_relative_time",
    "parse_relative_time_iso",
    "parse_relative_or_iso_time",
    # file_utils
    "FileTimestampError",
    "get_file_mtime",
    "set_file_mtime",
    "copy_file_mtime",
    # formatting
    "format_file_size",
    "get_resolution_label",
    "format_audio_languages",
    "truncate_filename",
    # json_utils
    "JsonParseResult",
    "parse_json_safe",
    "parse_json_with_schema",
    "serialize_json_safe",
    # string_utils
    "normalize_string",
    "compare_strings_ci",
    "contains_ci",
    # subprocess_utils
    "run_command",
    # validation
    "is_valid_uuid",
]
