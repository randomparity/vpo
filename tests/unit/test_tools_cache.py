"""Unit tests for tool capability caching."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vpo.tools.cache import (
    ToolCapabilityCache,
    _datetime_to_iso,
    _iso_to_datetime,
    deserialize_registry,
    serialize_registry,
)
from vpo.tools.models import (
    FFmpegCapabilities,
    FFmpegInfo,
    FFprobeInfo,
    MkvmergeInfo,
    MkvpropeditInfo,
    ToolRegistry,
    ToolStatus,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_registry() -> ToolRegistry:
    """Create a sample tool registry for testing."""
    now = datetime.now(timezone.utc)

    ffmpeg = FFmpegInfo()
    ffmpeg.path = Path("/usr/bin/ffmpeg")
    ffmpeg.version = "6.1.1"
    ffmpeg.version_tuple = (6, 1, 1)
    ffmpeg.status = ToolStatus.AVAILABLE
    ffmpeg.detected_at = now
    ffmpeg.capabilities = FFmpegCapabilities(
        configuration="--enable-gpl --enable-libx264",
        build_flags=["gpl", "libx264"],
        is_gpl=True,
        is_nonfree=False,
        encoders={"libx264", "aac"},
        decoders={"h264", "hevc"},
        muxers={"mp4", "matroska"},
        demuxers={"mov", "matroska"},
        filters={"scale", "overlay"},
    )

    ffprobe = FFprobeInfo()
    ffprobe.path = Path("/usr/bin/ffprobe")
    ffprobe.version = "6.1.1"
    ffprobe.version_tuple = (6, 1, 1)
    ffprobe.status = ToolStatus.AVAILABLE
    ffprobe.detected_at = now

    mkvmerge = MkvmergeInfo()
    mkvmerge.path = Path("/usr/bin/mkvmerge")
    mkvmerge.version = "81.0"
    mkvmerge.version_tuple = (81, 0)
    mkvmerge.status = ToolStatus.AVAILABLE
    mkvmerge.detected_at = now
    mkvmerge.supports_track_order = True
    mkvmerge.supports_json_output = True

    mkvpropedit = MkvpropeditInfo()
    mkvpropedit.path = Path("/usr/bin/mkvpropedit")
    mkvpropedit.version = "81.0"
    mkvpropedit.version_tuple = (81, 0)
    mkvpropedit.status = ToolStatus.AVAILABLE
    mkvpropedit.detected_at = now
    mkvpropedit.supports_track_edit = True
    mkvpropedit.supports_add_attachment = True

    return ToolRegistry(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        mkvmerge=mkvmerge,
        mkvpropedit=mkvpropedit,
        detected_at=now,
        cache_valid_until=now + timedelta(hours=24),
    )


# =============================================================================
# DateTime Conversion Tests
# =============================================================================


class TestDateTimeConversion:
    """Tests for datetime/ISO conversion."""

    def test_datetime_to_iso(self):
        """datetime should be converted to ISO string."""
        dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = _datetime_to_iso(dt)
        assert "2024-01-15" in result
        assert "12:30:45" in result

    def test_datetime_to_iso_none(self):
        """None should return None."""
        assert _datetime_to_iso(None) is None

    def test_iso_to_datetime(self):
        """ISO string should be converted to datetime."""
        iso = "2024-01-15T12:30:45+00:00"
        result = _iso_to_datetime(iso)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_to_datetime_none(self):
        """None should return None."""
        assert _iso_to_datetime(None) is None

    def test_iso_to_datetime_invalid(self):
        """Invalid string should return None."""
        assert _iso_to_datetime("not-a-date") is None

    def test_roundtrip(self):
        """Roundtrip conversion should preserve datetime."""
        original = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        iso = _datetime_to_iso(original)
        restored = _iso_to_datetime(iso)
        assert restored == original


# =============================================================================
# Serialization Tests
# =============================================================================


class TestRegistrySerialization:
    """Tests for registry serialization."""

    def test_serialize_basic(self, sample_registry: ToolRegistry):
        """Registry should serialize to dict."""
        data = serialize_registry(sample_registry)

        assert data["version"] == 1
        assert "detected_at" in data
        assert "ffmpeg" in data
        assert "ffprobe" in data
        assert "mkvmerge" in data
        assert "mkvpropedit" in data

    def test_serialize_ffmpeg_capabilities(self, sample_registry: ToolRegistry):
        """FFmpeg capabilities should be serialized."""
        data = serialize_registry(sample_registry)
        ffmpeg_data = data["ffmpeg"]

        assert "capabilities" in ffmpeg_data
        caps = ffmpeg_data["capabilities"]
        assert caps["is_gpl"] is True
        assert "libx264" in caps["encoders"]
        assert "h264" in caps["decoders"]

    def test_serialize_mkvmerge_features(self, sample_registry: ToolRegistry):
        """MKVmerge features should be serialized."""
        data = serialize_registry(sample_registry)
        mkvmerge_data = data["mkvmerge"]

        assert mkvmerge_data["supports_track_order"] is True
        assert mkvmerge_data["supports_json_output"] is True

    def test_serialize_to_json(self, sample_registry: ToolRegistry):
        """Serialized registry should be JSON-encodable."""
        data = serialize_registry(sample_registry)
        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)


class TestRegistryDeserialization:
    """Tests for registry deserialization."""

    def test_deserialize_basic(self, sample_registry: ToolRegistry):
        """Serialized registry should deserialize correctly."""
        data = serialize_registry(sample_registry)
        restored = deserialize_registry(data)

        assert restored.ffmpeg.version == "6.1.1"
        assert restored.ffprobe.version == "6.1.1"
        assert restored.mkvmerge.version == "81.0"
        assert restored.mkvpropedit.version == "81.0"

    def test_deserialize_paths(self, sample_registry: ToolRegistry):
        """Paths should be deserialized as Path objects."""
        data = serialize_registry(sample_registry)
        restored = deserialize_registry(data)

        assert isinstance(restored.ffmpeg.path, Path)
        assert restored.ffmpeg.path == Path("/usr/bin/ffmpeg")

    def test_deserialize_ffmpeg_capabilities(self, sample_registry: ToolRegistry):
        """FFmpeg capabilities should be deserialized."""
        data = serialize_registry(sample_registry)
        restored = deserialize_registry(data)

        caps = restored.ffmpeg.capabilities
        assert caps.is_gpl is True
        assert "libx264" in caps.encoders
        assert isinstance(caps.encoders, set)

    def test_deserialize_version_tuple(self, sample_registry: ToolRegistry):
        """Version tuples should be deserialized correctly."""
        data = serialize_registry(sample_registry)
        restored = deserialize_registry(data)

        assert restored.ffmpeg.version_tuple == (6, 1, 1)
        assert isinstance(restored.ffmpeg.version_tuple, tuple)

    def test_deserialize_wrong_version_raises(self):
        """Wrong schema version should raise ValueError."""
        data = {"version": 999}
        with pytest.raises(ValueError, match="Unsupported cache schema version"):
            deserialize_registry(data)

    def test_roundtrip_preservation(self, sample_registry: ToolRegistry):
        """Roundtrip should preserve all data."""
        data = serialize_registry(sample_registry)
        restored = deserialize_registry(data)

        assert restored.ffmpeg.status == sample_registry.ffmpeg.status
        assert (
            restored.mkvmerge.supports_track_order
            == sample_registry.mkvmerge.supports_track_order
        )


# =============================================================================
# Cache Class Tests
# =============================================================================


class TestToolCapabilityCache:
    """Tests for ToolCapabilityCache class."""

    def test_load_nonexistent_returns_none(self, tmp_path: Path):
        """Loading from nonexistent file should return None."""
        cache = ToolCapabilityCache(cache_path=tmp_path / "nonexistent.json")
        result = cache.load()
        assert result is None

    def test_save_and_load(self, tmp_path: Path, sample_registry: ToolRegistry):
        """Saved registry should be loadable."""
        cache_path = tmp_path / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path)

        cache.save(sample_registry)
        assert cache_path.exists()

        loaded = cache.load()
        assert loaded is not None
        assert loaded.ffmpeg.version == "6.1.1"

    def test_save_creates_parent_dirs(
        self, tmp_path: Path, sample_registry: ToolRegistry
    ):
        """Save should create parent directories."""
        cache_path = tmp_path / "nested" / "dir" / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path)

        cache.save(sample_registry)
        assert cache_path.exists()

    def test_load_expired_returns_none(
        self, tmp_path: Path, sample_registry: ToolRegistry
    ):
        """Loading expired cache should return None."""
        cache_path = tmp_path / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path, ttl_hours=1)

        # Set cache validity to the past
        sample_registry.cache_valid_until = datetime.now(timezone.utc) - timedelta(
            hours=2
        )

        data = serialize_registry(sample_registry)
        with open(cache_path, "w") as f:
            json.dump(data, f)

        loaded = cache.load()
        assert loaded is None

    def test_load_valid_cache(self, tmp_path: Path, sample_registry: ToolRegistry):
        """Loading valid cache should return registry."""
        cache_path = tmp_path / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path, ttl_hours=24)

        # Set cache validity to the future
        sample_registry.cache_valid_until = datetime.now(timezone.utc) + timedelta(
            hours=12
        )

        data = serialize_registry(sample_registry)
        with open(cache_path, "w") as f:
            json.dump(data, f)

        loaded = cache.load()
        assert loaded is not None

    def test_invalidate_removes_file(
        self, tmp_path: Path, sample_registry: ToolRegistry
    ):
        """Invalidate should remove cache file."""
        cache_path = tmp_path / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path)

        cache.save(sample_registry)
        assert cache_path.exists()

        cache.invalidate()
        assert not cache_path.exists()

    def test_invalidate_nonexistent_is_safe(self, tmp_path: Path):
        """Invalidating nonexistent cache should not raise."""
        cache = ToolCapabilityCache(cache_path=tmp_path / "nonexistent.json")
        # Should not raise
        cache.invalidate()

    def test_is_valid_returns_true_for_valid_cache(
        self, tmp_path: Path, sample_registry: ToolRegistry
    ):
        """is_valid should return True for valid cache."""
        cache_path = tmp_path / "cache.json"
        cache = ToolCapabilityCache(cache_path=cache_path, ttl_hours=24)

        cache.save(sample_registry)
        assert cache.is_valid() is True

    def test_is_valid_returns_false_for_missing(self, tmp_path: Path):
        """is_valid should return False for missing cache."""
        cache = ToolCapabilityCache(cache_path=tmp_path / "missing.json")
        assert cache.is_valid() is False

    def test_load_corrupted_returns_none(self, tmp_path: Path):
        """Loading corrupted JSON should return None."""
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("{ invalid json")

        cache = ToolCapabilityCache(cache_path=cache_path)
        result = cache.load()
        assert result is None
