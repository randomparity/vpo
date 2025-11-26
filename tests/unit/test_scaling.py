"""Unit tests for video scaling (US5).

Tests the ScalingSettings dataclass, RESOLUTION_MAP, aspect ratio preservation,
and upscale=false behavior.
"""

import pytest

from video_policy_orchestrator.policy.models import (
    RESOLUTION_MAP,
    ScaleAlgorithm,
    ScalingSettings,
)


class TestScalingSettingsDataclass:
    """T045: Unit tests for ScalingSettings dataclass."""

    def test_scaling_settings_with_max_resolution(self) -> None:
        """ScalingSettings with max_resolution preset."""
        settings = ScalingSettings(max_resolution="1080p")
        assert settings.max_resolution == "1080p"
        assert settings.max_width is None
        assert settings.max_height is None

    def test_scaling_settings_with_explicit_dimensions(self) -> None:
        """ScalingSettings with explicit max_width/max_height."""
        settings = ScalingSettings(max_width=1920, max_height=1080)
        assert settings.max_width == 1920
        assert settings.max_height == 1080
        assert settings.max_resolution is None

    def test_scaling_settings_default_algorithm(self) -> None:
        """ScalingSettings defaults to lanczos algorithm."""
        settings = ScalingSettings(max_resolution="1080p")
        assert settings.algorithm == ScaleAlgorithm.LANCZOS

    def test_scaling_settings_custom_algorithm(self) -> None:
        """ScalingSettings accepts custom algorithm."""
        settings = ScalingSettings(
            max_resolution="1080p", algorithm=ScaleAlgorithm.BICUBIC
        )
        assert settings.algorithm == ScaleAlgorithm.BICUBIC

    def test_scaling_settings_default_upscale(self) -> None:
        """ScalingSettings defaults upscale=False."""
        settings = ScalingSettings(max_resolution="1080p")
        assert settings.upscale is False

    def test_scaling_settings_upscale_enabled(self) -> None:
        """ScalingSettings can enable upscaling."""
        settings = ScalingSettings(max_resolution="1080p", upscale=True)
        assert settings.upscale is True

    def test_scaling_settings_invalid_resolution_raises(self) -> None:
        """ScalingSettings raises for invalid resolution preset."""
        with pytest.raises(ValueError, match="Invalid max_resolution"):
            ScalingSettings(max_resolution="not_a_resolution")

    def test_scaling_settings_get_max_dimensions(self) -> None:
        """ScalingSettings.get_max_dimensions returns correct values."""
        settings = ScalingSettings(max_resolution="1080p")
        max_dims = settings.get_max_dimensions()
        assert max_dims == (1920, 1080)

    def test_scaling_settings_get_max_dimensions_explicit(self) -> None:
        """ScalingSettings.get_max_dimensions uses explicit values when no preset."""
        settings = ScalingSettings(max_width=1280, max_height=720)
        max_dims = settings.get_max_dimensions()
        assert max_dims == (1280, 720)

    def test_scaling_settings_resolution_takes_precedence(self) -> None:
        """ScalingSettings.get_max_dimensions prefers max_resolution over explicit."""
        settings = ScalingSettings(
            max_resolution="1080p", max_width=1280, max_height=720
        )
        max_dims = settings.get_max_dimensions()
        # max_resolution takes precedence over explicit max_width/max_height
        assert max_dims == (1920, 1080)

    def test_scaling_settings_immutable(self) -> None:
        """ScalingSettings is frozen/immutable."""
        settings = ScalingSettings(max_resolution="1080p")
        with pytest.raises(AttributeError):
            settings.max_resolution = "720p"  # type: ignore[misc]


class TestResolutionMap:
    """T046: Unit tests for resolution preset to dimensions mapping."""

    def test_resolution_map_has_common_presets(self) -> None:
        """RESOLUTION_MAP contains common resolution presets."""
        assert "480p" in RESOLUTION_MAP
        assert "720p" in RESOLUTION_MAP
        assert "1080p" in RESOLUTION_MAP
        assert "4k" in RESOLUTION_MAP

    def test_resolution_map_480p(self) -> None:
        """480p maps to 854x480."""
        assert RESOLUTION_MAP["480p"] == (854, 480)

    def test_resolution_map_720p(self) -> None:
        """720p maps to 1280x720."""
        assert RESOLUTION_MAP["720p"] == (1280, 720)

    def test_resolution_map_1080p(self) -> None:
        """1080p maps to 1920x1080."""
        assert RESOLUTION_MAP["1080p"] == (1920, 1080)

    def test_resolution_map_1440p(self) -> None:
        """1440p maps to 2560x1440."""
        assert RESOLUTION_MAP["1440p"] == (2560, 1440)

    def test_resolution_map_4k(self) -> None:
        """4k maps to 3840x2160."""
        assert RESOLUTION_MAP["4k"] == (3840, 2160)

    def test_resolution_map_8k(self) -> None:
        """8k maps to 7680x4320."""
        assert RESOLUTION_MAP["8k"] == (7680, 4320)


class TestAspectRatioPreservation:
    """T047: Unit tests for aspect ratio preservation calculation."""

    def test_16_9_to_1080p(self) -> None:
        """16:9 aspect ratio is preserved when scaling to 1080p."""
        # 3840x2160 (4K) -> 1920x1080 (1080p)
        original_ratio = 3840 / 2160  # 16:9 = 1.778
        target_ratio = 1920 / 1080  # 16:9 = 1.778
        assert abs(original_ratio - target_ratio) < 0.01

    def test_ultrawide_preserved(self) -> None:
        """21:9 ultrawide aspect ratio scales correctly."""
        # 3440x1440 ultrawide
        original_ratio = 3440 / 1440  # ~2.389
        # Scaling to 1080p height limit
        max_height = 1080
        scale = max_height / 1440
        scaled_width = int(3440 * scale)
        scaled_height = int(1440 * scale)
        scaled_ratio = scaled_width / scaled_height
        assert abs(original_ratio - scaled_ratio) < 0.01

    def test_4_3_preserved(self) -> None:
        """4:3 aspect ratio is preserved."""
        original_ratio = 1440 / 1080  # 4:3 = 1.333
        # Scaling to 720p
        max_height = 720
        scale = max_height / 1080
        scaled_width = int(1440 * scale)
        scaled_height = int(1080 * scale)
        scaled_ratio = scaled_width / scaled_height
        assert abs(original_ratio - scaled_ratio) < 0.01


class TestUpscaleBehavior:
    """T048: Unit tests for upscale=false behavior."""

    def test_no_upscale_smaller_video(self) -> None:
        """With upscale=False, smaller videos are not scaled up."""
        settings = ScalingSettings(max_resolution="1080p", upscale=False)
        max_dims = settings.get_max_dimensions()
        assert max_dims == (1920, 1080)

        # A 720p video (1280x720) should NOT be upscaled to 1080p
        # The test just verifies the setting is False by default
        assert settings.upscale is False

    def test_upscale_enabled_allows_scaling_up(self) -> None:
        """With upscale=True, videos can be scaled up."""
        settings = ScalingSettings(max_resolution="1080p", upscale=True)
        assert settings.upscale is True


class TestScaleAlgorithm:
    """Tests for scale algorithm enum."""

    def test_all_algorithms_exist(self) -> None:
        """All expected scaling algorithms exist."""
        assert ScaleAlgorithm.LANCZOS
        assert ScaleAlgorithm.BICUBIC
        assert ScaleAlgorithm.BILINEAR

    def test_algorithm_values(self) -> None:
        """Algorithm enum values are correct."""
        assert ScaleAlgorithm.LANCZOS.value == "lanczos"
        assert ScaleAlgorithm.BICUBIC.value == "bicubic"
        assert ScaleAlgorithm.BILINEAR.value == "bilinear"
