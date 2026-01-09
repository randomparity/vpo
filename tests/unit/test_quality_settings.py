"""Unit tests for V6 quality settings."""

import pytest

from vpo.policy.models import (
    QualityMode,
    QualitySettings,
    get_default_crf,
)


class TestQualitySettingsDataclass:
    """Tests for QualitySettings dataclass (T024)."""

    def test_quality_settings_crf_mode(self):
        """QualitySettings with CRF mode."""
        qs = QualitySettings(mode=QualityMode.CRF, crf=20)
        assert qs.mode == QualityMode.CRF
        assert qs.crf == 20

    def test_quality_settings_bitrate_mode(self):
        """QualitySettings with bitrate mode."""
        qs = QualitySettings(mode=QualityMode.BITRATE, bitrate="5M")
        assert qs.mode == QualityMode.BITRATE
        assert qs.bitrate == "5M"

    def test_quality_settings_constrained_quality_mode(self):
        """QualitySettings with constrained quality mode."""
        qs = QualitySettings(
            mode=QualityMode.CONSTRAINED_QUALITY,
            crf=22,
            max_bitrate="10M",
        )
        assert qs.mode == QualityMode.CONSTRAINED_QUALITY
        assert qs.crf == 22
        assert qs.max_bitrate == "10M"

    def test_quality_settings_with_preset(self):
        """QualitySettings with encoding preset."""
        qs = QualitySettings(mode=QualityMode.CRF, preset="slow")
        assert qs.preset == "slow"

    def test_quality_settings_with_tune(self):
        """QualitySettings with tune option."""
        qs = QualitySettings(mode=QualityMode.CRF, tune="film")
        assert qs.tune == "film"

    def test_quality_settings_defaults(self):
        """QualitySettings has sensible defaults."""
        qs = QualitySettings()
        assert qs.mode == QualityMode.CRF
        assert qs.crf is None
        assert qs.bitrate is None
        assert qs.preset == "medium"
        assert qs.tune is None
        assert qs.two_pass is False

    def test_quality_settings_all_fields(self):
        """QualitySettings with all fields set."""
        qs = QualitySettings(
            mode=QualityMode.CRF,
            crf=18,
            bitrate="8M",
            min_bitrate="2M",
            max_bitrate="15M",
            preset="slower",
            tune="grain",
            two_pass=True,
        )
        assert qs.crf == 18
        assert qs.bitrate == "8M"
        assert qs.min_bitrate == "2M"
        assert qs.max_bitrate == "15M"
        assert qs.preset == "slower"
        assert qs.tune == "grain"
        assert qs.two_pass is True


class TestCRFValidation:
    """Tests for CRF range validation (T025)."""

    def test_crf_zero_valid(self):
        """CRF 0 is valid (lossless for x264/x265)."""
        qs = QualitySettings(crf=0)
        assert qs.crf == 0

    def test_crf_51_valid(self):
        """CRF 51 is valid (maximum compression)."""
        qs = QualitySettings(crf=51)
        assert qs.crf == 51

    def test_crf_typical_values(self):
        """Typical CRF values are valid."""
        for crf in [18, 20, 23, 28, 30]:
            qs = QualitySettings(crf=crf)
            assert qs.crf == crf

    def test_crf_negative_invalid(self):
        """Negative CRF raises ValueError."""
        with pytest.raises(ValueError, match="Invalid crf"):
            QualitySettings(crf=-1)

    def test_crf_over_51_invalid(self):
        """CRF > 51 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid crf"):
            QualitySettings(crf=52)

    def test_crf_way_over_limit_invalid(self):
        """CRF way over limit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid crf"):
            QualitySettings(crf=100)


class TestCodecSpecificCRFDefaults:
    """Tests for codec-specific CRF defaults (T026)."""

    def test_default_crf_hevc(self):
        """Default CRF for HEVC is 28."""
        assert get_default_crf("hevc") == 28
        assert get_default_crf("HEVC") == 28
        assert get_default_crf("h265") == 28
        assert get_default_crf("x265") == 28

    def test_default_crf_h264(self):
        """Default CRF for H.264 is 23."""
        assert get_default_crf("h264") == 23
        assert get_default_crf("H264") == 23
        assert get_default_crf("x264") == 23

    def test_default_crf_vp9(self):
        """Default CRF for VP9 is 31."""
        assert get_default_crf("vp9") == 31
        assert get_default_crf("VP9") == 31

    def test_default_crf_av1(self):
        """Default CRF for AV1 is 30."""
        assert get_default_crf("av1") == 30
        assert get_default_crf("AV1") == 30

    def test_default_crf_unknown_codec(self):
        """Unknown codec gets default of 23."""
        assert get_default_crf("unknown") == 23
        assert get_default_crf("") == 23


class TestPresetValidation:
    """Tests for encoding preset validation."""

    def test_valid_presets(self):
        """All valid presets are accepted."""
        valid_presets = [
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        for preset in valid_presets:
            qs = QualitySettings(preset=preset)
            assert qs.preset == preset

    def test_invalid_preset_raises(self):
        """Invalid preset raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset"):
            QualitySettings(preset="invalid")


class TestTuneValidation:
    """Tests for tune option validation."""

    def test_valid_tunes(self):
        """All valid tune options are accepted."""
        valid_tunes = [
            "film",
            "animation",
            "grain",
            "stillimage",
            "fastdecode",
            "zerolatency",
        ]
        for tune in valid_tunes:
            qs = QualitySettings(tune=tune)
            assert qs.tune == tune

    def test_invalid_tune_raises(self):
        """Invalid tune raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tune"):
            QualitySettings(tune="invalid")

    def test_none_tune_allowed(self):
        """None tune is allowed (no tune option)."""
        qs = QualitySettings(tune=None)
        assert qs.tune is None


class TestBitrateValidation:
    """Tests for bitrate format validation."""

    def test_valid_bitrates(self):
        """Valid bitrate formats are accepted."""
        qs = QualitySettings(bitrate="5M", min_bitrate="1M", max_bitrate="10M")
        assert qs.bitrate == "5M"
        assert qs.min_bitrate == "1M"
        assert qs.max_bitrate == "10M"

    def test_bitrate_kilobits(self):
        """Bitrate in kilobits is valid."""
        qs = QualitySettings(bitrate="5000k")
        assert qs.bitrate == "5000k"

    def test_invalid_bitrate_raises(self):
        """Invalid bitrate format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bitrate"):
            QualitySettings(bitrate="invalid")


class TestModeRequirements:
    """Tests for mode-specific requirements."""

    def test_bitrate_mode_requires_bitrate(self):
        """Bitrate mode requires bitrate to be set."""
        with pytest.raises(ValueError, match="bitrate is required"):
            QualitySettings(mode=QualityMode.BITRATE)

    def test_crf_mode_allows_no_crf(self):
        """CRF mode allows no explicit CRF (uses codec default)."""
        qs = QualitySettings(mode=QualityMode.CRF)
        assert qs.crf is None

    def test_constrained_quality_allows_no_max_bitrate(self):
        """Constrained quality allows no explicit max_bitrate."""
        qs = QualitySettings(mode=QualityMode.CONSTRAINED_QUALITY, crf=22)
        assert qs.max_bitrate is None
