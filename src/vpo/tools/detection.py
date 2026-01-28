"""External tool detection and version parsing.

This module provides functions to detect external tools, parse their versions,
and enumerate their capabilities (codecs, formats, filters for ffmpeg).
"""

import logging
import platform
import re
import shutil
import subprocess  # nosec B404 - subprocess is required for tool detection
from datetime import datetime, timezone
from pathlib import Path

from vpo.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolDetectionConfig,
    ToolInfo,
    ToolRegistry,
    ToolStatus,
)

logger = logging.getLogger(__name__)

# Timeout for version/capability detection commands (seconds)
DETECTION_TIMEOUT = 10


def parse_version_string(version_str: str) -> tuple[int, ...] | None:
    """Parse a version string into a comparable tuple.

    Handles various version formats:
    - "6.1.1" -> (6, 1, 1)
    - "6.1" -> (6, 1)
    - "n6.1.1" -> (6, 1, 1)  (ffmpeg nightlies)
    - "81.0" -> (81, 0)  (mkvtoolnix)

    Args:
        version_str: Version string to parse.

    Returns:
        Tuple of version components, or None if parsing fails.
    """
    if not version_str:
        return None

    # Strip leading 'n' or 'v' prefix
    version_str = version_str.lstrip("nv")

    # Extract numeric version parts (stop at first non-numeric segment)
    match = re.match(r"(\d+(?:\.\d+)*)", version_str)
    if not match:
        return None

    parts = match.group(1).split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _find_tool(name: str, configured_path: Path | None = None) -> Path | None:
    """Find a tool executable.

    Args:
        name: Tool name (e.g., "ffmpeg").
        configured_path: Optional configured path override.

    Returns:
        Path to tool executable, or None if not found.
    """
    # Try configured path first
    if configured_path:
        if configured_path.is_file():
            return configured_path
        logger.warning(
            "Configured path for %s is not a file: %s", name, configured_path
        )

    # Fall back to PATH lookup
    which_result = shutil.which(name)
    if which_result:
        return Path(which_result)

    return None


def _run_command(
    args: list[str], timeout: int = DETECTION_TIMEOUT
) -> tuple[str, str, int]:
    """Run a command and capture output.

    Args:
        args: Command and arguments.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (stdout, stderr, returncode).
    """
    try:
        result = subprocess.run(  # nosec B603 - args are tool paths and fixed flags
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out: %s", " ".join(args))
        return "", "timeout", -1
    except FileNotFoundError:
        return "", "not found", -1
    except Exception as e:
        logger.warning("Command failed: %s - %s", " ".join(args), e)
        return "", str(e), -1


# =============================================================================
# Generic Tool Detection
# =============================================================================


def _detect_tool_generic(
    config: ToolDetectionConfig,
    configured_path: Path | None = None,
) -> ToolInfo:
    """Generic tool detection with common boilerplate.

    Args:
        config: Tool-specific detection configuration.
        configured_path: Optional configured path to the tool.

    Returns:
        ToolInfo subclass instance with detection results.
    """
    info = config.info_factory()
    info.detected_at = datetime.now(timezone.utc)

    path = _find_tool(config.name, configured_path)
    if not path:
        info.status = ToolStatus.MISSING
        info.status_message = f"{config.name} not found in PATH"
        return info

    info.path = path

    stdout, stderr, rc = _run_command([str(path), config.version_flag])
    if rc != 0:
        info.status = ToolStatus.ERROR
        info.status_message = f"Failed to get {config.name} version: {stderr}"
        return info

    version_match = re.search(config.version_pattern, stdout)
    if version_match:
        info.version = version_match.group(1)
        info.version_tuple = parse_version_string(info.version)
        if info.version_tuple is None:
            logger.warning(
                "Could not parse %s version '%s' into comparable tuple",
                config.name,
                info.version,
            )

    if config.post_detect:
        config.post_detect(info, path, stdout)

    info.status = ToolStatus.AVAILABLE
    info.status_message = None
    return info


# =============================================================================
# Post-Detection Callbacks
# =============================================================================


def _probe_wav_codec_requirement(ffmpeg_path: Path) -> bool:
    """Probe whether FFmpeg requires explicit codec for WAV output.

    Some FFmpeg builds disable the default PCM encoder for format detection,
    requiring explicit -acodec pcm_s16le for WAV output.

    Args:
        ffmpeg_path: Path to ffmpeg executable.

    Returns:
        True if explicit codec is required, False otherwise.
    """
    null_device = "NUL" if platform.system() == "Windows" else "/dev/null"
    cmd = [
        str(ffmpeg_path),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono",
        "-t",
        "0.1",
        "-f",
        "wav",
        "-y",
        null_device,
    ]
    try:
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, timeout=5
        )
        return result.returncode != 0
    except Exception:
        # On probe failure, assume explicit codec is required (safer default)
        return True


def _probe_single_hw_encoder(ffmpeg_path: Path, encoder: str) -> bool:
    """Probe a single hardware encoder for actual usability.

    Args:
        ffmpeg_path: Path to ffmpeg executable.
        encoder: Encoder name to test (e.g., "h264_nvenc").

    Returns:
        True if encoder is usable, False otherwise.
    """
    null_device = "NUL" if platform.system() == "Windows" else "/dev/null"
    cmd = [
        str(ffmpeg_path),
        "-f",
        "lavfi",
        "-i",
        "nullsrc=s=64x64:d=0.1",
        "-c:v",
        encoder,
        "-f",
        "null",
        "-y",
        null_device,
    ]
    try:
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _probe_hw_encoder_availability(
    ffmpeg_path: Path, caps: FFmpegCapabilities
) -> dict[str, bool]:
    """Probe hardware encoders for actual runtime usability.

    Encoder being listed in ffmpeg -encoders does not mean it works.
    This probes actual usability by attempting to encode a test frame.

    Args:
        ffmpeg_path: Path to ffmpeg executable.
        caps: FFmpegCapabilities with encoder list.

    Returns:
        Dict mapping encoder type to availability status.
    """
    hw_status: dict[str, bool] = {"nvenc": False, "qsv": False, "vaapi": False}

    # Only probe encoders that appear in the encoder list
    if caps.has_encoder("h264_nvenc") or caps.has_encoder("hevc_nvenc"):
        hw_status["nvenc"] = _probe_single_hw_encoder(ffmpeg_path, "h264_nvenc")
        logger.debug("NVENC probe result: %s", hw_status["nvenc"])

    if caps.has_encoder("h264_qsv") or caps.has_encoder("hevc_qsv"):
        hw_status["qsv"] = _probe_single_hw_encoder(ffmpeg_path, "h264_qsv")
        logger.debug("QSV probe result: %s", hw_status["qsv"])

    if caps.has_encoder("h264_vaapi") or caps.has_encoder("hevc_vaapi"):
        hw_status["vaapi"] = _probe_single_hw_encoder(ffmpeg_path, "h264_vaapi")
        logger.debug("VAAPI probe result: %s", hw_status["vaapi"])

    return hw_status


def _ffmpeg_post_detect(info: ToolInfo, path: Path, stdout: str) -> None:
    """Post-detection hook for FFmpeg capabilities."""
    assert isinstance(info, FFmpegInfo)
    info.capabilities = _detect_ffmpeg_capabilities(path, stdout)

    # Set version-derived behavioral flags
    v = info.version_tuple
    if v:
        caps = info.capabilities
        caps.supports_stats_period = v >= (4, 3)
        caps.supports_fps_mode = v >= (5, 1)
        logger.debug(
            "FFmpeg %s: stats_period=%s, fps_mode=%s",
            info.version,
            caps.supports_stats_period,
            caps.supports_fps_mode,
        )

        # Probe build-specific behaviors
        caps.requires_explicit_pcm_codec = _probe_wav_codec_requirement(path)
        logger.debug(
            "FFmpeg requires_explicit_pcm_codec=%s", caps.requires_explicit_pcm_codec
        )

        # Probe hardware encoder availability
        hw = _probe_hw_encoder_availability(path, caps)
        caps.hw_nvenc_available = hw.get("nvenc", False)
        caps.hw_qsv_available = hw.get("qsv", False)
        caps.hw_vaapi_available = hw.get("vaapi", False)


def _mkvmerge_post_detect(info: ToolInfo, _path: Path, _stdout: str) -> None:
    """Post-detection hook for mkvmerge capabilities."""
    assert isinstance(info, MkvmergeInfo)
    # --track-order has been available for a very long time
    info.supports_track_order = True
    # -J (JSON output) added in mkvtoolnix 9.0
    if info.version_tuple:
        info.supports_json_output = info.version_tuple >= (9, 0)


def _mkvpropedit_post_detect(info: ToolInfo, _path: Path, _stdout: str) -> None:
    """Post-detection hook for mkvpropedit capabilities."""
    assert isinstance(info, MkvpropeditInfo)
    # All modern versions support these features
    info.supports_track_edit = True
    info.supports_add_attachment = True


# =============================================================================
# Tool Detection Configurations
# =============================================================================


FFPROBE_CONFIG = ToolDetectionConfig(
    name="ffprobe",
    version_flag="-version",
    version_pattern=r"ffprobe version (\S+)",
    info_factory=FFprobeInfo,
)

FFMPEG_CONFIG = ToolDetectionConfig(
    name="ffmpeg",
    version_flag="-version",
    version_pattern=r"ffmpeg version (\S+)",
    info_factory=FFmpegInfo,
    post_detect=_ffmpeg_post_detect,
)

MKVMERGE_CONFIG = ToolDetectionConfig(
    name="mkvmerge",
    version_flag="--version",
    version_pattern=r"mkvmerge v(\S+)",
    info_factory=MkvmergeInfo,
    post_detect=_mkvmerge_post_detect,
)

MKVPROPEDIT_CONFIG = ToolDetectionConfig(
    name="mkvpropedit",
    version_flag="--version",
    version_pattern=r"mkvpropedit v(\S+)",
    info_factory=MkvpropeditInfo,
    post_detect=_mkvpropedit_post_detect,
)


# =============================================================================
# Public Detection Functions
# =============================================================================


def detect_ffmpeg(configured_path: Path | None = None) -> FFmpegInfo:
    """Detect ffmpeg and enumerate its capabilities.

    Args:
        configured_path: Optional configured path to ffmpeg.

    Returns:
        FFmpegInfo with version and capabilities.
    """
    result = _detect_tool_generic(FFMPEG_CONFIG, configured_path)
    assert isinstance(result, FFmpegInfo)
    return result


def _detect_ffmpeg_capabilities(
    ffmpeg_path: Path, version_output: str
) -> FFmpegCapabilities:
    """Detect detailed ffmpeg capabilities.

    Args:
        ffmpeg_path: Path to ffmpeg executable.
        version_output: Output from ffmpeg -version.

    Returns:
        FFmpegCapabilities with detected features.
    """
    caps = FFmpegCapabilities()

    # Parse configuration from version output
    config_pattern = r"configuration:\s*(.+?)(?:\n|$)"
    config_match = re.search(config_pattern, version_output, re.DOTALL)
    if config_match:
        caps.configuration = config_match.group(1).strip()
        # Extract --enable flags
        caps.build_flags = re.findall(r"--enable-(\S+)", caps.configuration)
        caps.is_gpl = "gpl" in caps.build_flags
        caps.is_nonfree = "nonfree" in caps.build_flags

    # Detect encoders
    stdout, stderr, rc = _run_command([str(ffmpeg_path), "-encoders", "-hide_banner"])
    if rc == 0:
        caps.encoders = _parse_codec_list(stdout)
    else:
        logger.warning("Failed to enumerate ffmpeg encoders: %s", stderr)

    # Detect decoders
    stdout, stderr, rc = _run_command([str(ffmpeg_path), "-decoders", "-hide_banner"])
    if rc == 0:
        caps.decoders = _parse_codec_list(stdout)
    else:
        logger.warning("Failed to enumerate ffmpeg decoders: %s", stderr)

    # Detect muxers (output formats)
    stdout, stderr, rc = _run_command([str(ffmpeg_path), "-muxers", "-hide_banner"])
    if rc == 0:
        caps.muxers = _parse_format_list(stdout)
    else:
        logger.warning("Failed to enumerate ffmpeg muxers: %s", stderr)

    # Detect demuxers (input formats)
    stdout, stderr, rc = _run_command([str(ffmpeg_path), "-demuxers", "-hide_banner"])
    if rc == 0:
        caps.demuxers = _parse_format_list(stdout)
    else:
        logger.warning("Failed to enumerate ffmpeg demuxers: %s", stderr)

    # Detect filters
    stdout, stderr, rc = _run_command([str(ffmpeg_path), "-filters", "-hide_banner"])
    if rc == 0:
        caps.filters = _parse_filter_list(stdout)
    else:
        logger.warning("Failed to enumerate ffmpeg filters: %s", stderr)

    return caps


def _parse_ffmpeg_list(output: str, pattern: str) -> set[str]:
    """Parse ffmpeg list output (encoders, decoders, muxers, demuxers, filters).

    Args:
        output: Command output.
        pattern: Regex pattern with a single capture group for the name.

    Returns:
        Set of names (lowercase).
    """
    compiled = re.compile(pattern)
    return {
        match.group(1).casefold()
        for line in output.split("\n")
        if (match := compiled.match(line))
    }


def _parse_codec_list(output: str) -> set[str]:
    """Parse ffmpeg -encoders or -decoders output."""
    # Format: " VFXSBD codec_name    Description..."
    return _parse_ffmpeg_list(output, r"\s+[VASFXBDI.]{6}\s+(\S+)")


def _parse_format_list(output: str) -> set[str]:
    """Parse ffmpeg -muxers or -demuxers output."""
    # Format: " DE format_name    Description..."
    return _parse_ffmpeg_list(output, r"\s+[DE .]{2}\s+(\S+)")


def _parse_filter_list(output: str) -> set[str]:
    """Parse ffmpeg -filters output."""
    # Format: " TSC filter_name     type->type     Description..."
    return _parse_ffmpeg_list(output, r"\s+[TSC.]{3}\s+(\S+)")


def detect_ffprobe(configured_path: Path | None = None) -> FFprobeInfo:
    """Detect ffprobe and get version.

    Args:
        configured_path: Optional configured path to ffprobe.

    Returns:
        FFprobeInfo with version information.
    """
    result = _detect_tool_generic(FFPROBE_CONFIG, configured_path)
    assert isinstance(result, FFprobeInfo)
    return result


def detect_mkvmerge(configured_path: Path | None = None) -> MkvmergeInfo:
    """Detect mkvmerge and get version.

    Args:
        configured_path: Optional configured path to mkvmerge.

    Returns:
        MkvmergeInfo with version information.
    """
    result = _detect_tool_generic(MKVMERGE_CONFIG, configured_path)
    assert isinstance(result, MkvmergeInfo)
    return result


def detect_mkvpropedit(configured_path: Path | None = None) -> MkvpropeditInfo:
    """Detect mkvpropedit and get version.

    Args:
        configured_path: Optional configured path to mkvpropedit.

    Returns:
        MkvpropeditInfo with version information.
    """
    result = _detect_tool_generic(MKVPROPEDIT_CONFIG, configured_path)
    assert isinstance(result, MkvpropeditInfo)
    return result


def detect_all_tools(
    ffmpeg_path: Path | None = None,
    ffprobe_path: Path | None = None,
    mkvmerge_path: Path | None = None,
    mkvpropedit_path: Path | None = None,
) -> ToolRegistry:
    """Detect all external tools and build a registry.

    Args:
        ffmpeg_path: Optional configured path to ffmpeg.
        ffprobe_path: Optional configured path to ffprobe.
        mkvmerge_path: Optional configured path to mkvmerge.
        mkvpropedit_path: Optional configured path to mkvpropedit.

    Returns:
        ToolRegistry with all detected tools.
    """
    registry = ToolRegistry(
        ffmpeg=detect_ffmpeg(ffmpeg_path),
        ffprobe=detect_ffprobe(ffprobe_path),
        mkvmerge=detect_mkvmerge(mkvmerge_path),
        mkvpropedit=detect_mkvpropedit(mkvpropedit_path),
        detected_at=datetime.now(timezone.utc),
    )
    return registry
