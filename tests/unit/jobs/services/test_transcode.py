"""Tests for TranscodeJobService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.types import (
    Job,
    JobStatus,
    JobType,
    TrackInfo,
)
from vpo.jobs.services.transcode import (
    TranscodeJobResult,
    TranscodeJobService,
)


@pytest.fixture
def mock_introspector():
    """Create a mock introspector."""
    introspector = MagicMock()
    # Create a mock result that has the success property and duration_seconds property
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.container_format = "matroska"
    mock_result.duration_seconds = 3600.0  # Now using duration_seconds property
    mock_result.tracks = [
        TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            language="und",
            title=None,
            is_default=True,
            is_forced=False,
            width=1920,
            height=1080,
            duration_seconds=3600.0,  # Track-level duration
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
            title=None,
            is_default=True,
            is_forced=False,
        ),
    ]
    mock_result.error = None
    introspector.get_file_info.return_value = mock_result  # Changed from introspect
    return introspector


@pytest.fixture
def sample_job():
    """Create a sample transcode job."""
    return Job(
        id="test-job-123",
        file_id=None,
        file_path="/test/input.mkv",
        job_type=JobType.TRANSCODE,
        status=JobStatus.RUNNING,
        priority=100,
        policy_name="test-policy",
        policy_json='{"target_video_codec": "hevc", "target_crf": 20}',
        progress_percent=0.0,
        progress_json=None,
        created_at="2024-01-01T00:00:00+00:00",
        started_at="2024-01-01T00:00:00+00:00",
    )


class TestTranscodeJobResult:
    """Tests for TranscodeJobResult dataclass."""

    def test_success_result(self):
        """Success result has output path."""
        result = TranscodeJobResult(success=True, output_path="/output/file.mkv")
        assert result.success is True
        assert result.output_path == "/output/file.mkv"
        assert result.error_message is None

    def test_failure_result(self):
        """Failure result has error message."""
        result = TranscodeJobResult(success=False, error_message="Something failed")
        assert result.success is False
        assert result.output_path is None
        assert result.error_message == "Something failed"


class TestTranscodeJobServiceParsePolicy:
    """Tests for policy parsing."""

    def test_parse_valid_policy(self, mock_introspector):
        """Valid JSON parses to TranscodePolicyConfig."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json='{"target_video_codec": "hevc", "target_crf": 20}',
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        policy, policy_data, error = service._parse_policy(job, None)

        assert error is None
        assert policy is not None
        assert policy.target_video_codec == "hevc"
        assert policy.target_crf == 20

    def test_parse_empty_policy(self, mock_introspector):
        """Empty JSON uses defaults."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="{}",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        policy, policy_data, error = service._parse_policy(job, None)

        assert error is None
        assert policy is not None
        assert policy.target_video_codec is None
        assert policy.audio_transcode_to == "aac"  # default

    def test_parse_invalid_json(self, mock_introspector):
        """Invalid JSON returns error."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="not valid json",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        policy, policy_data, error = service._parse_policy(job, None)

        assert error is not None
        assert "Invalid policy JSON" in error
        assert policy is None

    def test_parse_legacy_audio_bitrate_key(self, mock_introspector):
        """Legacy 'audio_bitrate' key is supported."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json='{"audio_bitrate": "256k"}',
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        policy, policy_data, error = service._parse_policy(job, None)

        assert error is None
        assert policy.audio_transcode_bitrate == "256k"


class TestTranscodeJobServiceDetermineOutputPath:
    """Tests for output path determination."""

    def test_with_output_dir(self):
        """Uses specified output_dir."""
        input_path = Path("/input/video.mkv")
        policy_data = {"output_dir": "/output"}

        result = TranscodeJobService._determine_output_path(input_path, policy_data)

        assert result == Path("/output/video.mkv")

    def test_default_adds_transcoded_suffix(self):
        """Adds .transcoded suffix by default."""
        input_path = Path("/input/video.mkv")
        policy_data = {}

        result = TranscodeJobService._determine_output_path(input_path, policy_data)

        assert result == Path("/input/video.transcoded.mkv")


class TestTranscodeJobServiceProcess:
    """Tests for the main process method."""

    def test_process_file_not_found(self, mock_introspector):
        """Returns error when input file doesn't exist."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/nonexistent/file.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="{}",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        result = service.process(job)

        assert result.success is False
        assert "not found" in result.error_message

    def test_process_introspection_failure(self, mock_introspector):
        """Returns error when introspection fails."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "ffprobe failed"
        mock_introspector.get_file_info.return_value = mock_result
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test/input.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="{}",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        with patch("pathlib.Path.exists", return_value=True):
            result = service.process(job)

        assert result.success is False
        assert "Introspection failed" in result.error_message

    def test_process_no_video_track(self, mock_introspector):
        """Returns error when no video track found."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.container_format = "matroska"
        mock_result.duration_seconds = 3600.0
        mock_result.tracks = [
            TrackInfo(
                index=0,
                track_type="audio",
                codec="aac",
                language="eng",
                title=None,
                is_default=True,
                is_forced=False,
            ),
        ]
        mock_result.error = None
        mock_introspector.get_file_info.return_value = mock_result
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test/audio-only.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json="{}",
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        with patch("pathlib.Path.exists", return_value=True):
            result = service.process(job)

        assert result.success is False
        assert "No video track found" in result.error_message

    def test_process_none_policy_json(self, mock_introspector):
        """None policy_json uses empty dict and defaults."""
        service = TranscodeJobService(introspector=mock_introspector)
        job = Job(
            id="test",
            file_id=None,
            file_path="/test/input.mkv",
            job_type=JobType.TRANSCODE,
            status=JobStatus.RUNNING,
            priority=100,
            policy_name=None,
            policy_json=None,  # None instead of JSON string
            progress_percent=0.0,
            progress_json=None,
            created_at="2024-01-01T00:00:00+00:00",
            started_at="2024-01-01T00:00:00+00:00",
        )

        # Verify policy parsing handles None
        policy, policy_data, error = service._parse_policy(job, None)

        assert error is None
        assert policy is not None
        assert policy_data == {}
        assert policy.audio_transcode_to == "aac"  # default value

    def test_process_transcode_execution_failure(self, mock_introspector, sample_job):
        """Returns error when transcode execution fails."""
        service = TranscodeJobService(introspector=mock_introspector)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.transcode.TranscodeExecutor") as mock_executor_cls,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=False,
                output_path=None,
                error_message="FFmpeg exited with code 1",
            )

            result = service.process(sample_job)

        assert result.success is False
        assert result.error_message is not None
        assert "FFmpeg exited with code 1" in result.error_message

    def test_process_success_returns_output_path(self, mock_introspector, sample_job):
        """Successful transcode returns output path."""
        service = TranscodeJobService(introspector=mock_introspector)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.transcode.TranscodeExecutor") as mock_executor_cls,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            mock_executor.execute.return_value = MagicMock(
                success=True,
                output_path=Path("/test/input.transcoded.mkv"),
                error_message=None,
            )

            result = service.process(sample_job)

        assert result.success is True
        assert result.output_path is not None
        assert "transcoded" in result.output_path

    def test_process_executor_returns_none_uses_planned_path(
        self, mock_introspector, sample_job
    ):
        """When executor returns success with no output_path, uses planned path."""
        service = TranscodeJobService(introspector=mock_introspector)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("vpo.jobs.services.transcode.TranscodeExecutor") as mock_executor_cls,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor
            mock_executor.create_plan.return_value = MagicMock()
            # Executor returns success but no explicit output_path
            mock_executor.execute.return_value = MagicMock(
                success=True,
                output_path=None,
                error_message=None,
            )

            result = service.process(sample_job)

        assert result.success is True
        # Falls back to planned output path (input with .transcoded suffix)
        assert result.output_path is not None
        assert "transcoded" in result.output_path
