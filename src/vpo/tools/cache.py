"""Tool capability caching.

This module provides caching for detected tool capabilities to avoid
repeated subprocess calls. Cache is stored in ~/.vpo/tool-capabilities.json.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vpo.core import parse_iso_timestamp
from vpo.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolInfo,
    ToolRegistry,
    ToolStatus,
)

logger = logging.getLogger(__name__)

# Default cache TTL: 24 hours
DEFAULT_CACHE_TTL_HOURS = 24

# Default cache location
DEFAULT_CACHE_DIR = Path.home() / ".vpo"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "tool-capabilities.json"


def _datetime_to_iso(dt: datetime | None) -> str | None:
    """Convert datetime to ISO string for JSON serialization."""
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_datetime(s: str | None) -> datetime | None:
    """Convert ISO string back to datetime."""
    if s is None:
        return None
    try:
        return parse_iso_timestamp(s)
    except (ValueError, TypeError):
        return None


def _set_base_fields(info: ToolInfo, data: dict) -> None:
    """Set common ToolInfo fields from serialized data.

    Args:
        info: ToolInfo instance to populate.
        data: Serialized data dict.
    """
    info.path = Path(data["path"]) if data.get("path") else None
    info.version = data.get("version")
    version_tuple = data.get("version_tuple")
    info.version_tuple = tuple(version_tuple) if version_tuple else None
    info.status = ToolStatus(data.get("status", "missing"))
    info.status_message = data.get("status_message")
    info.detected_at = _iso_to_datetime(data.get("detected_at"))


def _serialize_tool_info(
    info: FFmpegInfo | FFprobeInfo | MkvmergeInfo | MkvpropeditInfo,
) -> dict:
    """Serialize a tool info object to dict."""
    result = {
        "name": info.name,
        "path": str(info.path) if info.path else None,
        "version": info.version,
        "version_tuple": list(info.version_tuple) if info.version_tuple else None,
        "status": info.status.value,
        "status_message": info.status_message,
        "detected_at": _datetime_to_iso(info.detected_at),
    }

    # Add type-specific fields
    if isinstance(info, FFmpegInfo):
        caps = info.capabilities
        result["capabilities"] = {
            "configuration": caps.configuration,
            "build_flags": caps.build_flags,
            "is_gpl": caps.is_gpl,
            "is_nonfree": caps.is_nonfree,
            "encoders": list(caps.encoders),
            "decoders": list(caps.decoders),
            "muxers": list(caps.muxers),
            "demuxers": list(caps.demuxers),
            "filters": list(caps.filters),
        }
    elif isinstance(info, MkvmergeInfo):
        result["supports_track_order"] = info.supports_track_order
        result["supports_json_output"] = info.supports_json_output
    elif isinstance(info, MkvpropeditInfo):
        result["supports_track_edit"] = info.supports_track_edit
        result["supports_add_attachment"] = info.supports_add_attachment

    return result


def _deserialize_ffmpeg_info(data: dict) -> FFmpegInfo:
    """Deserialize FFmpegInfo from dict."""
    caps_data = data.get("capabilities", {})
    capabilities = FFmpegCapabilities(
        configuration=caps_data.get("configuration", ""),
        build_flags=caps_data.get("build_flags", []),
        is_gpl=caps_data.get("is_gpl", False),
        is_nonfree=caps_data.get("is_nonfree", False),
        encoders=set(caps_data.get("encoders", [])),
        decoders=set(caps_data.get("decoders", [])),
        muxers=set(caps_data.get("muxers", [])),
        demuxers=set(caps_data.get("demuxers", [])),
        filters=set(caps_data.get("filters", [])),
    )
    info = FFmpegInfo(capabilities=capabilities)
    _set_base_fields(info, data)
    return info


def _deserialize_ffprobe_info(data: dict) -> FFprobeInfo:
    """Deserialize FFprobeInfo from dict."""
    info = FFprobeInfo()
    _set_base_fields(info, data)
    return info


def _deserialize_mkvmerge_info(data: dict) -> MkvmergeInfo:
    """Deserialize MkvmergeInfo from dict."""
    info = MkvmergeInfo()
    _set_base_fields(info, data)
    info.supports_track_order = data.get("supports_track_order", True)
    info.supports_json_output = data.get("supports_json_output", True)
    return info


def _deserialize_mkvpropedit_info(data: dict) -> MkvpropeditInfo:
    """Deserialize MkvpropeditInfo from dict."""
    info = MkvpropeditInfo()
    _set_base_fields(info, data)
    info.supports_track_edit = data.get("supports_track_edit", True)
    info.supports_add_attachment = data.get("supports_add_attachment", True)
    return info


def serialize_registry(registry: ToolRegistry) -> dict:
    """Serialize a ToolRegistry to a JSON-compatible dict.

    Args:
        registry: Tool registry to serialize.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "version": 1,  # Schema version for future compatibility
        "detected_at": _datetime_to_iso(registry.detected_at),
        "cache_valid_until": _datetime_to_iso(registry.cache_valid_until),
        "ffmpeg": _serialize_tool_info(registry.ffmpeg),
        "ffprobe": _serialize_tool_info(registry.ffprobe),
        "mkvmerge": _serialize_tool_info(registry.mkvmerge),
        "mkvpropedit": _serialize_tool_info(registry.mkvpropedit),
    }


def deserialize_registry(data: dict) -> ToolRegistry:
    """Deserialize a ToolRegistry from dict.

    Args:
        data: Dict from JSON.

    Returns:
        ToolRegistry instance.

    Raises:
        ValueError: If data is invalid or wrong schema version.
    """
    version = data.get("version", 0)
    if version != 1:
        raise ValueError(f"Unsupported cache schema version: {version}")

    detected_at = _iso_to_datetime(data.get("detected_at"))
    return ToolRegistry(
        ffmpeg=_deserialize_ffmpeg_info(data.get("ffmpeg", {})),
        ffprobe=_deserialize_ffprobe_info(data.get("ffprobe", {})),
        mkvmerge=_deserialize_mkvmerge_info(data.get("mkvmerge", {})),
        mkvpropedit=_deserialize_mkvpropedit_info(data.get("mkvpropedit", {})),
        detected_at=detected_at or datetime.now(timezone.utc),
        cache_valid_until=_iso_to_datetime(data.get("cache_valid_until")),
    )


class ToolCapabilityCache:
    """Manages caching of tool capability detection results.

    The cache is stored as JSON and includes TTL for automatic invalidation.
    """

    def __init__(
        self,
        cache_path: Path | None = None,
        ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ):
        """Initialize the cache.

        Args:
            cache_path: Path to cache file. Defaults to ~/.vpo/tool-capabilities.json.
            ttl_hours: Cache TTL in hours. Defaults to 24.
        """
        self.cache_path = cache_path or DEFAULT_CACHE_FILE
        self.ttl = timedelta(hours=ttl_hours)

    def load(self) -> ToolRegistry | None:
        """Load cached tool registry if valid.

        Returns:
            ToolRegistry if cache exists and is valid, None otherwise.
        """
        if not self.cache_path.exists():
            logger.debug("Cache file does not exist: %s", self.cache_path)
            return None

        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)

            registry = deserialize_registry(data)

            # Check if cache is still valid
            if registry.cache_valid_until:
                if datetime.now(timezone.utc) > registry.cache_valid_until:
                    logger.debug("Cache expired at %s", registry.cache_valid_until)
                    return None

            logger.debug("Loaded valid cache from %s", self.cache_path)
            return registry

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Failed to load cache: %s", e)
            return None

    def save(self, registry: ToolRegistry) -> None:
        """Save tool registry to cache.

        Uses atomic write (temp file + rename) to prevent corruption
        if the process crashes mid-write.

        Args:
            registry: Tool registry to cache.
        """
        # Set cache validity
        registry.cache_valid_until = datetime.now(timezone.utc) + self.ttl

        # Ensure cache directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = serialize_registry(registry)
            json_content = json.dumps(data, indent=2)

            # Atomic write: temp file + rename
            fd, temp_path_str = tempfile.mkstemp(
                suffix=self.cache_path.suffix,
                dir=self.cache_path.parent,
                text=True,
            )
            temp_path = Path(temp_path_str)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json_content)
                temp_path.replace(self.cache_path)  # Atomic on POSIX
                logger.debug("Saved cache to %s", self.cache_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
        except OSError as e:
            logger.warning("Failed to save cache: %s", e)

    def invalidate(self) -> None:
        """Invalidate (delete) the cache."""
        if self.cache_path.exists():
            try:
                self.cache_path.unlink()
                logger.debug("Invalidated cache at %s", self.cache_path)
            except OSError as e:
                logger.warning("Failed to invalidate cache: %s", e)

    def is_valid(self) -> bool:
        """Check if cache exists and is valid.

        Returns:
            True if cache is valid, False otherwise.
        """
        return self.load() is not None


def get_tool_registry(
    force_refresh: bool = False,
    cache_path: Path | None = None,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ffmpeg_path: Path | None = None,
    ffprobe_path: Path | None = None,
    mkvmerge_path: Path | None = None,
    mkvpropedit_path: Path | None = None,
) -> ToolRegistry:
    """Get tool registry, using cache if valid.

    This is the main entry point for getting tool capabilities.
    It will use cached results if available and valid, or detect
    tools fresh if cache is missing/expired or force_refresh is True.

    Args:
        force_refresh: Force fresh detection even if cache is valid.
        cache_path: Path to cache file.
        ttl_hours: Cache TTL in hours.
        ffmpeg_path: Optional configured path to ffmpeg.
        ffprobe_path: Optional configured path to ffprobe.
        mkvmerge_path: Optional configured path to mkvmerge.
        mkvpropedit_path: Optional configured path to mkvpropedit.

    Returns:
        ToolRegistry with detected tool capabilities.
    """
    from vpo.tools.detection import detect_all_tools

    cache = ToolCapabilityCache(cache_path=cache_path, ttl_hours=ttl_hours)

    # Try loading from cache
    if not force_refresh:
        registry = cache.load()
        if registry is not None:
            # Check if configured paths match cached paths (use resolve() for symlinks)
            configured_paths = [
                (ffmpeg_path, registry.ffmpeg.path),
                (ffprobe_path, registry.ffprobe.path),
                (mkvmerge_path, registry.mkvmerge.path),
                (mkvpropedit_path, registry.mkvpropedit.path),
            ]
            paths_match = all(
                cfg is None or cached is None or cfg.resolve() == cached.resolve()
                for cfg, cached in configured_paths
            )

            if paths_match:
                return registry
            logger.debug("Configured paths changed, refreshing detection")

    # Detect fresh
    logger.debug("Detecting tools fresh")
    registry = detect_all_tools(
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        mkvmerge_path=mkvmerge_path,
        mkvpropedit_path=mkvpropedit_path,
    )

    # Save to cache
    cache.save(registry)

    return registry
