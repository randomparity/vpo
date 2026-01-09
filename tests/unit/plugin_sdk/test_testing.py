"""Unit tests for plugin_sdk testing module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from vpo.db.models import FileInfo, TrackInfo
from vpo.executor.interface import ExecutorResult
from vpo.plugin.events import (
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)
from vpo.plugin_sdk.testing import (
    PluginTestCase,
    create_file_scanned_event,
    create_plan_execute_event,
    create_policy_evaluate_event,
    mock_executor_result,
    mock_file_info,
    mock_plan,
    mock_track_info,
    mock_tracks,
)
from vpo.policy.types import Plan


class TestMockFileInfo:
    """Tests for mock_file_info factory."""

    def test_returns_file_info(self) -> None:
        """Returns a FileInfo instance."""
        result = mock_file_info()
        assert isinstance(result, FileInfo)

    def test_default_values(self) -> None:
        """Default values are sensible."""
        result = mock_file_info()
        assert result.path == Path("/test/video.mkv")
        assert result.filename == "video.mkv"
        assert result.extension == ".mkv"
        assert result.container_format == "mkv"
        assert result.size_bytes == 1024 * 1024

    def test_custom_path(self) -> None:
        """Can specify custom path."""
        result = mock_file_info(path="/custom/movie.mp4")
        assert result.path == Path("/custom/movie.mp4")

    def test_directory_derived_from_path(self) -> None:
        """directory is derived from path parameter."""
        result = mock_file_info(path="/media/movies/test.mkv")
        assert result.directory == Path("/media/movies")

    def test_content_hash_passthrough(self) -> None:
        """content_hash kwarg passed to FileInfo."""
        result = mock_file_info(content_hash="abc123")
        assert result.content_hash == "abc123"

    def test_tracks_passthrough(self) -> None:
        """tracks kwarg passed to FileInfo."""
        tracks = [mock_track_info()]
        result = mock_file_info(tracks=tracks)
        assert result.tracks == tracks


class TestMockTrackInfo:
    """Tests for mock_track_info factory."""

    def test_returns_track_info(self) -> None:
        """Returns a TrackInfo instance."""
        result = mock_track_info()
        assert isinstance(result, TrackInfo)

    def test_default_values(self) -> None:
        """Default values are sensible."""
        result = mock_track_info()
        assert result.index == 0
        assert result.track_type == "video"
        assert result.codec == "h264"

    def test_custom_values(self) -> None:
        """Can specify custom values."""
        result = mock_track_info(
            index=2,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        assert result.index == 2
        assert result.track_type == "audio"
        assert result.codec == "aac"
        assert result.language == "eng"

    def test_channels_passthrough(self) -> None:
        """channels kwarg passed to TrackInfo."""
        result = mock_track_info(channels=6)
        assert result.channels == 6

    def test_width_height_passthrough(self) -> None:
        """width/height kwargs passed to TrackInfo."""
        result = mock_track_info(width=1920, height=1080)
        assert result.width == 1920
        assert result.height == 1080

    def test_frame_rate_passthrough(self) -> None:
        """frame_rate kwarg passed to TrackInfo."""
        result = mock_track_info(frame_rate="24000/1001")
        assert result.frame_rate == "24000/1001"

    def test_channel_layout_passthrough(self) -> None:
        """channel_layout kwarg passed to TrackInfo."""
        result = mock_track_info(channel_layout="5.1")
        assert result.channel_layout == "5.1"


class TestMockTracks:
    """Tests for mock_tracks factory."""

    def test_returns_list_of_tracks(self) -> None:
        """Returns list of TrackInfo."""
        result = mock_tracks()
        assert isinstance(result, list)
        assert all(isinstance(t, TrackInfo) for t in result)

    def test_default_counts(self) -> None:
        """Default is 1 video, 2 audio, 1 subtitle."""
        result = mock_tracks()
        video_count = sum(1 for t in result if t.track_type == "video")
        audio_count = sum(1 for t in result if t.track_type == "audio")
        subtitle_count = sum(1 for t in result if t.track_type == "subtitle")
        assert video_count == 1
        assert audio_count == 2
        assert subtitle_count == 1

    def test_custom_counts(self) -> None:
        """Can specify custom counts."""
        result = mock_tracks(video=2, audio=3, subtitle=4)
        video_count = sum(1 for t in result if t.track_type == "video")
        audio_count = sum(1 for t in result if t.track_type == "audio")
        subtitle_count = sum(1 for t in result if t.track_type == "subtitle")
        assert video_count == 2
        assert audio_count == 3
        assert subtitle_count == 4

    def test_audio_languages_cycle(self) -> None:
        """Audio tracks cycle through eng, jpn, und."""
        result = mock_tracks(video=0, audio=6, subtitle=0)
        languages = [t.language for t in result]
        assert languages == ["eng", "jpn", "und", "eng", "jpn", "und"]

    def test_track_indices_sequential(self) -> None:
        """Track indices are sequential across types."""
        result = mock_tracks(video=1, audio=2, subtitle=1)
        indices = [t.index for t in result]
        assert indices == [0, 1, 2, 3]


class TestMockPlan:
    """Tests for mock_plan factory."""

    def test_returns_plan(self) -> None:
        """Returns a Plan instance."""
        result = mock_plan()
        assert isinstance(result, Plan)

    def test_default_values(self) -> None:
        """Default values are sensible."""
        result = mock_plan()
        assert result.file_path == Path("/test/video.mkv")
        assert result.file_id == "test-uuid"
        assert result.policy_version == 1

    def test_requires_remux_default_false(self) -> None:
        """requires_remux defaults to False."""
        result = mock_plan()
        assert result.requires_remux is False

    def test_actions_default_empty_tuple(self) -> None:
        """actions defaults to empty tuple."""
        result = mock_plan()
        assert result.actions == ()

    def test_created_at_set(self) -> None:
        """created_at is set to current time."""
        before = datetime.now(timezone.utc)
        result = mock_plan()
        after = datetime.now(timezone.utc)
        assert before <= result.created_at <= after


class TestMockExecutorResult:
    """Tests for mock_executor_result factory."""

    def test_returns_executor_result(self) -> None:
        """Returns ExecutorResult instance."""
        result = mock_executor_result()
        assert isinstance(result, ExecutorResult)

    def test_default_success(self) -> None:
        """Defaults to success=True."""
        result = mock_executor_result()
        assert result.success is True
        assert result.message == "Success"

    def test_custom_values(self) -> None:
        """Can specify custom values."""
        result = mock_executor_result(
            success=False,
            message="Failed",
            backup_path=Path("/backup/file.mkv"),
        )
        assert result.success is False
        assert result.message == "Failed"
        assert result.backup_path == Path("/backup/file.mkv")


class TestCreateFileScannedEvent:
    """Tests for create_file_scanned_event factory."""

    def test_returns_event(self) -> None:
        """Returns FileScannedEvent instance."""
        result = create_file_scanned_event()
        assert isinstance(result, FileScannedEvent)

    def test_default_file_info_created(self) -> None:
        """Creates default file_info if not provided."""
        result = create_file_scanned_event()
        assert result.file_info is not None
        assert isinstance(result.file_info, FileInfo)

    def test_default_tracks_created(self) -> None:
        """Creates default tracks if not provided."""
        result = create_file_scanned_event()
        assert result.tracks is not None
        assert len(result.tracks) > 0

    def test_custom_file_info(self) -> None:
        """Can provide custom file_info."""
        custom_info = mock_file_info(path="/custom/path.mkv")
        result = create_file_scanned_event(file_info=custom_info)
        assert result.file_info.path == Path("/custom/path.mkv")

    def test_custom_tracks(self) -> None:
        """Can provide custom tracks."""
        custom_tracks = [mock_track_info(index=99)]
        result = create_file_scanned_event(tracks=custom_tracks)
        assert result.tracks[0].index == 99


class TestCreatePolicyEvaluateEvent:
    """Tests for create_policy_evaluate_event factory."""

    def test_returns_event(self) -> None:
        """Returns PolicyEvaluateEvent instance."""
        result = create_policy_evaluate_event()
        assert isinstance(result, PolicyEvaluateEvent)

    def test_default_file_info_created(self) -> None:
        """Creates default file_info if not provided."""
        result = create_policy_evaluate_event()
        assert result.file_info is not None

    def test_default_policy_is_mock(self) -> None:
        """Creates mock policy if not provided."""
        result = create_policy_evaluate_event()
        assert result.policy is not None

    def test_plan_can_be_provided(self) -> None:
        """Can provide plan for after_evaluate."""
        plan = mock_plan()
        result = create_policy_evaluate_event(plan=plan)
        assert result.plan is plan


class TestCreatePlanExecuteEvent:
    """Tests for create_plan_execute_event factory."""

    def test_returns_event(self) -> None:
        """Returns PlanExecuteEvent instance."""
        result = create_plan_execute_event()
        assert isinstance(result, PlanExecuteEvent)

    def test_default_plan_created(self) -> None:
        """Creates default plan if not provided."""
        result = create_plan_execute_event()
        assert result.plan is not None

    def test_result_can_be_provided(self) -> None:
        """Can provide result for after_execute."""
        executor_result = mock_executor_result()
        result = create_plan_execute_event(result=executor_result)
        assert result.result is executor_result

    def test_error_can_be_provided(self) -> None:
        """Can provide error for execution_failed."""
        error = ValueError("Test error")
        result = create_plan_execute_event(error=error)
        assert result.error is error


class TestPluginTestCase:
    """Tests for PluginTestCase base class."""

    def test_create_file_scanned_event_method(self) -> None:
        """create_file_scanned_event delegates to module function."""
        test_case = PluginTestCase()
        result = test_case.create_file_scanned_event()
        assert isinstance(result, FileScannedEvent)

    def test_create_policy_evaluate_event_method(self) -> None:
        """create_policy_evaluate_event delegates to module function."""
        test_case = PluginTestCase()
        result = test_case.create_policy_evaluate_event()
        assert isinstance(result, PolicyEvaluateEvent)

    def test_create_plan_execute_event_method(self) -> None:
        """create_plan_execute_event delegates to module function."""
        test_case = PluginTestCase()
        result = test_case.create_plan_execute_event()
        assert isinstance(result, PlanExecuteEvent)

    def test_methods_accept_same_args(self) -> None:
        """Methods accept same arguments as module functions."""
        test_case = PluginTestCase()

        # Test with custom arguments
        event = test_case.create_file_scanned_event(file_path="/custom/path.mkv")
        assert event.file_path == Path("/custom/path.mkv")
