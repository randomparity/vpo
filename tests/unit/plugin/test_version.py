"""Unit tests for plugin API version handling."""

import pytest

from video_policy_orchestrator.plugin.version import (
    PLUGIN_API_VERSION,
    APIVersion,
    is_compatible,
)


class TestAPIVersionParsing:
    """Tests for APIVersion.parse() method."""

    def test_parse_standard_semver(self):
        """Parse standard semver format."""
        version = APIVersion.parse("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_parse_with_prerelease(self):
        """Parse version with prerelease suffix."""
        version = APIVersion.parse("2.0.0-beta")
        assert version.major == 2
        assert version.minor == 0
        assert version.patch == 0

    def test_parse_with_whitespace(self):
        """Parse version with surrounding whitespace."""
        version = APIVersion.parse("  1.0.0  ")
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0

    def test_parse_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid version string"):
            APIVersion.parse("1.0")

    def test_parse_non_numeric_raises(self):
        """Non-numeric version should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid version string"):
            APIVersion.parse("a.b.c")

    def test_parse_empty_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid version string"):
            APIVersion.parse("")


class TestAPIVersionComparison:
    """Tests for APIVersion comparison operators."""

    def test_equal_versions(self):
        """Equal versions should compare equal."""
        v1 = APIVersion(1, 2, 3)
        v2 = APIVersion(1, 2, 3)
        assert v1 == v2

    def test_less_than_major(self):
        """Lower major version should be less than."""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)
        assert v1 < v2
        assert not v2 < v1

    def test_less_than_minor(self):
        """Lower minor version should be less than."""
        v1 = APIVersion(1, 1, 0)
        v2 = APIVersion(1, 2, 0)
        assert v1 < v2

    def test_less_than_patch(self):
        """Lower patch version should be less than."""
        v1 = APIVersion(1, 0, 1)
        v2 = APIVersion(1, 0, 2)
        assert v1 < v2

    def test_less_than_or_equal(self):
        """Less than or equal should work correctly."""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(1, 0, 0)
        v3 = APIVersion(2, 0, 0)
        assert v1 <= v2
        assert v1 <= v3

    def test_greater_than(self):
        """Greater than should work correctly."""
        v1 = APIVersion(2, 0, 0)
        v2 = APIVersion(1, 9, 9)
        assert v1 > v2

    def test_greater_than_or_equal(self):
        """Greater than or equal should work correctly."""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(1, 0, 0)
        v3 = APIVersion(0, 9, 9)
        assert v1 >= v2
        assert v1 >= v3


class TestAPIVersionString:
    """Tests for APIVersion string representation."""

    def test_str_representation(self):
        """String representation should be semver format."""
        version = APIVersion(1, 2, 3)
        assert str(version) == "1.2.3"

    def test_roundtrip(self):
        """Parse and str should roundtrip."""
        original = "1.2.3"
        version = APIVersion.parse(original)
        assert str(version) == original


class TestAPIVersionCurrent:
    """Tests for APIVersion.current() method."""

    def test_current_returns_plugin_api_version(self):
        """current() should return the PLUGIN_API_VERSION."""
        current = APIVersion.current()
        assert str(current) == PLUGIN_API_VERSION


class TestIsCompatible:
    """Tests for is_compatible() function."""

    def test_compatible_when_in_range(self):
        """Should be compatible when core is in plugin range."""
        assert is_compatible("1.0.0", "1.99.99", "1.5.0")

    def test_compatible_at_min_boundary(self):
        """Should be compatible at minimum boundary."""
        assert is_compatible("1.0.0", "2.0.0", "1.0.0")

    def test_compatible_at_max_boundary(self):
        """Should be compatible at maximum boundary."""
        assert is_compatible("1.0.0", "2.0.0", "2.0.0")

    def test_incompatible_below_min(self):
        """Should be incompatible below minimum."""
        assert not is_compatible("1.0.0", "2.0.0", "0.9.9")

    def test_incompatible_above_max(self):
        """Should be incompatible above maximum."""
        assert not is_compatible("1.0.0", "2.0.0", "2.0.1")

    def test_uses_current_version_by_default(self):
        """Should use PLUGIN_API_VERSION when no core version specified."""
        # Current version is 1.0.0, so this should be compatible
        assert is_compatible("1.0.0", "1.99.99")

    def test_accepts_apiversion_objects(self):
        """Should accept APIVersion objects as well as strings."""
        min_ver = APIVersion(1, 0, 0)
        max_ver = APIVersion(2, 0, 0)
        core = APIVersion(1, 5, 0)
        assert is_compatible(min_ver, max_ver, core)
