"""Unit tests for channel downmix filter generation."""

import pytest

from video_policy_orchestrator.policy.synthesis.downmix import (
    get_channel_count,
    get_downmix_filter,
    get_output_layout,
    normalize_channel_layout,
    validate_downmix,
)


class TestNormalizeChannelLayout:
    """Tests for normalize_channel_layout function."""

    def test_stereo_variants(self):
        """Test normalization of stereo layout variants."""
        assert normalize_channel_layout("stereo") == "stereo"
        assert normalize_channel_layout("2.0") == "stereo"
        assert normalize_channel_layout("2") == "stereo"

    def test_51_variants(self):
        """Test normalization of 5.1 layout variants."""
        assert normalize_channel_layout("5.1") == "5.1"
        assert normalize_channel_layout("5.1(side)") == "5.1"
        assert normalize_channel_layout("5.1(back)") == "5.1"
        assert normalize_channel_layout("5point1") == "5.1"
        assert normalize_channel_layout("6") == "5.1"

    def test_71_variants(self):
        """Test normalization of 7.1 layout variants."""
        assert normalize_channel_layout("7.1") == "7.1"
        assert normalize_channel_layout("7.1(wide)") == "7.1"
        assert normalize_channel_layout("7.1(side)") == "7.1"
        assert normalize_channel_layout("7point1") == "7.1"
        assert normalize_channel_layout("8") == "7.1"

    def test_mono(self):
        """Test normalization of mono layout."""
        assert normalize_channel_layout("mono") == "mono"
        assert normalize_channel_layout("1.0") == "mono"
        assert normalize_channel_layout("1") == "mono"

    def test_none_input(self):
        """Test that None input returns None."""
        assert normalize_channel_layout(None) is None

    def test_case_insensitive(self):
        """Test that layout matching is case-insensitive."""
        assert normalize_channel_layout("STEREO") == "stereo"
        assert normalize_channel_layout("Mono") == "mono"


class TestGetChannelCount:
    """Tests for get_channel_count function."""

    def test_explicit_count_takes_priority(self):
        """Test that explicit channel count overrides layout."""
        assert get_channel_count("stereo", channels=6) == 6
        assert get_channel_count("5.1", channels=2) == 2

    def test_layout_to_count(self):
        """Test channel count from layout strings."""
        assert get_channel_count("mono") == 1
        assert get_channel_count("stereo") == 2
        assert get_channel_count("5.1") == 6
        assert get_channel_count("7.1") == 8

    def test_normalized_layouts(self):
        """Test channel count from variant layouts."""
        assert get_channel_count("5.1(side)") == 6
        assert get_channel_count("7.1(wide)") == 8

    def test_none_layout(self):
        """Test that None layout returns None when no explicit count."""
        assert get_channel_count(None) is None


class TestGetDownmixFilter:
    """Tests for get_downmix_filter function."""

    def test_same_channels_returns_none(self):
        """Test that no filter is needed for same channel count."""
        assert get_downmix_filter(6, 6) is None
        assert get_downmix_filter(2, 2) is None

    def test_71_to_51(self):
        """Test 7.1 to 5.1 downmix filter."""
        filter_str = get_downmix_filter(8, 6)
        assert filter_str is not None
        assert "pan=5.1" in filter_str
        assert "FL=FL" in filter_str
        assert "LFE=LFE" in filter_str

    def test_51_to_stereo(self):
        """Test 5.1 to stereo downmix filter."""
        filter_str = get_downmix_filter(6, 2)
        assert filter_str is not None
        assert "pan=stereo" in filter_str
        # Should include LFE in the mix
        assert "LFE" in filter_str

    def test_51_to_mono(self):
        """Test 5.1 to mono downmix filter."""
        filter_str = get_downmix_filter(6, 1)
        assert filter_str is not None
        assert "pan=mono" in filter_str

    def test_stereo_to_mono(self):
        """Test stereo to mono downmix filter."""
        filter_str = get_downmix_filter(2, 1)
        assert filter_str is not None
        assert "pan=mono" in filter_str
        assert "FL" in filter_str
        assert "FR" in filter_str

    def test_71_to_stereo(self):
        """Test 7.1 to stereo downmix filter."""
        filter_str = get_downmix_filter(8, 2)
        assert filter_str is not None
        assert "pan=stereo" in filter_str
        assert "LFE" in filter_str

    def test_upmix_raises_error(self):
        """Test that attempting to upmix raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_downmix_filter(2, 6)
        assert "Cannot upmix" in str(exc_info.value)


class TestValidateDownmix:
    """Tests for validate_downmix function."""

    def test_valid_downmix(self):
        """Test that valid downmix is validated."""
        is_valid, message = validate_downmix(6, 2)
        assert is_valid is True
        assert message == ""

    def test_same_channels_valid(self):
        """Test that same channel count is valid."""
        is_valid, message = validate_downmix(6, 6)
        assert is_valid is True

    def test_upmix_invalid(self):
        """Test that upmix is invalid."""
        is_valid, message = validate_downmix(2, 6)
        assert is_valid is False
        assert "upmix" in message.lower()

    def test_zero_target_invalid(self):
        """Test that zero target channels is invalid."""
        is_valid, message = validate_downmix(6, 0)
        assert is_valid is False

    def test_too_many_source_channels(self):
        """Test that too many source channels is invalid."""
        is_valid, message = validate_downmix(16, 2)
        assert is_valid is False


class TestGetOutputLayout:
    """Tests for get_output_layout function."""

    def test_mono(self):
        """Test mono layout output."""
        assert get_output_layout(1) == "mono"

    def test_stereo(self):
        """Test stereo layout output."""
        assert get_output_layout(2) == "stereo"

    def test_51(self):
        """Test 5.1 layout output."""
        assert get_output_layout(6) == "5.1"

    def test_71(self):
        """Test 7.1 layout output."""
        assert get_output_layout(8) == "7.1"

    def test_non_standard(self):
        """Test non-standard channel count returns generic layout."""
        assert get_output_layout(4) == "4c"
