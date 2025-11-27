"""Tests for policy/video_analysis.py - video stream analysis utilities."""

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.video_analysis import (
    HDRType,
    VideoAnalysisResult,
    analyze_video_tracks,
    build_hdr_preservation_args,
    detect_hdr_content,
    detect_hdr_type,
    detect_missing_bitrate,
    detect_vfr_content,
    parse_frame_rate,
    select_primary_video_stream,
)


class TestParseFrameRate:
    """Tests for parse_frame_rate function."""

    def test_fractional_rate(self) -> None:
        """Parses fractional frame rate (e.g., 24000/1001)."""
        result = parse_frame_rate("24000/1001")
        assert result is not None
        assert abs(result - 23.976) < 0.01

    def test_integer_rate(self) -> None:
        """Parses integer frame rate."""
        assert parse_frame_rate("30") == 30.0
        assert parse_frame_rate("60") == 60.0

    def test_decimal_rate(self) -> None:
        """Parses decimal frame rate."""
        assert parse_frame_rate("29.97") == 29.97

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert parse_frame_rate(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_frame_rate("") is None

    def test_zero_denominator_returns_none(self) -> None:
        """Zero denominator returns None."""
        assert parse_frame_rate("0/0") is None
        assert parse_frame_rate("30/0") is None

    def test_invalid_string_returns_none(self) -> None:
        """Invalid string returns None."""
        assert parse_frame_rate("invalid") is None
        assert parse_frame_rate("abc/def") is None


class TestDetectVfrContent:
    """Tests for detect_vfr_content function."""

    def test_cfr_content(self) -> None:
        """CFR content (matching frame rates) returns False."""
        is_vfr, warning = detect_vfr_content("30/1", "30/1")
        assert is_vfr is False
        assert warning is None

    def test_vfr_content(self) -> None:
        """VFR content (differing frame rates) returns True."""
        # VFR: r_frame_rate=30 but average is 24
        is_vfr, warning = detect_vfr_content("30/1", "24/1")
        assert is_vfr is True
        assert warning is not None
        assert "Variable frame rate" in warning

    def test_slight_difference_is_cfr(self) -> None:
        """Slight difference within tolerance is CFR."""
        # 23.976 vs 24 is within 1% tolerance
        is_vfr, warning = detect_vfr_content("24000/1001", "24/1")
        assert is_vfr is False
        assert warning is None

    def test_none_rates_return_false(self) -> None:
        """None frame rates return False (can't determine)."""
        is_vfr, warning = detect_vfr_content(None, "30/1")
        assert is_vfr is False
        assert warning is None

        is_vfr, warning = detect_vfr_content("30/1", None)
        assert is_vfr is False
        assert warning is None

    def test_zero_avg_returns_false(self) -> None:
        """Zero average frame rate returns False."""
        is_vfr, warning = detect_vfr_content("30/1", "0/1")
        assert is_vfr is False
        assert warning is None


class TestDetectMissingBitrate:
    """Tests for detect_missing_bitrate function."""

    def test_bitrate_present(self) -> None:
        """Returns actual bitrate when present."""
        was_estimated, bitrate, warning = detect_missing_bitrate(
            bitrate=10_000_000, file_size_bytes=None, duration_seconds=None
        )
        assert was_estimated is False
        assert bitrate == 10_000_000
        assert warning is None

    def test_estimates_from_file_size(self) -> None:
        """Estimates bitrate from file size and duration."""
        # 100 MB file, 100 seconds = 8 Mbps
        file_size = 100 * 1024 * 1024  # 100 MB
        duration = 100.0  # seconds
        expected_bps = (file_size * 8) // 100  # bits per second

        was_estimated, bitrate, warning = detect_missing_bitrate(
            bitrate=None, file_size_bytes=file_size, duration_seconds=duration
        )
        assert was_estimated is True
        assert bitrate == expected_bps
        assert warning is not None
        assert "Estimated" in warning

    def test_missing_file_size(self) -> None:
        """Returns None bitrate when file size is missing."""
        was_estimated, bitrate, warning = detect_missing_bitrate(
            bitrate=None, file_size_bytes=None, duration_seconds=100.0
        )
        assert was_estimated is True
        assert bitrate is None
        assert warning is not None
        assert "cannot be estimated" in warning

    def test_zero_duration(self) -> None:
        """Returns None bitrate when duration is zero."""
        was_estimated, bitrate, warning = detect_missing_bitrate(
            bitrate=None, file_size_bytes=1000, duration_seconds=0.0
        )
        assert was_estimated is True
        assert bitrate is None
        assert warning is not None

    def test_zero_bitrate_triggers_estimation(self) -> None:
        """Zero bitrate triggers estimation."""
        was_estimated, bitrate, warning = detect_missing_bitrate(
            bitrate=0, file_size_bytes=100 * 1024 * 1024, duration_seconds=100.0
        )
        assert was_estimated is True
        assert bitrate is not None


class TestSelectPrimaryVideoStream:
    """Tests for select_primary_video_stream function."""

    def _make_track(
        self,
        index: int,
        track_type: str = "video",
        is_default: bool = False,
    ) -> TrackInfo:
        """Helper to create a TrackInfo for testing."""
        return TrackInfo(
            index=index,
            track_type=track_type,
            codec="hevc",
            language="eng",
            title=None,
            is_default=is_default,
            is_forced=False,
        )

    def test_single_video_track(self) -> None:
        """Returns single video track with no warnings."""
        tracks = [self._make_track(0, "video")]
        primary, warnings = select_primary_video_stream(tracks)
        assert primary is not None
        assert primary.index == 0
        assert warnings == []

    def test_no_video_tracks(self) -> None:
        """Returns None with warning when no video tracks."""
        tracks = [self._make_track(0, "audio")]
        primary, warnings = select_primary_video_stream(tracks)
        assert primary is None
        assert len(warnings) == 1
        assert "No video streams" in warnings[0]

    def test_multiple_tracks_selects_default(self) -> None:
        """Selects default-flagged track when multiple exist."""
        tracks = [
            self._make_track(0, "video", is_default=False),
            self._make_track(1, "video", is_default=True),
            self._make_track(2, "video", is_default=False),
        ]
        primary, warnings = select_primary_video_stream(tracks)
        assert primary is not None
        assert primary.index == 1
        assert len(warnings) == 1
        assert "Multiple video streams" in warnings[0]

    def test_multiple_tracks_no_default(self) -> None:
        """Selects first track when none is default."""
        tracks = [
            self._make_track(0, "video", is_default=False),
            self._make_track(1, "video", is_default=False),
        ]
        primary, warnings = select_primary_video_stream(tracks)
        assert primary is not None
        assert primary.index == 0
        assert len(warnings) == 1

    def test_mixed_track_types(self) -> None:
        """Only considers video tracks."""
        tracks = [
            self._make_track(0, "audio"),
            self._make_track(1, "video"),
            self._make_track(2, "subtitle"),
        ]
        primary, warnings = select_primary_video_stream(tracks)
        assert primary is not None
        assert primary.index == 1
        assert warnings == []


class TestDetectHdrType:
    """Tests for detect_hdr_type function."""

    def _make_video_track(
        self,
        color_transfer: str | None = None,
        title: str | None = None,
    ) -> TrackInfo:
        """Helper to create video TrackInfo for HDR testing."""
        return TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            language="eng",
            title=title,
            is_default=True,
            is_forced=False,
            color_transfer=color_transfer,
        )

    def test_sdr_content(self) -> None:
        """SDR content returns NONE."""
        tracks = [self._make_video_track(color_transfer="bt709")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.NONE
        assert desc is None

    def test_hdr10_from_transfer(self) -> None:
        """HDR10 detected from smpte2084 transfer."""
        tracks = [self._make_video_track(color_transfer="smpte2084")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.HDR10
        assert desc is not None
        assert "HDR10" in desc

    def test_hlg_from_transfer(self) -> None:
        """HLG detected from arib-std-b67 transfer."""
        tracks = [self._make_video_track(color_transfer="arib-std-b67")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.HLG
        assert desc is not None
        assert "HLG" in desc

    def test_dolby_vision_from_title(self) -> None:
        """Dolby Vision detected from title."""
        tracks = [self._make_video_track(title="Dolby Vision HDR")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.DOLBY_VISION
        assert desc is not None

    def test_dovi_from_title(self) -> None:
        """Dolby Vision detected from 'dovi' in title."""
        tracks = [self._make_video_track(title="Video DoVi")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.DOLBY_VISION

    def test_hdr10_from_title(self) -> None:
        """HDR10 detected from title when no transfer info."""
        tracks = [self._make_video_track(title="Movie HDR10")]
        hdr_type, desc = detect_hdr_type(tracks)
        assert hdr_type == HDRType.HDR10

    def test_no_video_tracks(self) -> None:
        """Returns NONE when no video tracks."""
        hdr_type, desc = detect_hdr_type([])
        assert hdr_type == HDRType.NONE
        assert desc is None


class TestDetectHdrContent:
    """Tests for detect_hdr_content compatibility wrapper."""

    def test_returns_boolean(self) -> None:
        """Returns boolean instead of HDRType enum."""
        track = TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            language="eng",
            title=None,
            is_default=True,
            is_forced=False,
            color_transfer="smpte2084",
        )
        is_hdr, desc = detect_hdr_content([track])
        assert is_hdr is True
        assert isinstance(is_hdr, bool)


class TestBuildHdrPreservationArgs:
    """Tests for build_hdr_preservation_args function."""

    def test_sdr_returns_empty(self) -> None:
        """SDR content returns empty args."""
        args = build_hdr_preservation_args(HDRType.NONE)
        assert args == []

    def test_hdr10_args(self) -> None:
        """HDR10 includes proper color metadata."""
        args = build_hdr_preservation_args(HDRType.HDR10)
        assert "-colorspace" in args
        assert "bt2020nc" in args
        assert "-color_trc" in args
        assert "smpte2084" in args

    def test_hlg_args(self) -> None:
        """HLG includes proper transfer function."""
        args = build_hdr_preservation_args(HDRType.HLG)
        assert "-color_trc" in args
        assert "arib-std-b67" in args

    def test_dolby_vision_uses_pq(self) -> None:
        """Dolby Vision uses PQ transfer function."""
        args = build_hdr_preservation_args(HDRType.DOLBY_VISION)
        assert "smpte2084" in args


class TestAnalyzeVideoTracks:
    """Tests for analyze_video_tracks orchestration function."""

    def _make_video_track(
        self,
        index: int = 0,
        is_default: bool = True,
        color_transfer: str | None = None,
    ) -> TrackInfo:
        """Helper to create video TrackInfo."""
        return TrackInfo(
            index=index,
            track_type="video",
            codec="hevc",
            language="eng",
            title=None,
            is_default=is_default,
            is_forced=False,
            color_transfer=color_transfer,
        )

    def test_complete_analysis(self) -> None:
        """Returns complete VideoAnalysisResult."""
        tracks = [self._make_video_track(color_transfer="smpte2084")]
        result = analyze_video_tracks(
            tracks=tracks,
            video_bitrate=10_000_000,
            file_size_bytes=100 * 1024 * 1024,
            duration_seconds=100.0,
            r_frame_rate="24000/1001",
            avg_frame_rate="24000/1001",
        )

        assert isinstance(result, VideoAnalysisResult)
        assert result.primary_video_track is not None
        assert result.primary_video_index == 0
        assert result.is_vfr is False
        assert result.is_hdr is True
        assert result.hdr_type == HDRType.HDR10
        assert result.bitrate_estimated is False
        assert result.estimated_bitrate == 10_000_000

    def test_accumulates_warnings(self) -> None:
        """Accumulates warnings from all analysis steps."""
        # Multiple video streams (warning) + missing bitrate (warning)
        tracks = [
            self._make_video_track(index=0, is_default=False),
            self._make_video_track(index=1, is_default=False),
        ]
        result = analyze_video_tracks(
            tracks=tracks,
            video_bitrate=None,
            file_size_bytes=None,
            duration_seconds=None,
            r_frame_rate=None,
            avg_frame_rate=None,
        )

        # Should have warnings for multiple streams and missing bitrate
        assert len(result.warnings) >= 2

    def test_empty_tracks(self) -> None:
        """Handles empty track list."""
        result = analyze_video_tracks(
            tracks=[],
            video_bitrate=None,
            file_size_bytes=None,
            duration_seconds=None,
            r_frame_rate=None,
            avg_frame_rate=None,
        )

        assert result.primary_video_track is None
        assert result.primary_video_index is None
        assert result.is_hdr is False
        assert result.hdr_type == HDRType.NONE
