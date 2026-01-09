"""Unit tests for V6 skip condition evaluation.

NOTE: The skip condition evaluation logic has been moved from
executor/transcode.py to policy/transcode.py as part of the
clean architecture refactoring. Tests have been updated to
import from the new locations.
"""

import pytest

# Import codec matching from unified codecs module
from vpo.policy.codecs import video_codec_matches_any
from vpo.policy.models import (
    SkipCondition,
    parse_bitrate,
)

# Import skip evaluation from policy layer (new location)
from vpo.policy.transcode import (
    _bitrate_under_threshold,
    _resolution_within_threshold,
    evaluate_skip_condition,
)


class TestSkipConditionDataclass:
    """Tests for SkipCondition dataclass (T012)."""

    def test_skip_condition_with_codec_matches(self):
        """SkipCondition stores codec_matches correctly."""
        sc = SkipCondition(codec_matches=("hevc", "h265"))
        assert sc.codec_matches == ("hevc", "h265")

    def test_skip_condition_with_resolution_within(self):
        """SkipCondition stores resolution_within correctly."""
        sc = SkipCondition(resolution_within="1080p")
        assert sc.resolution_within == "1080p"

    def test_skip_condition_with_bitrate_under(self):
        """SkipCondition stores bitrate_under correctly."""
        sc = SkipCondition(bitrate_under="10M")
        assert sc.bitrate_under == "10M"

    def test_skip_condition_all_fields(self):
        """SkipCondition stores all fields together."""
        sc = SkipCondition(
            codec_matches=("hevc", "h265"),
            resolution_within="1080p",
            bitrate_under="10M",
        )
        assert sc.codec_matches == ("hevc", "h265")
        assert sc.resolution_within == "1080p"
        assert sc.bitrate_under == "10M"

    def test_skip_condition_empty_raises(self):
        """SkipCondition with no conditions raises ValueError.

        Empty skip_if would match all files (vacuously true), which is
        almost certainly not the intended behavior. Users must specify
        at least one condition.
        """
        with pytest.raises(ValueError, match="requires at least one condition"):
            SkipCondition()

    def test_skip_condition_invalid_resolution_raises(self):
        """Invalid resolution_within raises ValueError."""
        with pytest.raises(ValueError, match="Invalid resolution_within"):
            SkipCondition(resolution_within="invalid")

    def test_skip_condition_invalid_bitrate_raises(self):
        """Invalid bitrate_under raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bitrate_under"):
            SkipCondition(bitrate_under="invalid")


class TestParseBitrate:
    """Tests for bitrate parsing utility."""

    def test_parse_megabits_uppercase(self):
        """Parse '10M' correctly."""
        assert parse_bitrate("10M") == 10_000_000

    def test_parse_megabits_lowercase(self):
        """Parse '10m' correctly."""
        assert parse_bitrate("10m") == 10_000_000

    def test_parse_kilobits_uppercase(self):
        """Parse '5000K' correctly."""
        assert parse_bitrate("5000K") == 5_000_000

    def test_parse_kilobits_lowercase(self):
        """Parse '5000k' correctly."""
        assert parse_bitrate("5000k") == 5_000_000

    def test_parse_decimal_megabits(self):
        """Parse '2.5M' correctly."""
        assert parse_bitrate("2.5M") == 2_500_000

    def test_parse_raw_bits(self):
        """Parse raw number as bits per second."""
        assert parse_bitrate("1000000") == 1_000_000

    def test_parse_invalid_returns_none(self):
        """Invalid bitrate returns None."""
        assert parse_bitrate("invalid") is None
        assert parse_bitrate("") is None

    def test_parse_with_whitespace(self):
        """Parse with surrounding whitespace."""
        assert parse_bitrate("  10M  ") == 10_000_000


class TestCodecMatchesEvaluation:
    """Tests for codec_matches evaluation (T014).

    NOTE: Codec matching has been moved to policy/codecs.py.
    Using video_codec_matches_any imported at module level.
    """

    def test_codec_matches_exact_match(self):
        """Exact codec match returns True."""
        assert video_codec_matches_any("hevc", ("hevc", "h265")) is True

    def test_codec_matches_case_insensitive(self):
        """Codec matching is case-insensitive."""
        assert video_codec_matches_any("HEVC", ("hevc", "h265")) is True
        assert video_codec_matches_any("hevc", ("HEVC", "H265")) is True

    def test_codec_matches_no_match(self):
        """No match returns False."""
        assert video_codec_matches_any("h264", ("hevc", "h265")) is False

    def test_codec_matches_alias(self):
        """Codec aliases are matched (h265 == hevc)."""
        # h265 should match hevc pattern
        assert video_codec_matches_any("h265", ("hevc",)) is True
        # hevc should match h265 pattern
        assert video_codec_matches_any("hevc", ("h265",)) is True


class TestResolutionWithinEvaluation:
    """Tests for resolution_within evaluation (T015).

    NOTE: Resolution evaluation has been moved to policy/transcode.py.
    Using _resolution_within_threshold imported at module level.
    """

    def test_resolution_within_passes_at_limit(self):
        """Resolution at exact limit passes."""
        # 1080p is 1920x1080
        assert _resolution_within_threshold(1920, 1080, "1080p") is True

    def test_resolution_within_passes_below_limit(self):
        """Resolution below limit passes."""
        assert _resolution_within_threshold(1280, 720, "1080p") is True

    def test_resolution_within_fails_above_limit(self):
        """Resolution above limit fails."""
        # 4K exceeds 1080p
        assert _resolution_within_threshold(3840, 2160, "1080p") is False

    def test_resolution_within_different_presets(self):
        """Different resolution presets work."""
        # 720p limit
        assert _resolution_within_threshold(1280, 720, "720p") is True
        assert _resolution_within_threshold(1920, 1080, "720p") is False

        # 4k limit
        assert _resolution_within_threshold(3840, 2160, "4k") is True
        assert _resolution_within_threshold(7680, 4320, "4k") is False

    def test_resolution_within_none_returns_true(self):
        """None resolution_within always passes."""
        assert _resolution_within_threshold(3840, 2160, None) is True


class TestBitrateUnderEvaluation:
    """Tests for bitrate_under evaluation (T016).

    NOTE: Bitrate evaluation has been moved to policy/transcode.py.
    Using _bitrate_under_threshold imported at module level.
    """

    def test_bitrate_under_passes_below_threshold(self):
        """Bitrate below threshold passes."""
        # 5 Mbps < 10 Mbps threshold
        assert _bitrate_under_threshold(5_000_000, "10M") is True

    def test_bitrate_under_fails_at_threshold(self):
        """Bitrate at threshold fails (must be under, not equal)."""
        assert _bitrate_under_threshold(10_000_000, "10M") is False

    def test_bitrate_under_fails_above_threshold(self):
        """Bitrate above threshold fails."""
        assert _bitrate_under_threshold(15_000_000, "10M") is False

    def test_bitrate_under_none_returns_true(self):
        """None bitrate_under always passes."""
        assert _bitrate_under_threshold(100_000_000, None) is True


class TestShouldSkipTranscode:
    """Tests for should_skip_transcode/evaluate_skip_condition function (T013, T017).

    NOTE: Skip evaluation has been moved to policy/transcode.py.
    Using evaluate_skip_condition imported at module level.
    """

    def test_skip_when_codec_matches(self):
        """Skip when codec matches skip_if.codec_matches."""
        skip_if = SkipCondition(codec_matches=("hevc", "h265"))
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,
        )
        assert result.skip is True
        assert "codec" in result.reason.lower()

    def test_no_skip_when_codec_mismatch(self):
        """No skip when codec doesn't match."""
        skip_if = SkipCondition(codec_matches=("hevc", "h265"))
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,
        )
        assert result.skip is False

    def test_skip_with_resolution_only(self):
        """Skip based on resolution_within alone."""
        skip_if = SkipCondition(resolution_within="1080p")
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,
        )
        assert result.skip is True

    def test_skip_with_bitrate_only(self):
        """Skip based on bitrate_under alone."""
        skip_if = SkipCondition(bitrate_under="10M")
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=5_000_000,
        )
        assert result.skip is True

    def test_and_logic_all_conditions_must_pass(self):
        """All specified conditions must pass for skip (AND logic) (T017)."""
        # All conditions match
        skip_if = SkipCondition(
            codec_matches=("hevc",),
            resolution_within="1080p",
            bitrate_under="10M",
        )
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=5_000_000,
        )
        assert result.skip is True

    def test_and_logic_one_condition_fails_no_skip(self):
        """If one condition fails, no skip (AND logic)."""
        # Codec matches, resolution matches, but bitrate too high
        skip_if = SkipCondition(
            codec_matches=("hevc",),
            resolution_within="1080p",
            bitrate_under="10M",
        )
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=15_000_000,  # Above 10M threshold
        )
        assert result.skip is False

    def test_none_skip_if_returns_no_skip(self):
        """None skip_if returns no skip."""
        result = evaluate_skip_condition(
            skip_if=None,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,
        )
        assert result.skip is False

    def test_empty_skip_condition_raises_at_construction(self):
        """Empty SkipCondition raises ValueError at construction.

        Empty skip_if would skip all files (vacuously true), which is
        almost certainly not the intended behavior. This is caught
        at SkipCondition construction time.
        """
        with pytest.raises(ValueError, match="requires at least one condition"):
            SkipCondition()

    def test_skip_reason_includes_details(self):
        """Skip reason includes what conditions were met."""
        skip_if = SkipCondition(
            codec_matches=("hevc",),
            resolution_within="1080p",
        )
        result = evaluate_skip_condition(
            skip_if=skip_if,
            video_codec="hevc",
            video_width=1920,
            video_height=1080,
            video_bitrate=None,
        )
        assert result.skip is True
        assert result.reason is not None
        assert len(result.reason) > 0
