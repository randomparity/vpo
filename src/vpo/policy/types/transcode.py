"""Transcode configuration types for policy.

This module contains all types related to video and audio transcoding,
including quality settings, scaling, hardware acceleration, and skip conditions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from vpo.policy.types.enums import (
    RESOLUTION_MAP,
    VALID_AUDIO_CODECS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
)


class QualityMode(Enum):
    """Video encoding quality mode."""

    CRF = "crf"  # Constant Rate Factor (variable bitrate, quality-based)
    BITRATE = "bitrate"  # Target bitrate mode (constant bitrate)
    CONSTRAINED_QUALITY = "constrained_quality"  # CRF with max bitrate cap


class ScaleAlgorithm(Enum):
    """Video scaling algorithm."""

    LANCZOS = "lanczos"  # Best quality for downscaling
    BICUBIC = "bicubic"  # Good quality, faster
    BILINEAR = "bilinear"  # Fast, acceptable quality


class HardwareAccelMode(Enum):
    """Hardware acceleration mode for video encoding."""

    AUTO = "auto"  # Auto-detect best available encoder
    NVENC = "nvenc"  # Force NVIDIA NVENC
    QSV = "qsv"  # Force Intel Quick Sync Video
    VAAPI = "vaapi"  # Force VAAPI (Linux AMD/Intel)
    NONE = "none"  # Force CPU encoding


# Valid encoding presets (slowest to fastest)
VALID_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)

# Valid tune options per encoder type
# x264/x265 support these tunes
X264_X265_TUNES = (
    "film",
    "animation",
    "grain",
    "stillimage",
    "fastdecode",
    "zerolatency",
)

# Codec-specific default CRF values (balanced quality)
DEFAULT_CRF_VALUES: dict[str, int] = {
    "h264": 23,
    "x264": 23,
    "hevc": 28,
    "h265": 28,
    "x265": 28,
    "vp9": 31,
    "av1": 30,
}


def parse_bitrate(bitrate_str: str) -> int | None:
    """Parse a bitrate string like '10M' or '5000k' to bits per second.

    Args:
        bitrate_str: Bitrate string with M/m (megabits) or K/k (kilobits) suffix.

    Returns:
        Bitrate in bits per second, or None if parsing fails.

    Examples:
        parse_bitrate("10M") -> 10_000_000
        parse_bitrate("5000k") -> 5_000_000
        parse_bitrate("2500K") -> 2_500_000
    """
    if not bitrate_str:
        return None

    bitrate_str = bitrate_str.strip()
    try:
        if bitrate_str[-1].casefold() == "m":
            return int(float(bitrate_str[:-1]) * 1_000_000)
        elif bitrate_str[-1].casefold() == "k":
            return int(float(bitrate_str[:-1]) * 1_000)
        else:
            # Assume bits per second
            return int(bitrate_str)
    except (ValueError, IndexError):
        return None


def get_default_crf(codec: str) -> int:
    """Get codec-specific default CRF value.

    Args:
        codec: Video codec name (h264, hevc, vp9, av1).

    Returns:
        Default CRF value for the codec.
    """
    return DEFAULT_CRF_VALUES.get(codec.casefold(), 23)


@dataclass(frozen=True)
class AudioPreservationRule:
    """Rule for handling a specific audio codec.

    Used to define fine-grained control over audio codec handling
    beyond the simple preserve/transcode list.
    """

    codec_pattern: str  # Codec name or pattern (e.g., "truehd", "dts*")
    action: str  # "preserve", "transcode", "remove"
    transcode_to: str | None = None  # Target codec if action=transcode
    transcode_bitrate: str | None = None  # Target bitrate if action=transcode

    def __post_init__(self) -> None:
        """Validate the rule configuration."""
        valid_actions = ("preserve", "transcode", "remove")
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action: {self.action}. "
                f"Must be one of: {', '.join(valid_actions)}"
            )
        if self.action == "transcode" and not self.transcode_to:
            raise ValueError("transcode_to is required when action is 'transcode'")


@dataclass(frozen=True)
class TranscodePolicyConfig:
    """Transcoding-specific policy configuration."""

    # Video settings
    target_video_codec: str | None = None  # hevc, h264, vp9, av1
    target_crf: int | None = None  # 0-51 for x264/x265
    target_bitrate: str | None = None  # e.g., "5M", "2500k"
    max_resolution: str | None = None  # 1080p, 720p, 4k, etc.
    max_width: int | None = None  # Max width in pixels
    max_height: int | None = None  # Max height in pixels

    # Audio preservation
    audio_preserve_codecs: tuple[str, ...] = ()  # Codecs to stream copy
    audio_transcode_to: str = "aac"  # Target codec for non-preserved
    audio_transcode_bitrate: str = "192k"  # Bitrate for transcoded audio
    audio_downmix: str | None = None  # None, "stereo", "5.1"

    # Destination
    destination: str | None = None  # Template string for output location
    destination_fallback: str = "Unknown"  # Fallback for missing metadata

    def __post_init__(self) -> None:
        """Validate transcode policy configuration."""
        if self.target_video_codec is not None:
            codec = self.target_video_codec.casefold()
            if codec not in VALID_VIDEO_CODECS:
                raise ValueError(
                    f"Invalid target_video_codec: {self.target_video_codec}. "
                    f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
                )

        if self.target_crf is not None:
            if not 0 <= self.target_crf <= 51:
                raise ValueError(
                    f"Invalid target_crf: {self.target_crf}. Must be 0-51."
                )

        if self.max_resolution is not None:
            if self.max_resolution.casefold() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid max_resolution: {self.max_resolution}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )

        if self.audio_transcode_to.casefold() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid audio_transcode_to: {self.audio_transcode_to}. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )

        if self.audio_downmix is not None:
            if self.audio_downmix not in ("stereo", "5.1"):
                raise ValueError(
                    f"Invalid audio_downmix: {self.audio_downmix}. "
                    "Must be 'stereo' or '5.1'."
                )

    @property
    def has_video_settings(self) -> bool:
        """True if any video transcoding settings are specified."""
        return any(
            [
                self.target_video_codec,
                self.target_crf,
                self.target_bitrate,
                self.max_resolution,
                self.max_width,
                self.max_height,
            ]
        )

    @property
    def has_audio_settings(self) -> bool:
        """True if audio processing settings are specified."""
        return bool(self.audio_preserve_codecs) or self.audio_downmix is not None

    def get_max_dimensions(self) -> tuple[int, int] | None:
        """Get max dimensions from resolution preset or explicit values.

        Returns:
            (max_width, max_height) tuple or None if no limit.
        """
        if self.max_resolution:
            return RESOLUTION_MAP.get(self.max_resolution.casefold())
        if self.max_width or self.max_height:
            return (self.max_width or 99999, self.max_height or 99999)
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscodePolicyConfig":
        """Create TranscodePolicyConfig from a dictionary.

        Args:
            data: Dictionary with policy configuration. Keys match dataclass fields.
                  Supports both 'audio_transcode_bitrate' and legacy 'audio_bitrate'.

        Returns:
            TranscodePolicyConfig instance.

        Raises:
            ValueError: If validation fails on any field.
        """
        return cls(
            target_video_codec=data.get("target_video_codec"),
            target_crf=data.get("target_crf"),
            target_bitrate=data.get("target_bitrate"),
            max_resolution=data.get("max_resolution"),
            max_width=data.get("max_width"),
            max_height=data.get("max_height"),
            audio_preserve_codecs=tuple(data.get("audio_preserve_codecs", [])),
            audio_transcode_to=data.get("audio_transcode_to", "aac"),
            audio_transcode_bitrate=data.get(
                "audio_transcode_bitrate",
                data.get("audio_bitrate", "192k"),  # Legacy key support
            ),
            audio_downmix=data.get("audio_downmix"),
            destination=data.get("destination"),
            destination_fallback=data.get("destination_fallback", "Unknown"),
        )


@dataclass(frozen=True)
class SkipCondition:
    """Conditions for skipping video transcoding (AND logic).

    All specified conditions must be true for the skip to occur.
    Unspecified conditions (None) are not evaluated.
    """

    codec_matches: tuple[str, ...] | None = None
    """Skip if video codec matches any in this list (case-insensitive)."""

    resolution_within: str | None = None
    """Skip if video resolution <= this preset (e.g., '1080p')."""

    bitrate_under: str | None = None
    """Skip if video bitrate < this value (e.g., '10M')."""

    def __post_init__(self) -> None:
        """Validate skip condition configuration."""
        # Require at least one condition to be specified
        if (
            self.codec_matches is None
            and self.resolution_within is None
            and self.bitrate_under is None
        ):
            raise ValueError(
                "SkipCondition requires at least one condition to be specified. "
                "Empty skip_if would skip all files. "
                "Specify codec_matches, resolution_within, or bitrate_under."
            )
        if self.resolution_within is not None:
            if self.resolution_within.casefold() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid resolution_within: {self.resolution_within}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )
        if self.bitrate_under is not None:
            if parse_bitrate(self.bitrate_under) is None:
                raise ValueError(
                    f"Invalid bitrate_under: {self.bitrate_under}. "
                    "Must be a number followed by M or k (e.g., '10M', '5000k')."
                )


@dataclass(frozen=True)
class QualitySettings:
    """Video encoding quality settings."""

    mode: QualityMode = QualityMode.CRF
    """Quality control mode (crf, bitrate, constrained_quality)."""

    crf: int | None = None
    """CRF value (0-51). Lower = better quality. Defaults applied per codec."""

    bitrate: str | None = None
    """Target bitrate for bitrate mode (e.g., '5M', '2500k')."""

    min_bitrate: str | None = None
    """Minimum bitrate for constrained quality."""

    max_bitrate: str | None = None
    """Maximum bitrate for constrained quality."""

    preset: str = "medium"
    """Encoding preset (ultrafast to veryslow)."""

    tune: str | None = None
    """Content-specific tune option (film, animation, grain, etc.)."""

    two_pass: bool = False
    """Enable two-pass encoding for accurate bitrate targeting."""

    def __post_init__(self) -> None:
        """Validate quality settings."""
        if self.crf is not None:
            if not 0 <= self.crf <= 51:
                raise ValueError(f"Invalid crf: {self.crf}. Must be 0-51.")

        if self.preset not in VALID_PRESETS:
            raise ValueError(
                f"Invalid preset: {self.preset}. "
                f"Must be one of: {', '.join(VALID_PRESETS)}"
            )

        if self.tune is not None:
            if self.tune not in X264_X265_TUNES:
                raise ValueError(
                    f"Invalid tune: {self.tune}. "
                    f"Must be one of: {', '.join(X264_X265_TUNES)}"
                )

        # Validate bitrate strings
        for bitrate_name, bitrate_val in [
            ("bitrate", self.bitrate),
            ("min_bitrate", self.min_bitrate),
            ("max_bitrate", self.max_bitrate),
        ]:
            if bitrate_val is not None:
                if parse_bitrate(bitrate_val) is None:
                    raise ValueError(
                        f"Invalid {bitrate_name}: {bitrate_val}. "
                        "Must be a number followed by M or k."
                    )

        # Validate mode-specific requirements
        if self.mode == QualityMode.BITRATE and self.bitrate is None:
            raise ValueError("bitrate is required when mode is 'bitrate'")


@dataclass(frozen=True)
class ScalingSettings:
    """Video resolution scaling settings."""

    max_resolution: str | None = None
    """Maximum resolution preset (e.g., '1080p', '720p', '4k')."""

    max_width: int | None = None
    """Maximum width in pixels (alternative to max_resolution)."""

    max_height: int | None = None
    """Maximum height in pixels (alternative to max_resolution)."""

    algorithm: ScaleAlgorithm = ScaleAlgorithm.LANCZOS
    """Scaling algorithm to use."""

    upscale: bool = False
    """Allow upscaling smaller content (false = preserve original if smaller)."""

    def __post_init__(self) -> None:
        """Validate scaling settings."""
        if self.max_resolution is not None:
            if self.max_resolution.casefold() not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid max_resolution: {self.max_resolution}. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )

        if self.max_width is not None and self.max_width <= 0:
            raise ValueError(f"max_width must be positive, got {self.max_width}")

        if self.max_height is not None and self.max_height <= 0:
            raise ValueError(f"max_height must be positive, got {self.max_height}")

    def get_max_dimensions(self) -> tuple[int, int] | None:
        """Get max dimensions from resolution preset or explicit values.

        Returns:
            (max_width, max_height) tuple or None if no limit.
        """
        if self.max_resolution:
            return RESOLUTION_MAP.get(self.max_resolution.casefold())
        if self.max_width or self.max_height:
            return (self.max_width or 99999, self.max_height or 99999)
        return None


@dataclass(frozen=True)
class HardwareAccelConfig:
    """Hardware acceleration settings."""

    enabled: HardwareAccelMode = HardwareAccelMode.AUTO
    """Hardware acceleration mode."""

    fallback_to_cpu: bool = True
    """Fall back to CPU encoding if hardware encoder fails or unavailable."""

    def __post_init__(self) -> None:
        """Validate hardware acceleration configuration."""
        if not isinstance(self.enabled, HardwareAccelMode):
            raise ValueError(
                f"enabled must be a HardwareAccelMode enum value, "
                f"got {type(self.enabled).__name__}: {self.enabled}"
            )


@dataclass(frozen=True)
class AudioTranscodeConfig:
    """Audio handling configuration for video transcoding.

    Controls which audio codecs are preserved (stream-copied) and
    which are transcoded during video transcoding operations.
    """

    preserve_codecs: tuple[str, ...] = ("truehd", "dts-hd", "flac", "pcm_s24le")
    """Audio codecs to preserve (stream-copy without re-encoding)."""

    transcode_to: str = "aac"
    """Target codec for non-preserved audio tracks."""

    transcode_bitrate: str = "192k"
    """Bitrate for transcoded audio tracks."""

    def __post_init__(self) -> None:
        """Validate audio transcode configuration."""
        if self.transcode_to.casefold() not in VALID_AUDIO_CODECS:
            raise ValueError(
                f"Invalid transcode_to: {self.transcode_to}. "
                f"Must be one of: {', '.join(sorted(VALID_AUDIO_CODECS))}"
            )
        if parse_bitrate(self.transcode_bitrate) is None:
            raise ValueError(
                f"Invalid transcode_bitrate: {self.transcode_bitrate}. "
                "Must be a number followed by k (e.g., '192k', '256k')."
            )


@dataclass(frozen=True)
class VideoTranscodeConfig:
    """Video transcoding configuration within a transcode policy.

    This is the new V6 configuration that extends the existing
    TranscodePolicyConfig with conditional skip logic and enhanced settings.
    """

    target_codec: str
    """Target video codec (hevc, h264, vp9, av1)."""

    skip_if: SkipCondition | None = None
    """Conditions for skipping transcoding."""

    quality: QualitySettings | None = None
    """Quality settings (CRF, bitrate, preset, tune)."""

    scaling: ScalingSettings | None = None
    """Resolution scaling settings."""

    hardware_acceleration: HardwareAccelConfig | None = None
    """Hardware acceleration settings."""

    ffmpeg_args: tuple[str, ...] | None = None
    """Custom FFmpeg command-line arguments to append before output.

    Example: ("-max_muxing_queue_size", "9999")
    """

    def __post_init__(self) -> None:
        """Validate video transcode configuration."""
        if self.target_codec.casefold() not in VALID_VIDEO_CODECS:
            raise ValueError(
                f"Invalid target_codec: {self.target_codec}. "
                f"Must be one of: {', '.join(sorted(VALID_VIDEO_CODECS))}"
            )


@dataclass(frozen=True)
class VideoTranscodeAction:
    """Planned video transcode action."""

    source_codec: str
    """Source video codec."""

    target_codec: str
    """Target video codec."""

    encoder: str
    """FFmpeg encoder name (e.g., 'libx265', 'hevc_nvenc')."""

    crf: int | None = None
    """CRF value if using CRF mode."""

    bitrate: str | None = None
    """Target bitrate if using bitrate mode."""

    max_bitrate: str | None = None
    """Max bitrate if using constrained quality mode."""

    preset: str = "medium"
    """Encoding preset."""

    tune: str | None = None
    """Tune option."""

    scale_width: int | None = None
    """Target width if scaling."""

    scale_height: int | None = None
    """Target height if scaling."""

    scale_algorithm: str | None = None
    """Scaling algorithm name."""


@dataclass(frozen=True)
class VideoTranscodeResult:
    """Result of video transcode evaluation.

    This captures whether transcoding was skipped and the planned
    operations if not skipped.
    """

    skipped: bool
    """True if transcoding was skipped due to skip conditions."""

    skip_reason: str | None = None
    """Human-readable reason for skipping (e.g., 'Already HEVC at 1080p')."""

    video_action: VideoTranscodeAction | None = None
    """Planned video transcode action if not skipped."""

    audio_actions: tuple["AudioTrackAction", ...] = ()
    """Planned audio track actions."""

    encoder: str | None = None
    """Selected encoder name (e.g., 'hevc_nvenc', 'libx265')."""

    encoder_type: str | None = None
    """Encoder type: 'hardware' or 'software'."""


@dataclass(frozen=True)
class AudioTrackAction:
    """Planned action for a single audio track."""

    track_index: int
    """Track index in source file."""

    action: str
    """Action: 'copy', 'transcode', or 'remove'."""

    source_codec: str | None = None
    """Source audio codec."""

    target_codec: str | None = None
    """Target codec if transcoding."""

    target_bitrate: str | None = None
    """Target bitrate if transcoding."""

    reason: str = ""
    """Human-readable reason for the action."""
