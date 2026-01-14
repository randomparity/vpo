"""Unit tests for FFmpeg synthesis executor."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vpo.db.models import TrackInfo
from vpo.policy.synthesis.exceptions import (
    SynthesisCancelledError,
)
from vpo.policy.synthesis.executor import (
    FFmpegSynthesisExecutor,
    SynthesisExecutionResult,
    _sigint_handler,
)
from vpo.policy.synthesis.models import (
    AudioCodec,
    SourceTrackSelection,
    SynthesisOperation,
    SynthesisPlan,
)


@pytest.fixture
def sample_track() -> TrackInfo:
    """Create a sample audio track."""
    return TrackInfo(
        index=1,
        track_type="audio",
        codec="truehd",
        language="eng",
        title="TrueHD 7.1",
        is_default=True,
        is_forced=False,
        channels=8,
        channel_layout="7.1",
    )


@pytest.fixture
def sample_operation(sample_track: TrackInfo) -> SynthesisOperation:
    """Create a sample synthesis operation."""
    return SynthesisOperation(
        definition_name="eac3_51",
        source_track=SourceTrackSelection(
            track_index=1,
            track_info=sample_track,
            score=100,
            is_fallback=False,
            match_reasons=("language_match",),
        ),
        target_codec=AudioCodec.EAC3,
        target_channels=6,
        target_bitrate=640000,
        target_title="EAC3 5.1",
        target_language="eng",
        target_position=2,
        downmix_filter="pan=5.1|FL=FL|FR=FR|FC=FC|LFE=LFE|BL=0.707*SL+0.707*BL|BR=0.707*SR+0.707*BR",
    )


@pytest.fixture
def sample_plan(
    sample_operation: SynthesisOperation, sample_track: TrackInfo, tmp_path: Path
) -> SynthesisPlan:
    """Create a sample synthesis plan."""
    test_file = tmp_path / "test.mkv"
    test_file.write_bytes(b"test content")

    return SynthesisPlan(
        file_id="test-file-id-1234",
        file_path=test_file,
        operations=(sample_operation,),
        skipped=(),
        final_track_order=(),
        audio_tracks=(sample_track,),
    )


class TestSynthesisExecutionResult:
    """Tests for SynthesisExecutionResult dataclass."""

    def test_successful_result(self, tmp_path: Path) -> None:
        """Test creating a successful result."""
        result = SynthesisExecutionResult(
            success=True,
            output_path=tmp_path / "output.mkv",
            tracks_created=2,
            message="Success",
        )
        assert result.success is True
        assert result.tracks_created == 2

    def test_failed_result_with_errors(self) -> None:
        """Test creating a failed result with errors."""
        result = SynthesisExecutionResult(
            success=False,
            message="Transcoding failed",
            errors=["FFmpeg error", "Invalid codec"],
        )
        assert result.success is False
        assert len(result.errors) == 2


class TestFFmpegSynthesisExecutor:
    """Tests for FFmpegSynthesisExecutor class."""

    def test_dry_run_returns_success(self, sample_plan: SynthesisPlan) -> None:
        """Test that dry run returns success without modifying files."""
        executor = FFmpegSynthesisExecutor()

        result = executor.execute(sample_plan, dry_run=True)

        assert result.success is True
        assert "Would create 1" in result.message
        assert result.tracks_created == 1

    def test_empty_plan_returns_success(self, tmp_path: Path) -> None:
        """Test that empty plan returns success immediately."""
        test_file = tmp_path / "test.mkv"
        test_file.write_bytes(b"test")

        plan = SynthesisPlan(
            file_id="test-id",
            file_path=test_file,
            operations=(),
            skipped=(),
            final_track_order=(),
        )
        executor = FFmpegSynthesisExecutor()

        result = executor.execute(plan)

        assert result.success is True
        assert "No synthesis operations" in result.message

    def test_build_ffmpeg_args_includes_encoder(
        self,
        sample_operation: SynthesisOperation,
        sample_track: TrackInfo,
        tmp_path: Path,
    ) -> None:
        """Test that FFmpeg args include correct encoder."""
        executor = FFmpegSynthesisExecutor(ffmpeg_path=Path("/usr/bin/ffmpeg"))
        input_path = tmp_path / "input.mkv"
        output_path = tmp_path / "output.eac3"
        audio_tracks = (sample_track,)

        args = executor._build_ffmpeg_args(
            input_path, sample_operation, output_path, audio_tracks
        )

        assert "/usr/bin/ffmpeg" in args
        assert "-c:a" in args
        assert "eac3" in args  # encoder name

    def test_build_ffmpeg_args_includes_downmix_filter(
        self,
        sample_operation: SynthesisOperation,
        sample_track: TrackInfo,
        tmp_path: Path,
    ) -> None:
        """Test that FFmpeg args include downmix filter when present."""
        executor = FFmpegSynthesisExecutor(ffmpeg_path=Path("/usr/bin/ffmpeg"))
        input_path = tmp_path / "input.mkv"
        output_path = tmp_path / "output.eac3"
        audio_tracks = (sample_track,)

        args = executor._build_ffmpeg_args(
            input_path, sample_operation, output_path, audio_tracks
        )

        assert "-af" in args
        # Should have the filter after -af
        af_idx = args.index("-af")
        assert "pan=5.1" in args[af_idx + 1]

    def test_build_ffmpeg_args_includes_bitrate(
        self,
        sample_operation: SynthesisOperation,
        sample_track: TrackInfo,
        tmp_path: Path,
    ) -> None:
        """Test that FFmpeg args include bitrate."""
        executor = FFmpegSynthesisExecutor(ffmpeg_path=Path("/usr/bin/ffmpeg"))
        input_path = tmp_path / "input.mkv"
        output_path = tmp_path / "output.eac3"
        audio_tracks = (sample_track,)

        args = executor._build_ffmpeg_args(
            input_path, sample_operation, output_path, audio_tracks
        )

        assert "-b:a" in args
        assert "640000" in args

    def test_build_mkvmerge_args_includes_original(
        self, sample_operation: SynthesisOperation, tmp_path: Path
    ) -> None:
        """Test that mkvmerge args include original file."""
        executor = FFmpegSynthesisExecutor(mkvmerge_path=Path("/usr/bin/mkvmerge"))
        input_path = tmp_path / "input.mkv"
        audio_path = tmp_path / "synth.eac3"
        output_path = tmp_path / "output.mkv"

        args = executor._build_mkvmerge_args(
            input_path,
            [(sample_operation, audio_path)],
            output_path,
        )

        assert "/usr/bin/mkvmerge" in args
        assert str(input_path) in args
        assert str(audio_path) in args
        assert "-o" in args

    def test_build_mkvmerge_args_includes_language(
        self, sample_operation: SynthesisOperation, tmp_path: Path
    ) -> None:
        """Test that mkvmerge args include language metadata."""
        executor = FFmpegSynthesisExecutor(mkvmerge_path=Path("/usr/bin/mkvmerge"))
        input_path = tmp_path / "input.mkv"
        audio_path = tmp_path / "synth.eac3"
        output_path = tmp_path / "output.mkv"

        args = executor._build_mkvmerge_args(
            input_path,
            [(sample_operation, audio_path)],
            output_path,
        )

        assert "--language" in args
        assert "0:eng" in args


class TestRestoreFromBackup:
    """Tests for backup/restore functionality."""

    def test_restore_copies_backup_to_original(self, tmp_path: Path) -> None:
        """Test that restore replaces original with backup content."""
        original = tmp_path / "test.mkv"
        backup = tmp_path / "test.bak.mkv"

        original.write_text("modified content")
        backup.write_text("original content")

        executor = FFmpegSynthesisExecutor()
        result = executor._restore_from_backup(original, backup)

        assert result is True
        assert original.read_text() == "original content"

    def test_restore_returns_false_if_backup_missing(self, tmp_path: Path) -> None:
        """Test that restore returns False when backup doesn't exist."""
        original = tmp_path / "test.mkv"
        backup = tmp_path / "test.bak.mkv"

        original.write_text("content")
        # backup doesn't exist

        executor = FFmpegSynthesisExecutor()
        result = executor._restore_from_backup(original, backup)

        assert result is False


class TestCleanupTempFiles:
    """Tests for temp file cleanup."""

    def test_cleanup_removes_transcoded_files(self, tmp_path: Path) -> None:
        """Test that cleanup removes transcoded audio files."""
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        audio_file = work_dir / "synth.eac3"
        audio_file.write_bytes(b"audio data")

        executor = FFmpegSynthesisExecutor()
        mock_op = MagicMock()
        executor._cleanup_temp_files(
            work_dir, [(mock_op, audio_file)], keep_on_error=False
        )

        assert not audio_file.exists()

    def test_cleanup_keeps_files_on_error(self, tmp_path: Path) -> None:
        """Test that cleanup keeps files when keep_on_error is True."""
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        audio_file = work_dir / "synth.eac3"
        audio_file.write_bytes(b"audio data")

        executor = FFmpegSynthesisExecutor()
        mock_op = MagicMock()
        executor._cleanup_temp_files(
            work_dir, [(mock_op, audio_file)], keep_on_error=True
        )

        assert audio_file.exists()


class TestSigintHandler:
    """Tests for SIGINT handler."""

    def test_handler_raises_cancelled_error(self) -> None:
        """Test that SIGINT handler raises SynthesisCancelledError."""
        import signal

        with pytest.raises(SynthesisCancelledError):
            with _sigint_handler():
                # Simulate SIGINT
                signal.raise_signal(signal.SIGINT)

    def test_handler_restores_original_handler(self) -> None:
        """Test that original SIGINT handler is restored after context."""
        import signal

        original_handler = signal.getsignal(signal.SIGINT)

        try:
            with _sigint_handler():
                pass
        except SynthesisCancelledError:
            pass

        # Handler should be restored (may be different from original if nested)
        current_handler = signal.getsignal(signal.SIGINT)
        assert current_handler == original_handler

    def test_handler_skips_setup_in_non_main_thread(self) -> None:
        """Test that SIGINT handler setup is skipped in non-main thread.

        When running in a background thread (e.g., from job system),
        signal handlers cannot be set. The context manager should
        gracefully skip setup rather than raising ValueError.
        """
        import threading

        result: list[str] = []

        def run_in_thread() -> None:
            # This should NOT raise ValueError when in non-main thread
            with _sigint_handler():
                result.append("completed")

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()

        # Should have completed successfully without error
        assert result == ["completed"]
