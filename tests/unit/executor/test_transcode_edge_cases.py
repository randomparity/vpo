"""Unit tests for TranscodeExecutor edge case handling.

Tests for disk space checking, backup handling, output verification,
two-pass encoding, audio handling, and quality arguments that are not
covered by the main test_transcode_executor.py tests.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.executor.transcode import (
    TranscodeExecutor,
    TranscodePlan,
    TwoPassContext,
    build_audio_args,
    build_downmix_filter,
    build_ffmpeg_command_pass1,
    build_quality_args,
    get_audio_encoder,
)
from vpo.executor.transcode.command import (
    _build_stream_maps,
    _needs_explicit_mapping,
)
from vpo.policy.transcode import (
    AudioAction,
    AudioPlan,
    AudioTrackPlan,
)
from vpo.policy.types import (
    QualityMode,
    QualitySettings,
    TranscodePolicyConfig,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def basic_policy() -> TranscodePolicyConfig:
    """Basic transcode policy for testing."""
    return TranscodePolicyConfig(target_video_codec="hevc")


@pytest.fixture
def basic_executor(basic_policy: TranscodePolicyConfig) -> TranscodeExecutor:
    """Basic executor instance for testing."""
    return TranscodeExecutor(policy=basic_policy)


# =============================================================================
# TestCheckDiskSpace
# =============================================================================


class TestCheckDiskSpace:
    """Tests for TranscodeExecutor._check_disk_space_for_plan method."""

    def test_returns_none_when_sufficient_space(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns None when there is sufficient disk space."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 1000)  # 1KB file

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=basic_executor.policy,
            needs_video_transcode=True,
        )

        result = basic_executor._check_disk_space_for_plan(plan)

        assert result is None

    def test_returns_error_when_insufficient_space(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns error message when disk space is insufficient."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 1000)

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=basic_executor.policy,
            needs_video_transcode=True,
        )

        # Mock disk_usage to return very low free space
        with patch.object(shutil, "disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=100)  # 100 bytes free
            result = basic_executor._check_disk_space_for_plan(plan)

        assert result is not None
        assert "Insufficient disk space" in result

    def test_uses_lower_ratio_for_hevc(self, tmp_path: Path) -> None:
        """Uses lower compression ratio estimate for HEVC/AV1."""
        hevc_policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy=hevc_policy)

        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=hevc_policy,
            needs_video_transcode=True,
        )

        # With HEVC, ratio is 0.5, so estimated = 10000 * 0.5 * 1.2 = 6000 bytes
        with patch.object(shutil, "disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=5000)  # 5KB free
            result = executor._check_disk_space_for_plan(plan)

        assert result is not None  # Should fail (5000 < 6000)

    def test_uses_higher_ratio_for_h264(self, tmp_path: Path) -> None:
        """Uses higher compression ratio estimate for H264."""
        h264_policy = TranscodePolicyConfig(target_video_codec="h264")
        executor = TranscodeExecutor(policy=h264_policy)

        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 10000)

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=h264_policy,
            needs_video_transcode=True,
        )

        # With H264, ratio is 0.8, so estimated = 10000 * 0.8 * 1.2 = 9600 bytes
        with patch.object(shutil, "disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=9000)  # 9KB free
            result = executor._check_disk_space_for_plan(plan)

        assert result is not None  # Should fail (9000 < 9600)

    def test_handles_oserror_gracefully(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Handles OSError from disk_usage gracefully."""
        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 1000)

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=basic_executor.policy,
            needs_video_transcode=True,
        )

        with patch.object(shutil, "disk_usage") as mock_usage:
            mock_usage.side_effect = OSError("Permission denied")
            result = basic_executor._check_disk_space_for_plan(plan)

        # Should return None (not error out) when can't check
        assert result is None

    def test_checks_temp_directory_when_specified(self, tmp_path: Path) -> None:
        """Checks temp directory space when temp_directory is set."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy=policy, temp_directory=temp_dir)

        input_file = tmp_path / "input.mkv"
        input_file.write_bytes(b"x" * 1000)

        plan = TranscodePlan(
            input_path=input_file,
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )

        with patch.object(shutil, "disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(free=1000000)
            executor._check_disk_space_for_plan(plan)
            # Should check temp_dir, not output parent
            mock_usage.assert_called_once_with(temp_dir)


# =============================================================================
# TestBackupOriginal
# =============================================================================


class TestBackupOriginal:
    """Tests for TranscodeExecutor._backup_original method."""

    def test_creates_backup_with_original_suffix(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Creates backup file with .original suffix."""
        original = tmp_path / "video.mkv"
        original.write_bytes(b"original content")
        output = tmp_path / "video_new.mkv"
        output.write_bytes(b"transcoded content")

        success, backup_path, error = basic_executor._backup_original(original, output)

        assert success is True
        assert backup_path is not None
        assert backup_path.name == "video.mkv.original"
        assert backup_path.exists()
        assert not original.exists()

    def test_increments_counter_when_backup_exists(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Increments counter suffix when backup already exists."""
        original = tmp_path / "video.mkv"
        original.write_bytes(b"original content")

        # Create existing backup
        existing_backup = tmp_path / "video.mkv.original"
        existing_backup.write_bytes(b"old backup")

        output = tmp_path / "video_new.mkv"
        output.write_bytes(b"transcoded content")

        success, backup_path, error = basic_executor._backup_original(original, output)

        assert success is True
        assert backup_path is not None
        assert backup_path.name == "video.mkv.original.1"

    def test_increments_counter_multiple_backups(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Increments counter correctly with multiple existing backups."""
        original = tmp_path / "video.mkv"
        original.write_bytes(b"original content")

        # Create multiple existing backups
        (tmp_path / "video.mkv.original").write_bytes(b"backup 0")
        (tmp_path / "video.mkv.original.1").write_bytes(b"backup 1")
        (tmp_path / "video.mkv.original.2").write_bytes(b"backup 2")

        output = tmp_path / "video_new.mkv"
        output.write_bytes(b"transcoded content")

        success, backup_path, error = basic_executor._backup_original(original, output)

        assert success is True
        assert backup_path is not None
        assert backup_path.name == "video.mkv.original.3"

    def test_returns_error_on_oserror(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns error tuple on OSError."""
        original = tmp_path / "video.mkv"
        original.write_bytes(b"original content")
        output = tmp_path / "video_new.mkv"

        with patch.object(Path, "rename") as mock_rename:
            mock_rename.side_effect = OSError("Permission denied")
            success, backup_path, error = basic_executor._backup_original(
                original, output
            )

        assert success is False
        assert backup_path is None
        assert error is not None
        assert "Permission denied" in error


# =============================================================================
# TestVerifyOutputIntegrity
# =============================================================================


class TestVerifyOutputIntegrity:
    """Tests for TranscodeExecutor._verify_output_integrity method."""

    def test_returns_false_when_file_missing(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns False when output file does not exist."""
        missing_file = tmp_path / "nonexistent.mkv"

        result = basic_executor._verify_output_integrity(missing_file)

        assert result is False

    def test_returns_false_when_file_empty(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns False when output file is empty."""
        empty_file = tmp_path / "empty.mkv"
        empty_file.touch()

        result = basic_executor._verify_output_integrity(empty_file)

        assert result is False

    def test_returns_true_when_file_valid(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Returns True when output file exists and has content."""
        valid_file = tmp_path / "valid.mkv"
        valid_file.write_bytes(b"video content")

        result = basic_executor._verify_output_integrity(valid_file)

        assert result is True


# =============================================================================
# TestCleanupPartial
# =============================================================================


class TestCleanupPartial:
    """Tests for TranscodeExecutor._cleanup_partial method."""

    def test_removes_existing_file(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Removes partial output file when it exists."""
        partial = tmp_path / "partial.mkv"
        partial.write_bytes(b"partial content")

        basic_executor._cleanup_partial(partial)

        assert not partial.exists()

    def test_handles_nonexistent_file(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Does not error when file does not exist."""
        nonexistent = tmp_path / "nonexistent.mkv"

        # Should not raise
        basic_executor._cleanup_partial(nonexistent)

    def test_handles_oserror(
        self, basic_executor: TranscodeExecutor, tmp_path: Path
    ) -> None:
        """Handles OSError during cleanup gracefully."""
        existing = tmp_path / "locked.mkv"
        existing.write_bytes(b"content")

        with patch.object(Path, "unlink") as mock_unlink:
            mock_unlink.side_effect = OSError("Permission denied")
            # Should not raise
            basic_executor._cleanup_partial(existing)

        # Verify file still exists (cleanup failed but didn't crash)
        assert existing.exists()


# =============================================================================
# TestTwoPassContext
# =============================================================================


class TestTwoPassContext:
    """Tests for TwoPassContext dataclass."""

    def test_cleanup_removes_x265_log_files(self, tmp_path: Path) -> None:
        """Cleanup removes x265 pass log files."""
        passlogfile = tmp_path / "passlog"
        # Create mock log files
        (tmp_path / "passlog.log").write_text("log content")
        (tmp_path / "passlog.log.cutree").write_text("cutree content")

        ctx = TwoPassContext(passlogfile=passlogfile)
        ctx.cleanup()

        assert not (tmp_path / "passlog.log").exists()
        assert not (tmp_path / "passlog.log.cutree").exists()

    def test_cleanup_removes_x264_log_files(self, tmp_path: Path) -> None:
        """Cleanup removes x264 pass log files."""
        passlogfile = tmp_path / "passlog"
        # Create mock log files
        (tmp_path / "passlog-0.log").write_text("log content")
        (tmp_path / "passlog-0.log.mbtree").write_text("mbtree content")

        ctx = TwoPassContext(passlogfile=passlogfile)
        ctx.cleanup()

        assert not (tmp_path / "passlog-0.log").exists()
        assert not (tmp_path / "passlog-0.log.mbtree").exists()

    def test_cleanup_handles_missing_files(self, tmp_path: Path) -> None:
        """Cleanup does not error when log files do not exist."""
        passlogfile = tmp_path / "passlog"

        ctx = TwoPassContext(passlogfile=passlogfile)
        # Should not raise
        ctx.cleanup()

    def test_current_pass_defaults_to_1(self, tmp_path: Path) -> None:
        """Current pass defaults to 1."""
        ctx = TwoPassContext(passlogfile=tmp_path / "passlog")
        assert ctx.current_pass == 1


# =============================================================================
# TestBuildQualityArgs
# =============================================================================


class TestBuildQualityArgs:
    """Tests for build_quality_args function."""

    def test_crf_mode(self) -> None:
        """Builds correct args for CRF quality mode."""
        quality = QualitySettings(mode=QualityMode.CRF, crf=20, preset="slow")
        policy = TranscodePolicyConfig()

        args = build_quality_args(quality, policy, "hevc", "libx265")

        assert "-crf" in args
        assert "20" in args
        assert "-preset" in args
        assert "slow" in args

    def test_bitrate_mode(self) -> None:
        """Builds correct args for bitrate quality mode."""
        quality = QualitySettings(
            mode=QualityMode.BITRATE, bitrate="5M", preset="medium"
        )
        policy = TranscodePolicyConfig()

        args = build_quality_args(quality, policy, "hevc", "libx265")

        assert "-b:v" in args
        assert "5M" in args

    def test_constrained_quality_mode(self) -> None:
        """Builds correct args for constrained quality mode."""
        quality = QualitySettings(
            mode=QualityMode.CONSTRAINED_QUALITY,
            crf=22,
            max_bitrate="10M",
            preset="medium",
        )
        policy = TranscodePolicyConfig()

        args = build_quality_args(quality, policy, "hevc", "libx265")

        assert "-crf" in args
        assert "-maxrate" in args
        assert "-bufsize" in args

    def test_fallback_to_policy_crf(self) -> None:
        """Falls back to policy CRF when quality is None."""
        policy = TranscodePolicyConfig(target_video_codec="hevc", target_crf=18)

        args = build_quality_args(None, policy, "hevc", "libx265")

        assert "-crf" in args
        assert "18" in args

    def test_fallback_to_policy_bitrate(self) -> None:
        """Falls back to policy bitrate when quality is None."""
        policy = TranscodePolicyConfig(target_video_codec="hevc", target_bitrate="8M")

        args = build_quality_args(None, policy, "hevc", "libx265")

        assert "-b:v" in args
        assert "8M" in args

    def test_fallback_to_default_crf(self) -> None:
        """Falls back to default CRF when no quality or policy settings."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")

        args = build_quality_args(None, policy, "hevc", "libx265")

        # Should have default CRF
        assert "-crf" in args

    def test_preset_added_for_x264(self) -> None:
        """Adds preset for libx264 encoder."""
        quality = QualitySettings(mode=QualityMode.CRF, crf=20, preset="fast")
        policy = TranscodePolicyConfig()

        args = build_quality_args(quality, policy, "h264", "libx264")

        assert "-preset" in args
        assert "fast" in args

    def test_tune_option_added_when_specified(self) -> None:
        """Adds tune option when specified in quality settings."""
        quality = QualitySettings(
            mode=QualityMode.CRF, crf=20, preset="medium", tune="film"
        )
        policy = TranscodePolicyConfig()

        args = build_quality_args(quality, policy, "hevc", "libx265")

        assert "-tune" in args
        assert "film" in args

    def test_two_pass_args_for_x264(self, tmp_path: Path) -> None:
        """Adds two-pass args for libx264."""
        quality = QualitySettings(
            mode=QualityMode.BITRATE, bitrate="5M", preset="medium", two_pass=True
        )
        policy = TranscodePolicyConfig()
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")
        two_pass_ctx.current_pass = 1

        args = build_quality_args(quality, policy, "h264", "libx264", two_pass_ctx)

        assert "-pass" in args
        assert "1" in args
        assert "-passlogfile" in args

    def test_two_pass_args_for_x265(self, tmp_path: Path) -> None:
        """Adds two-pass args for libx265."""
        quality = QualitySettings(
            mode=QualityMode.BITRATE, bitrate="5M", preset="medium", two_pass=True
        )
        policy = TranscodePolicyConfig()
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")
        two_pass_ctx.current_pass = 2

        args = build_quality_args(quality, policy, "hevc", "libx265", two_pass_ctx)

        assert "-x265-params" in args
        # Check that pass and stats are in the x265-params
        x265_idx = args.index("-x265-params")
        assert "pass=2" in args[x265_idx + 1]
        assert "stats=" in args[x265_idx + 1]


# =============================================================================
# TestAudioHandling
# =============================================================================


class TestNeedsExplicitMapping:
    """Tests for _needs_explicit_mapping function."""

    def test_returns_true_when_track_removed(self) -> None:
        """Returns True when any track is marked for removal."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
                AudioTrackPlan(
                    track_index=2,
                    stream_index=1,
                    codec="ac3",
                    language="eng",
                    channels=6,
                    channel_layout="5.1",
                    action=AudioAction.REMOVE,
                    reason="Not in keep list",
                ),
            ]
        )

        result = _needs_explicit_mapping(audio_plan)

        assert result is True

    def test_returns_false_when_no_remove(self) -> None:
        """Returns False when no tracks are marked for removal."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
                AudioTrackPlan(
                    track_index=2,
                    stream_index=1,
                    codec="flac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.TRANSCODE,
                    target_codec="aac",
                ),
            ]
        )

        result = _needs_explicit_mapping(audio_plan)

        assert result is False

    def test_returns_false_for_none_plan(self) -> None:
        """Returns False when audio_plan is None."""
        result = _needs_explicit_mapping(None)
        assert result is False


class TestBuildStreamMaps:
    """Tests for _build_stream_maps function."""

    def test_maps_video_stream(self, make_transcode_plan) -> None:
        """Always maps the first video stream."""
        plan = make_transcode_plan()
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
            ]
        )

        args = _build_stream_maps(plan, audio_plan)

        assert "-map" in args
        assert "0:v:0" in args

    def test_excludes_removed_audio_tracks(self, make_transcode_plan) -> None:
        """Excludes audio tracks marked for removal."""
        plan = make_transcode_plan()
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
                AudioTrackPlan(
                    track_index=2,
                    stream_index=1,
                    codec="ac3",
                    language="eng",
                    channels=6,
                    channel_layout="5.1",
                    action=AudioAction.REMOVE,
                ),
            ]
        )

        args = _build_stream_maps(plan, audio_plan)

        # Should have track 1 but not track 2
        assert "0:1" in args
        assert "0:2" not in args

    def test_maps_subtitle_streams(self, make_transcode_plan) -> None:
        """Maps subtitle streams."""
        plan = make_transcode_plan()
        audio_plan = None

        args = _build_stream_maps(plan, audio_plan)

        assert "0:s?" in args

    def test_maps_attachment_streams(self, make_transcode_plan) -> None:
        """Maps attachment streams (fonts, etc.)."""
        plan = make_transcode_plan()
        audio_plan = None

        args = _build_stream_maps(plan, audio_plan)

        assert "0:t?" in args

    def test_maps_all_audio_when_no_plan(self, make_transcode_plan) -> None:
        """Maps all audio when no audio plan provided."""
        plan = make_transcode_plan()

        args = _build_stream_maps(plan, None)

        assert "0:a?" in args


class TestBuildAudioArgs:
    """Tests for build_audio_args function."""

    def test_copy_action_uses_copy_codec(self) -> None:
        """COPY action uses stream copy."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
            ]
        )
        policy = TranscodePolicyConfig()

        args = build_audio_args(audio_plan, policy)

        assert "-c:a:0" in args
        assert "copy" in args

    def test_transcode_action_uses_encoder(self) -> None:
        """TRANSCODE action uses appropriate encoder."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="flac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.TRANSCODE,
                    target_codec="aac",
                    target_bitrate="192k",
                ),
            ]
        )
        policy = TranscodePolicyConfig()

        args = build_audio_args(audio_plan, policy)

        assert "-c:a:0" in args
        assert "aac" in args
        assert "-b:a:0" in args
        assert "192k" in args

    def test_remove_action_no_codec_args(self) -> None:
        """REMOVE action generates no codec arguments."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
                AudioTrackPlan(
                    track_index=2,
                    stream_index=1,
                    codec="ac3",
                    language="eng",
                    channels=6,
                    channel_layout="5.1",
                    action=AudioAction.REMOVE,
                ),
            ]
        )
        policy = TranscodePolicyConfig()

        args = build_audio_args(audio_plan, policy)

        # Should have args for first track only
        assert "-c:a:0" in args
        # Output index 1 should not exist (removed track doesn't increment index)
        assert "-c:a:1" not in args

    def test_output_indices_account_for_removals(self) -> None:
        """Output stream indices correctly account for removed tracks."""
        audio_plan = AudioPlan(
            tracks=[
                AudioTrackPlan(
                    track_index=1,
                    stream_index=0,
                    codec="ac3",
                    language="eng",
                    channels=6,
                    channel_layout="5.1",
                    action=AudioAction.REMOVE,
                ),
                AudioTrackPlan(
                    track_index=2,
                    stream_index=1,
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    action=AudioAction.COPY,
                ),
            ]
        )
        policy = TranscodePolicyConfig()

        args = build_audio_args(audio_plan, policy)

        # Second track becomes output stream 0 (first was removed)
        assert "-c:a:0" in args
        assert "copy" in args


class TestBuildDownmixFilter:
    """Tests for build_downmix_filter function."""

    def test_stereo_downmix(self) -> None:
        """Builds stereo downmix filter."""
        track = AudioTrackPlan(
            track_index=1,
            stream_index=0,
            codec="aac",
            language="eng",
            channels=2,
            channel_layout="stereo",
            action=AudioAction.TRANSCODE,
        )

        result = build_downmix_filter(track)

        assert result is not None
        assert "pan=stereo" in result
        assert "[0:a:0]" in result

    def test_stereo_downmix_with_different_stream_index(self) -> None:
        """Uses correct stream index for stereo downmix."""
        track = AudioTrackPlan(
            track_index=3,
            stream_index=2,
            codec="aac",
            language="eng",
            channels=2,
            channel_layout="stereo",
            action=AudioAction.TRANSCODE,
        )

        result = build_downmix_filter(track)

        assert result is not None
        assert "[0:a:2]" in result

    def test_5_1_downmix(self) -> None:
        """Builds 5.1 downmix filter."""
        track = AudioTrackPlan(
            track_index=1,
            stream_index=1,
            codec="aac",
            language="eng",
            channels=6,
            channel_layout="5.1",
            action=AudioAction.TRANSCODE,
        )

        result = build_downmix_filter(track)

        assert result is not None
        assert "pan=5.1" in result
        assert "[0:a:1]" in result

    def test_unsupported_layout_returns_none(self) -> None:
        """Returns None for unsupported channel layouts."""
        track = AudioTrackPlan(
            track_index=1,
            stream_index=0,
            codec="aac",
            language="eng",
            channels=8,
            channel_layout="7.1",
            action=AudioAction.TRANSCODE,
        )

        result = build_downmix_filter(track)

        assert result is None

    def test_no_channel_layout_returns_none(self) -> None:
        """Returns None when no channel layout specified."""
        track = AudioTrackPlan(
            track_index=1,
            stream_index=0,
            codec="aac",
            language="eng",
            channels=2,
            channel_layout=None,
            action=AudioAction.TRANSCODE,
        )

        result = build_downmix_filter(track)

        assert result is None


# =============================================================================
# TestGetAudioEncoder
# =============================================================================


class TestGetAudioEncoder:
    """Tests for get_audio_encoder function."""

    @pytest.mark.parametrize(
        "codec,expected",
        [
            ("aac", "aac"),
            ("ac3", "ac3"),
            ("eac3", "eac3"),
            ("flac", "flac"),
            ("opus", "libopus"),
            ("mp3", "libmp3lame"),
            ("vorbis", "libvorbis"),
            ("pcm_s16le", "pcm_s16le"),
            ("pcm_s24le", "pcm_s24le"),
        ],
    )
    def test_codec_to_encoder_mapping(self, codec: str, expected: str) -> None:
        """Maps audio codecs to correct FFmpeg encoders."""
        result = get_audio_encoder(codec)
        assert result == expected

    def test_unknown_codec_defaults_to_aac(self) -> None:
        """Unknown codec defaults to AAC encoder."""
        result = get_audio_encoder("unknown_codec")
        assert result == "aac"

    def test_case_insensitive(self) -> None:
        """Codec lookup is case-insensitive."""
        assert get_audio_encoder("AAC") == "aac"
        assert get_audio_encoder("FLAC") == "flac"
        assert get_audio_encoder("Opus") == "libopus"


# =============================================================================
# TestBuildFFmpegCommandPass1
# =============================================================================


class TestBuildFFmpegCommandPass1:
    """Tests for build_ffmpeg_command_pass1 function."""

    def test_outputs_to_null_device(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass outputs to /dev/null (or NUL on Windows)."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        cmd = build_ffmpeg_command_pass1(plan, two_pass_ctx)

        assert "-f" in cmd
        assert "null" in cmd
        # Should have /dev/null or NUL at the end
        assert cmd[-1] in ("/dev/null", "NUL")

    def test_disables_audio(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass disables audio output."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        cmd = build_ffmpeg_command_pass1(plan, two_pass_ctx)

        assert "-an" in cmd

    def test_includes_video_encoder(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass includes video encoder."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        cmd = build_ffmpeg_command_pass1(plan, two_pass_ctx)

        assert "-c:v" in cmd
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "libx265"

    def test_includes_scale_filter(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass includes scale filter when needed."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
            needs_video_scale=True,
            target_width=1920,
            target_height=1080,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        cmd = build_ffmpeg_command_pass1(plan, two_pass_ctx)

        assert "-vf" in cmd
        idx = cmd.index("-vf")
        assert "scale=1920:1080" in cmd[idx + 1]

    def test_includes_cpu_cores(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass includes thread count when specified."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        cmd = build_ffmpeg_command_pass1(plan, two_pass_ctx, cpu_cores=4)

        assert "-threads" in cmd
        idx = cmd.index("-threads")
        assert cmd[idx + 1] == "4"

    def test_sets_pass_to_1(self, tmp_path: Path, mock_ffmpeg) -> None:
        """First pass sets current_pass to 1."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        plan = TranscodePlan(
            input_path=tmp_path / "input.mkv",
            output_path=tmp_path / "output.mkv",
            policy=policy,
            needs_video_transcode=True,
        )
        two_pass_ctx = TwoPassContext(passlogfile=tmp_path / "passlog")

        build_ffmpeg_command_pass1(plan, two_pass_ctx)

        # The function should set current_pass to 1
        assert two_pass_ctx.current_pass == 1
