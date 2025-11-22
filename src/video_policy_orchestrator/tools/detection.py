"""External tool detection and version parsing.

This module provides functions to detect external tools, parse their versions,
and enumerate their capabilities (codecs, formats, filters for ffmpeg).
"""

import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from video_policy_orchestrator.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
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
    if configured_path and configured_path.exists():
        return configured_path

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
        result = subprocess.run(
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


def detect_ffmpeg(configured_path: Path | None = None) -> FFmpegInfo:
    """Detect ffmpeg and enumerate its capabilities.

    Args:
        configured_path: Optional configured path to ffmpeg.

    Returns:
        FFmpegInfo with version and capabilities.
    """
    info = FFmpegInfo()
    info.detected_at = datetime.now(timezone.utc)

    path = _find_tool("ffmpeg", configured_path)
    if not path:
        info.status = ToolStatus.MISSING
        info.status_message = "ffmpeg not found in PATH"
        return info

    info.path = path

    # Get version
    stdout, stderr, rc = _run_command([str(path), "-version"])
    if rc != 0:
        info.status = ToolStatus.ERROR
        info.status_message = f"Failed to get ffmpeg version: {stderr}"
        return info

    # Parse version from first line: "ffmpeg version 6.1.1 Copyright..."
    version_match = re.search(r"ffmpeg version (\S+)", stdout)
    if version_match:
        info.version = version_match.group(1)
        info.version_tuple = parse_version_string(info.version)
        if info.version_tuple is None:
            logger.warning(
                "Could not parse ffmpeg version '%s' into comparable tuple. "
                "Please report this format at github.com/anthropics/claude-code/issues",
                info.version,
            )

    # Parse build configuration
    capabilities = _detect_ffmpeg_capabilities(path, stdout)
    info.capabilities = capabilities

    info.status = ToolStatus.AVAILABLE
    info.status_message = None
    return info


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
    stdout, _, rc = _run_command([str(ffmpeg_path), "-encoders", "-hide_banner"])
    if rc == 0:
        caps.encoders = _parse_codec_list(stdout)

    # Detect decoders
    stdout, _, rc = _run_command([str(ffmpeg_path), "-decoders", "-hide_banner"])
    if rc == 0:
        caps.decoders = _parse_codec_list(stdout)

    # Detect muxers (output formats)
    stdout, _, rc = _run_command([str(ffmpeg_path), "-muxers", "-hide_banner"])
    if rc == 0:
        caps.muxers = _parse_format_list(stdout)

    # Detect demuxers (input formats)
    stdout, _, rc = _run_command([str(ffmpeg_path), "-demuxers", "-hide_banner"])
    if rc == 0:
        caps.demuxers = _parse_format_list(stdout)

    # Detect filters
    stdout, _, rc = _run_command([str(ffmpeg_path), "-filters", "-hide_banner"])
    if rc == 0:
        caps.filters = _parse_filter_list(stdout)

    return caps


def _parse_codec_list(output: str) -> set[str]:
    """Parse ffmpeg -encoders or -decoders output.

    Format: " VFXSBD codec_name    Description..."
    Where V=video, A=audio, S=subtitle, F=frame, X=experimental, etc.

    Args:
        output: Command output.

    Returns:
        Set of codec names (lowercase).
    """
    codecs = set()
    for line in output.split("\n"):
        # Skip header lines (look for lines starting with space + flags)
        match = re.match(r"\s+[VASFXBDI.]{6}\s+(\S+)", line)
        if match:
            codecs.add(match.group(1).lower())
    return codecs


def _parse_format_list(output: str) -> set[str]:
    """Parse ffmpeg -muxers or -demuxers output.

    Format: " DE format_name    Description..."
    Where D=demuxing, E=muxing.

    Args:
        output: Command output.

    Returns:
        Set of format names (lowercase).
    """
    formats = set()
    for line in output.split("\n"):
        # Skip header lines
        match = re.match(r"\s+[DE .]{2}\s+(\S+)", line)
        if match:
            formats.add(match.group(1).lower())
    return formats


def _parse_filter_list(output: str) -> set[str]:
    """Parse ffmpeg -filters output.

    Format: " TSC filter_name     type->type     Description..."

    Args:
        output: Command output.

    Returns:
        Set of filter names (lowercase).
    """
    filters = set()
    for line in output.split("\n"):
        # Skip header lines
        match = re.match(r"\s+[TSC.]{3}\s+(\S+)", line)
        if match:
            filters.add(match.group(1).lower())
    return filters


def detect_ffprobe(configured_path: Path | None = None) -> FFprobeInfo:
    """Detect ffprobe and get version.

    Args:
        configured_path: Optional configured path to ffprobe.

    Returns:
        FFprobeInfo with version information.
    """
    info = FFprobeInfo()
    info.detected_at = datetime.now(timezone.utc)

    path = _find_tool("ffprobe", configured_path)
    if not path:
        info.status = ToolStatus.MISSING
        info.status_message = "ffprobe not found in PATH"
        return info

    info.path = path

    # Get version
    stdout, stderr, rc = _run_command([str(path), "-version"])
    if rc != 0:
        info.status = ToolStatus.ERROR
        info.status_message = f"Failed to get ffprobe version: {stderr}"
        return info

    # Parse version: "ffprobe version 6.1.1 Copyright..."
    version_match = re.search(r"ffprobe version (\S+)", stdout)
    if version_match:
        info.version = version_match.group(1)
        info.version_tuple = parse_version_string(info.version)
        if info.version_tuple is None:
            logger.warning(
                "Could not parse ffprobe version '%s' into comparable tuple",
                info.version,
            )

    info.status = ToolStatus.AVAILABLE
    info.status_message = None
    return info


def detect_mkvmerge(configured_path: Path | None = None) -> MkvmergeInfo:
    """Detect mkvmerge and get version.

    Args:
        configured_path: Optional configured path to mkvmerge.

    Returns:
        MkvmergeInfo with version information.
    """
    info = MkvmergeInfo()
    info.detected_at = datetime.now(timezone.utc)

    path = _find_tool("mkvmerge", configured_path)
    if not path:
        info.status = ToolStatus.MISSING
        info.status_message = "mkvmerge not found in PATH"
        return info

    info.path = path

    # Get version: mkvmerge outputs to stdout with --version
    stdout, stderr, rc = _run_command([str(path), "--version"])
    if rc != 0:
        info.status = ToolStatus.ERROR
        info.status_message = f"Failed to get mkvmerge version: {stderr}"
        return info

    # Parse version: "mkvmerge v81.0 ('A Tattered Line of String') 64-bit"
    version_match = re.search(r"mkvmerge v(\S+)", stdout)
    if version_match:
        info.version = version_match.group(1)
        info.version_tuple = parse_version_string(info.version)
        if info.version_tuple is None:
            logger.warning(
                "Could not parse mkvmerge version '%s' into comparable tuple",
                info.version,
            )

    # Check for specific features based on version
    if info.version_tuple:
        # --track-order has been available for a very long time
        info.supports_track_order = True
        # -J (JSON output) added in mkvtoolnix 9.0
        info.supports_json_output = info.version_tuple >= (9, 0)

    info.status = ToolStatus.AVAILABLE
    info.status_message = None
    return info


def detect_mkvpropedit(configured_path: Path | None = None) -> MkvpropeditInfo:
    """Detect mkvpropedit and get version.

    Args:
        configured_path: Optional configured path to mkvpropedit.

    Returns:
        MkvpropeditInfo with version information.
    """
    info = MkvpropeditInfo()
    info.detected_at = datetime.now(timezone.utc)

    path = _find_tool("mkvpropedit", configured_path)
    if not path:
        info.status = ToolStatus.MISSING
        info.status_message = "mkvpropedit not found in PATH"
        return info

    info.path = path

    # Get version
    stdout, stderr, rc = _run_command([str(path), "--version"])
    if rc != 0:
        info.status = ToolStatus.ERROR
        info.status_message = f"Failed to get mkvpropedit version: {stderr}"
        return info

    # Parse version: "mkvpropedit v81.0 ('A Tattered Line of String') 64-bit"
    version_match = re.search(r"mkvpropedit v(\S+)", stdout)
    if version_match:
        info.version = version_match.group(1)
        info.version_tuple = parse_version_string(info.version)
        if info.version_tuple is None:
            logger.warning(
                "Could not parse mkvpropedit version '%s' into comparable tuple",
                info.version,
            )

    # All modern versions support these features
    info.supports_track_edit = True
    info.supports_add_attachment = True

    info.status = ToolStatus.AVAILABLE
    info.status_message = None
    return info


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
