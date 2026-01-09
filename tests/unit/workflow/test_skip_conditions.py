"""Unit tests for skip condition evaluation.

T011/T012: Tests for skip_when condition evaluation.
"""

from datetime import datetime
from pathlib import Path

import pytest

from vpo.db.types import FileInfo, TrackInfo
from vpo.policy.models import (
    PhaseSkipCondition,
    SkipReasonType,
)
from vpo.workflow.skip_conditions import (
    evaluate_skip_when,
    get_video_resolution_label,
    parse_duration,
    parse_file_size,
)


class TestParseDuration:
    """Tests for duration string parsing."""

    def test_parse_seconds(self) -> None:
        """Parse seconds format."""
        assert parse_duration("30s") == 30.0
        assert parse_duration("90s") == 90.0

    def test_parse_minutes(self) -> None:
        """Parse minutes format."""
        assert parse_duration("30m") == 1800.0
        assert parse_duration("90m") == 5400.0

    def test_parse_hours(self) -> None:
        """Parse hours format."""
        assert parse_duration("2h") == 7200.0
        assert parse_duration("1h") == 3600.0

    def test_parse_compound_format(self) -> None:
        """Parse compound hour:minute format."""
        assert parse_duration("1h30m") == 5400.0
        assert parse_duration("2h15m") == 8100.0
        assert parse_duration("1h0m") == 3600.0

    def test_parse_invalid_returns_none(self) -> None:
        """Invalid format returns None."""
        assert parse_duration("invalid") is None
        assert parse_duration("30") is None
        assert parse_duration("h30m") is None


class TestParseFileSize:
    """Tests for file size string parsing."""

    def test_parse_bytes(self) -> None:
        """Parse bytes."""
        assert parse_file_size("1024B") == 1024

    def test_parse_kilobytes(self) -> None:
        """Parse kilobytes."""
        assert parse_file_size("100KB") == 102400

    def test_parse_megabytes(self) -> None:
        """Parse megabytes."""
        assert parse_file_size("500MB") == 524288000

    def test_parse_gigabytes(self) -> None:
        """Parse gigabytes."""
        assert parse_file_size("1GB") == 1073741824
        assert parse_file_size("5GB") == 5368709120

    def test_parse_terabytes(self) -> None:
        """Parse terabytes."""
        assert parse_file_size("1TB") == 1099511627776

    def test_parse_decimal(self) -> None:
        """Parse decimal sizes."""
        assert parse_file_size("1.5GB") == 1610612736

    def test_case_insensitive(self) -> None:
        """Size parsing is case-insensitive."""
        assert parse_file_size("1gb") == 1073741824
        assert parse_file_size("1Gb") == 1073741824

    def test_parse_invalid_returns_none(self) -> None:
        """Invalid format returns None."""
        assert parse_file_size("invalid") is None
        assert parse_file_size("1000") is None
        assert parse_file_size("GB") is None


class TestGetVideoResolutionLabel:
    """Tests for resolution label generation."""

    def test_4k_resolution(self) -> None:
        """4K resolution (2160p)."""
        assert get_video_resolution_label(2160) == "2160p"
        assert get_video_resolution_label(2200) == "2160p"

    def test_1440p_resolution(self) -> None:
        """1440p resolution."""
        assert get_video_resolution_label(1440) == "1440p"
        assert get_video_resolution_label(1600) == "1440p"

    def test_1080p_resolution(self) -> None:
        """1080p resolution."""
        assert get_video_resolution_label(1080) == "1080p"
        assert get_video_resolution_label(1200) == "1080p"

    def test_720p_resolution(self) -> None:
        """720p resolution."""
        assert get_video_resolution_label(720) == "720p"
        assert get_video_resolution_label(900) == "720p"

    def test_480p_resolution(self) -> None:
        """480p and below resolution."""
        assert get_video_resolution_label(480) == "480p"
        assert get_video_resolution_label(360) == "480p"


@pytest.fixture
def sample_file_info() -> FileInfo:
    """Create sample file info for testing."""
    return FileInfo(
        path=Path("/test/movie.mkv"),
        filename="movie.mkv",
        directory=Path("/test"),
        extension=".mkv",
        size_bytes=5_000_000_000,  # 5GB
        modified_at=datetime.now(),
        content_hash="abc123",
        container_format="matroska",
        tracks=(
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
                duration_seconds=7200.0,  # 2 hours
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                channels=2,
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="srt",
                language="eng",
            ),
        ),
    )


class TestEvaluateSkipWhenVideoCodec:
    """Tests for video_codec skip condition."""

    def test_skip_when_codec_matches_exact(self, sample_file_info: FileInfo) -> None:
        """Skip when video codec matches exactly."""
        condition = PhaseSkipCondition(video_codec=("hevc",))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "video_codec"
        assert "hevc" in result.message

    def test_skip_when_codec_matches_alias(self, sample_file_info: FileInfo) -> None:
        """Skip when video codec matches alias (h265 = hevc)."""
        condition = PhaseSkipCondition(video_codec=("h265",))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.condition_name == "video_codec"

    def test_no_skip_when_codec_differs(self, sample_file_info: FileInfo) -> None:
        """Don't skip when video codec doesn't match."""
        condition = PhaseSkipCondition(video_codec=("h264", "vp9"))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenAudioCodec:
    """Tests for audio_codec_exists skip condition."""

    def test_skip_when_audio_codec_exists(self, sample_file_info: FileInfo) -> None:
        """Skip when audio track with codec exists."""
        condition = PhaseSkipCondition(audio_codec_exists="aac")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "audio_codec_exists"

    def test_no_skip_when_audio_codec_missing(self, sample_file_info: FileInfo) -> None:
        """Don't skip when audio codec not found."""
        condition = PhaseSkipCondition(audio_codec_exists="truehd")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenSubtitleLanguage:
    """Tests for subtitle_language_exists skip condition."""

    def test_skip_when_subtitle_language_exists(
        self, sample_file_info: FileInfo
    ) -> None:
        """Skip when subtitle track with language exists."""
        condition = PhaseSkipCondition(subtitle_language_exists="eng")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "subtitle_language_exists"

    def test_no_skip_when_subtitle_language_missing(
        self, sample_file_info: FileInfo
    ) -> None:
        """Don't skip when subtitle language not found."""
        condition = PhaseSkipCondition(subtitle_language_exists="jpn")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenContainer:
    """Tests for container skip condition."""

    def test_skip_when_container_matches(self, sample_file_info: FileInfo) -> None:
        """Skip when container format matches."""
        condition = PhaseSkipCondition(container=("matroska",))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "container"

    def test_skip_when_container_matches_alias(
        self, sample_file_info: FileInfo
    ) -> None:
        """Skip when container format matches via alias (mkv -> matroska)."""
        # sample_file_info has container_format="matroska", user specifies "mkv"
        condition = PhaseSkipCondition(container=("mkv",))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "container"

    def test_skip_when_mp4_alias(self) -> None:
        """Skip when container matches mp4 alias from ffprobe format string."""
        # ffprobe returns "mov,mp4,m4a,3gp,3g2,mj2" for mp4 files
        file_info = FileInfo(
            path=Path("/test/video.mp4"),
            filename="video.mp4",
            directory=Path("/test"),
            extension=".mp4",
            size_bytes=1_000_000_000,
            modified_at=datetime.now(),
            container_format="mov,mp4,m4a,3gp,3g2,mj2",
            tracks=(),
        )
        condition = PhaseSkipCondition(container=("mp4",))
        result = evaluate_skip_when(condition, file_info, file_info.path)

        assert result is not None
        assert result.condition_name == "container"

    def test_no_skip_when_container_differs(self, sample_file_info: FileInfo) -> None:
        """Don't skip when container doesn't match."""
        condition = PhaseSkipCondition(container=("mp4", "avi"))
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenResolution:
    """Tests for resolution skip condition."""

    def test_skip_when_resolution_matches(self, sample_file_info: FileInfo) -> None:
        """Skip when resolution matches exactly."""
        condition = PhaseSkipCondition(resolution="1080p")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.reason_type == SkipReasonType.CONDITION
        assert result.condition_name == "resolution"

    def test_no_skip_when_resolution_differs(self, sample_file_info: FileInfo) -> None:
        """Don't skip when resolution doesn't match."""
        condition = PhaseSkipCondition(resolution="4k")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenResolutionUnder:
    """Tests for resolution_under skip condition."""

    def test_skip_when_resolution_under_threshold(self) -> None:
        """Skip when resolution is under threshold."""
        file_info = FileInfo(
            path=Path("/test/movie.mkv"),
            filename="movie.mkv",
            directory=Path("/test"),
            extension=".mkv",
            size_bytes=1_000_000_000,
            modified_at=datetime.now(),
            content_hash="abc123",
            container_format="matroska",
            tracks=(
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="h264",
                    width=1280,
                    height=720,
                ),
            ),
        )
        condition = PhaseSkipCondition(resolution_under="1080p")
        result = evaluate_skip_when(condition, file_info, file_info.path)

        assert result is not None
        assert result.condition_name == "resolution_under"
        assert "720p" in result.message

    def test_no_skip_when_resolution_at_threshold(
        self, sample_file_info: FileInfo
    ) -> None:
        """Don't skip when resolution is at threshold."""
        condition = PhaseSkipCondition(resolution_under="1080p")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None


class TestEvaluateSkipWhenFileSize:
    """Tests for file_size_under and file_size_over skip conditions."""

    def test_skip_when_file_size_under(self) -> None:
        """Skip when file size is under threshold."""
        file_info = FileInfo(
            path=Path("/test/small.mkv"),
            filename="small.mkv",
            directory=Path("/test"),
            extension=".mkv",
            size_bytes=500_000_000,  # 500MB
            modified_at=datetime.now(),
            content_hash="abc123",
            container_format="matroska",
            tracks=(),
        )
        condition = PhaseSkipCondition(file_size_under="1GB")
        result = evaluate_skip_when(condition, file_info, file_info.path)

        assert result is not None
        assert result.condition_name == "file_size_under"

    def test_no_skip_when_file_size_over_threshold(
        self, sample_file_info: FileInfo
    ) -> None:
        """Don't skip when file size is over threshold."""
        condition = PhaseSkipCondition(file_size_under="1GB")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None  # 5GB file is not under 1GB

    def test_skip_when_file_size_over(self, sample_file_info: FileInfo) -> None:
        """Skip when file size is over threshold."""
        condition = PhaseSkipCondition(file_size_over="1GB")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.condition_name == "file_size_over"


class TestEvaluateSkipWhenDuration:
    """Tests for duration_under and duration_over skip conditions."""

    def test_skip_when_duration_under(self) -> None:
        """Skip when duration is under threshold."""
        file_info = FileInfo(
            path=Path("/test/short.mkv"),
            filename="short.mkv",
            directory=Path("/test"),
            extension=".mkv",
            size_bytes=100_000_000,
            modified_at=datetime.now(),
            content_hash="abc123",
            container_format="matroska",
            tracks=(
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="h264",
                    duration_seconds=1200.0,  # 20 minutes
                ),
            ),
        )
        condition = PhaseSkipCondition(duration_under="30m")
        result = evaluate_skip_when(condition, file_info, file_info.path)

        assert result is not None
        assert result.condition_name == "duration_under"

    def test_skip_when_duration_over(self, sample_file_info: FileInfo) -> None:
        """Skip when duration is over threshold."""
        condition = PhaseSkipCondition(duration_over="1h")
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None  # 2 hour file is over 1 hour
        assert result.condition_name == "duration_over"


class TestMultipleConditionsOrLogic:
    """Tests for OR logic with multiple conditions."""

    def test_first_matching_condition_wins(self, sample_file_info: FileInfo) -> None:
        """First matching condition triggers skip."""
        # video_codec matches, container doesn't
        condition = PhaseSkipCondition(
            video_codec=("hevc",),
            container=("mp4",),
        )
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is not None
        assert result.condition_name == "video_codec"

    def test_no_conditions_match_returns_none(self, sample_file_info: FileInfo) -> None:
        """Return None when no conditions match."""
        condition = PhaseSkipCondition(
            video_codec=("vp9",),
            container=("mp4",),
            audio_codec_exists="truehd",
        )
        result = evaluate_skip_when(condition, sample_file_info, sample_file_info.path)

        assert result is None
