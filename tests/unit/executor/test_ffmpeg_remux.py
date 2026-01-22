"""Unit tests for FFmpegRemuxExecutor.

Tests for command building, output stream index calculation,
temp file cleanup, and output validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.ffmpeg_remux import FFmpegRemuxExecutor
from vpo.policy.types import (
    ContainerChange,
    ContainerTranscodePlan,
    IncompatibleTrackPlan,
    Plan,
    TrackDisposition,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def executor() -> FFmpegRemuxExecutor:
    """Create a basic executor instance."""
    return FFmpegRemuxExecutor(timeout=60)


@pytest.fixture
def mock_plan(tmp_path: Path) -> Plan:
    """Create a basic mock plan."""
    return Plan(
        file_id="test-id",
        file_path=tmp_path / "test.mkv",
        policy_version=12,
        actions=(),
        requires_remux=True,
        container_change=ContainerChange(
            source_format="mkv",
            target_format="mp4",
            warnings=(),
            incompatible_tracks=(),
        ),
    )


# =============================================================================
# Tests for _build_transcode_command output stream index calculation
# =============================================================================


class TestBuildTranscodeCommandStreamIndices:
    """Tests for correct output stream index calculation in _build_transcode_command."""

    def test_single_audio_transcode_no_removals(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Single audio transcode with no removals uses correct index."""
        # Track 0: video, Track 1: audio (transcode to aac)
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="audio",
                    source_codec="truehd",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="256k",
                    reason="truehd is not MP4-compatible",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1,),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # No tracks removed, so output index = input index
        assert "-c:1" in cmd
        assert cmd[cmd.index("-c:1") + 1] == "aac"
        assert "-b:1" in cmd
        assert cmd[cmd.index("-b:1") + 1] == "256k"

    def test_mixed_remove_and_transcode_correct_indices(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Transcode after removal uses corrected output index."""
        # Track 0: video
        # Track 1: audio (remove - PGS subtitle mislabeled as audio for test)
        # Track 2: audio (transcode to aac)
        # After removing track 1, track 2 becomes output index 1
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="audio",
                    source_codec="truehd",
                    action="remove",
                    reason="removed",
                ),
                IncompatibleTrackPlan(
                    track_index=2,
                    track_type="audio",
                    source_codec="dts",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="256k",
                    reason="dts is not MP4-compatible",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1, 2),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # Track 1 is removed (exclusion map should be present)
        assert "-map" in cmd
        assert "-0:1" in cmd  # Exclusion map for track 1

        # Track 2 input becomes output index 1 (after removing track 1)
        assert "-c:1" in cmd  # Output index 1, not input index 2
        assert cmd[cmd.index("-c:1") + 1] == "aac"

    def test_multiple_removals_before_transcode(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Multiple removals correctly shift transcode indices."""
        # Track 0: video
        # Track 1: subtitle (remove)
        # Track 2: subtitle (remove)
        # Track 3: audio (transcode)
        # After removing tracks 1 and 2, track 3 becomes output index 1
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="subtitle",
                    source_codec="hdmv_pgs_subtitle",
                    action="remove",
                    reason="bitmap subtitles removed",
                ),
                IncompatibleTrackPlan(
                    track_index=2,
                    track_type="subtitle",
                    source_codec="dvd_subtitle",
                    action="remove",
                    reason="bitmap subtitles removed",
                ),
                IncompatibleTrackPlan(
                    track_index=3,
                    track_type="audio",
                    source_codec="truehd",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="320k",
                    reason="truehd is not MP4-compatible",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1, 2, 3),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # Tracks 1 and 2 are removed
        assert "-0:1" in cmd
        assert "-0:2" in cmd

        # Track 3 becomes output index 1 (0 is video, 1&2 removed)
        assert "-c:1" in cmd
        assert cmd[cmd.index("-c:1") + 1] == "aac"

    def test_with_track_dispositions_combined_removals(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Track dispositions and transcode_plan removals combine correctly."""
        # Track 0: video
        # Track 1: audio (removed by disposition)
        # Track 2: audio (transcode)
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=2,
                    track_type="audio",
                    source_codec="dts",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="256k",
                    reason="dts is not MP4-compatible",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            track_dispositions=(
                TrackDisposition(
                    track_index=1,
                    track_type="audio",
                    codec="aac",
                    language="eng",
                    title=None,
                    channels=2,
                    resolution=None,
                    action="REMOVE",
                    reason="Language filter",
                ),
            ),
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(2,),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # Track 1 removed by disposition
        assert "-0:1" in cmd

        # Track 2 becomes output index 1 (after removing track 1)
        assert "-c:1" in cmd
        assert cmd[cmd.index("-c:1") + 1] == "aac"

    def test_subtitle_convert_with_removals(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Subtitle conversion indices correct after audio removal."""
        # Track 0: video
        # Track 1: audio (remove)
        # Track 2: subtitle (convert to mov_text)
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="audio",
                    source_codec="truehd",
                    action="remove",
                    reason="removed",
                ),
                IncompatibleTrackPlan(
                    track_index=2,
                    track_type="subtitle",
                    source_codec="subrip",
                    action="convert",
                    target_codec="mov_text",
                    reason="text subtitle conversion",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1, 2),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # Track 2 becomes output index 1
        assert "-c:1" in cmd
        assert cmd[cmd.index("-c:1") + 1] == "mov_text"

    def test_bitrate_only_for_transcode_action(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Bitrate option only added for transcode action, not convert."""
        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="audio",
                    source_codec="truehd",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="320k",
                    reason="transcode",
                ),
                IncompatibleTrackPlan(
                    track_index=2,
                    track_type="subtitle",
                    source_codec="subrip",
                    action="convert",
                    target_codec="mov_text",
                    reason="convert",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1, 2),
                transcode_plan=transcode_plan,
            ),
        )

        cmd = executor._build_transcode_command(
            plan, tmp_path / "output.mp4", transcode_plan
        )

        # Audio track has bitrate
        assert "-b:1" in cmd
        # Subtitle track doesn't have bitrate
        assert "-b:2" not in cmd


# =============================================================================
# Tests for timeout scaling
# =============================================================================


class TestTimeoutScaling:
    """Tests for _compute_timeout_for_plan method."""

    def test_returns_none_when_timeout_zero(self, tmp_path: Path) -> None:
        """Returns None when timeout is 0 (no timeout)."""
        executor = FFmpegRemuxExecutor(timeout=0)
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        result = executor._compute_timeout_for_plan(plan)

        assert result is None

    def test_uses_default_timeout_without_transcode(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Uses default timeout when no transcoding involved."""
        plan = Plan(
            file_id="test-id",
            file_path=tmp_path / "test.mkv",
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        result = executor._compute_timeout_for_plan(plan)

        assert result == 60  # Our test executor timeout

    def test_scales_timeout_for_large_file_with_transcode(self, tmp_path: Path) -> None:
        """Scales timeout based on file size when transcoding."""
        executor = FFmpegRemuxExecutor(timeout=60)

        # Create a 2GB mock file
        input_file = tmp_path / "test.mkv"
        input_file.touch()

        transcode_plan = ContainerTranscodePlan(
            track_plans=(
                IncompatibleTrackPlan(
                    track_index=1,
                    track_type="audio",
                    source_codec="truehd",
                    action="transcode",
                    target_codec="aac",
                    target_bitrate="256k",
                    reason="test",
                ),
            ),
        )
        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(1,),
                transcode_plan=transcode_plan,
            ),
        )

        # Mock stat to return 2GB file size
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_size=2 * 1024**3)
            result = executor._compute_timeout_for_plan(plan)

        # 2GB * 300 seconds/GB = 600 seconds, which is > 60
        assert result == 600


# =============================================================================
# Tests for output validation
# =============================================================================


class TestOutputValidation:
    """Tests for FFmpeg output file validation."""

    def test_execute_fails_if_output_missing(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Execute fails if FFmpeg returns 0 but no output file."""
        input_file = tmp_path / "test.mkv"
        input_file.write_bytes(b"fake mkv content")

        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        with patch("subprocess.run") as mock_run:
            # FFmpeg returns 0 but we won't create the temp file
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Mock tempfile to track temp path
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.__enter__ = MagicMock(
                    return_value=mock_temp_instance
                )
                mock_temp_instance.__exit__ = MagicMock(return_value=False)
                mock_temp_instance.name = str(tmp_path / "nonexistent.mp4")
                mock_temp.return_value = mock_temp_instance

                result = executor.execute(plan)

        assert result.success is False
        # Output validation now reports "does not exist"
        msg = result.message.lower()
        assert "does not exist" in msg or "validation failed" in msg

    def test_execute_fails_if_output_empty(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Execute fails if FFmpeg creates empty output file."""
        input_file = tmp_path / "test.mkv"
        input_file.write_bytes(b"fake mkv content")

        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Create actual temp file that's empty
            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                empty_file = tmp_path / "empty.mp4"
                empty_file.touch()  # Empty file

                mock_temp_instance = MagicMock()
                mock_temp_instance.__enter__ = MagicMock(
                    return_value=mock_temp_instance
                )
                mock_temp_instance.__exit__ = MagicMock(return_value=False)
                mock_temp_instance.name = str(empty_file)
                mock_temp.return_value = mock_temp_instance

                result = executor.execute(plan)

        assert result.success is False
        assert "empty" in result.message.lower()


# =============================================================================
# Tests for temp file cleanup
# =============================================================================


class TestTempFileCleanup:
    """Tests for temp file cleanup on errors."""

    def test_temp_file_cleaned_on_subprocess_error(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Temp file is cleaned up when subprocess raises an error."""
        input_file = tmp_path / "test.mkv"
        input_file.write_bytes(b"fake mkv content")

        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        temp_file = tmp_path / "temp_output.mp4"
        temp_file.write_bytes(b"partial content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("FFmpeg not found")

            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.__enter__ = MagicMock(
                    return_value=mock_temp_instance
                )
                mock_temp_instance.__exit__ = MagicMock(return_value=False)
                mock_temp_instance.name = str(temp_file)
                mock_temp.return_value = mock_temp_instance

                result = executor.execute(plan)

        assert result.success is False
        # Temp file should be cleaned up
        assert not temp_file.exists()

    def test_temp_file_cleaned_on_timeout(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Temp file is cleaned up when subprocess times out."""
        import subprocess

        input_file = tmp_path / "test.mkv"
        input_file.write_bytes(b"fake mkv content")

        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        temp_file = tmp_path / "temp_output.mp4"
        temp_file.write_bytes(b"partial content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 60)

            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.__enter__ = MagicMock(
                    return_value=mock_temp_instance
                )
                mock_temp_instance.__exit__ = MagicMock(return_value=False)
                mock_temp_instance.name = str(temp_file)
                mock_temp.return_value = mock_temp_instance

                result = executor.execute(plan)

        assert result.success is False
        assert "timed out" in result.message.lower()
        assert not temp_file.exists()

    def test_temp_file_cleaned_on_nonzero_exit(
        self, executor: FFmpegRemuxExecutor, tmp_path: Path
    ) -> None:
        """Temp file is cleaned up when FFmpeg returns non-zero."""
        input_file = tmp_path / "test.mkv"
        input_file.write_bytes(b"fake mkv content")

        plan = Plan(
            file_id="test-id",
            file_path=input_file,
            policy_version=12,
            actions=(),
            requires_remux=True,
            container_change=ContainerChange(
                source_format="mkv",
                target_format="mp4",
                warnings=(),
                incompatible_tracks=(),
            ),
        )

        temp_file = tmp_path / "temp_output.mp4"
        temp_file.write_bytes(b"partial content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Conversion failed")

            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_temp_instance = MagicMock()
                mock_temp_instance.__enter__ = MagicMock(
                    return_value=mock_temp_instance
                )
                mock_temp_instance.__exit__ = MagicMock(return_value=False)
                mock_temp_instance.name = str(temp_file)
                mock_temp.return_value = mock_temp_instance

                result = executor.execute(plan)

        assert result.success is False
        assert not temp_file.exists()
