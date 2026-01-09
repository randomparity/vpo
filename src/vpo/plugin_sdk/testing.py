"""Testing utilities for plugin development.

Provides fixtures, mocks, and helpers for testing plugins.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from vpo.db.models import FileInfo, TrackInfo
from vpo.executor.interface import ExecutorResult
from vpo.plugin.events import (
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
    TranscriptionCompletedEvent,
    TranscriptionRequestedEvent,
)
from vpo.policy.models import Plan

# ==============================================================================
# Mock Factories
# ==============================================================================


def mock_file_info(
    path: str | Path = "/test/video.mkv",
    filename: str = "video.mkv",
    extension: str = ".mkv",
    size_bytes: int = 1024 * 1024,
    container_format: str = "mkv",
    **kwargs: Any,
) -> FileInfo:
    """Create a mock FileInfo for testing.

    Args:
        path: File path.
        filename: File name.
        extension: File extension.
        size_bytes: File size.
        container_format: Container format.
        **kwargs: Additional FileInfo attributes.

    Returns:
        FileInfo instance.

    """
    return FileInfo(
        path=Path(path),
        filename=filename,
        directory=Path(path).parent,
        extension=extension,
        size_bytes=size_bytes,
        modified_at=datetime.now(timezone.utc),
        content_hash=kwargs.get("content_hash"),
        container_format=container_format,
        scanned_at=datetime.now(timezone.utc),
        scan_status="ok",
        scan_error=None,
        tracks=kwargs.get("tracks", []),
    )


def mock_track_info(
    index: int = 0,
    track_type: str = "video",
    codec: str = "h264",
    language: str | None = None,
    title: str | None = None,
    is_default: bool = False,
    is_forced: bool = False,
    **kwargs: Any,
) -> TrackInfo:
    """Create a mock TrackInfo for testing.

    Args:
        index: Track index.
        track_type: Type (video, audio, subtitle).
        codec: Codec name.
        language: Language code.
        title: Track title.
        is_default: Default flag.
        is_forced: Forced flag.
        **kwargs: Additional TrackInfo attributes.

    Returns:
        TrackInfo instance.

    """
    return TrackInfo(
        index=index,
        track_type=track_type,
        codec=codec,
        language=language,
        title=title,
        is_default=is_default,
        is_forced=is_forced,
        channels=kwargs.get("channels"),
        channel_layout=kwargs.get("channel_layout"),
        width=kwargs.get("width"),
        height=kwargs.get("height"),
        frame_rate=kwargs.get("frame_rate"),
    )


def mock_tracks(
    video: int = 1,
    audio: int = 2,
    subtitle: int = 1,
) -> list[TrackInfo]:
    """Create a list of mock tracks for testing.

    Args:
        video: Number of video tracks.
        audio: Number of audio tracks.
        subtitle: Number of subtitle tracks.

    Returns:
        List of TrackInfo instances.

    """
    tracks = []
    index = 0

    # Add video tracks
    for _ in range(video):
        tracks.append(
            mock_track_info(
                index=index,
                track_type="video",
                codec="h264",
                width=1920,
                height=1080,
            )
        )
        index += 1

    # Add audio tracks
    languages = ["eng", "jpn", "und"]
    for i in range(audio):
        tracks.append(
            mock_track_info(
                index=index,
                track_type="audio",
                codec="aac",
                language=languages[i % len(languages)],
                channels=2,
            )
        )
        index += 1

    # Add subtitle tracks
    for i in range(subtitle):
        tracks.append(
            mock_track_info(
                index=index,
                track_type="subtitle",
                codec="subrip",
                language=languages[i % len(languages)],
            )
        )
        index += 1

    return tracks


def mock_plan(
    file_path: str | Path = "/test/video.mkv",
    file_id: str = "test-uuid",
    policy_version: int = 1,
    actions: tuple = (),
    requires_remux: bool = False,
) -> Plan:
    """Create a mock Plan for testing.

    Args:
        file_path: File path.
        file_id: File UUID.
        policy_version: Policy version.
        actions: Tuple of PlannedAction.
        requires_remux: Whether plan requires remux.

    Returns:
        Plan instance.

    """
    return Plan(
        file_id=file_id,
        file_path=Path(file_path),
        policy_version=policy_version,
        actions=actions,
        requires_remux=requires_remux,
        created_at=datetime.now(timezone.utc),
    )


def mock_executor_result(
    success: bool = True,
    message: str = "Success",
    backup_path: Path | None = None,
) -> ExecutorResult:
    """Create a mock ExecutorResult for testing.

    Args:
        success: Success status.
        message: Result message.
        backup_path: Path to backup file.

    Returns:
        ExecutorResult instance.

    """
    return ExecutorResult(
        success=success,
        message=message,
        backup_path=backup_path,
    )


# ==============================================================================
# Event Factories
# ==============================================================================


def create_file_scanned_event(
    file_path: str | Path = "/test/video.mkv",
    file_info: FileInfo | None = None,
    tracks: list[TrackInfo] | None = None,
) -> FileScannedEvent:
    """Create a FileScannedEvent for testing.

    Args:
        file_path: Path to file.
        file_info: FileInfo or None to auto-create.
        tracks: List of tracks or None to auto-create.

    Returns:
        FileScannedEvent instance.

    """
    if file_info is None:
        file_info = mock_file_info(path=file_path)
    if tracks is None:
        tracks = mock_tracks()

    return FileScannedEvent(
        file_path=Path(file_path),
        file_info=file_info,
        tracks=tracks,
    )


def create_policy_evaluate_event(
    file_path: str | Path = "/test/video.mkv",
    file_info: FileInfo | None = None,
    policy: Any | None = None,
    plan: Plan | None = None,
) -> PolicyEvaluateEvent:
    """Create a PolicyEvaluateEvent for testing.

    Args:
        file_path: Path to file.
        file_info: FileInfo or None for mock.
        policy: PolicySchema or None for mock.
        plan: Plan for after_evaluate, None for before_evaluate.

    Returns:
        PolicyEvaluateEvent instance.

    """
    if file_info is None:
        file_info = mock_file_info(path=file_path)
    if policy is None:
        policy = MagicMock()

    return PolicyEvaluateEvent(
        file_path=Path(file_path),
        file_info=file_info,
        policy=policy,
        plan=plan,
    )


def create_plan_execute_event(
    plan: Plan | None = None,
    result: ExecutorResult | None = None,
    error: Exception | None = None,
) -> PlanExecuteEvent:
    """Create a PlanExecuteEvent for testing.

    Args:
        plan: Plan or None for mock.
        result: ExecutorResult for after_execute.
        error: Exception for execution_failed.

    Returns:
        PlanExecuteEvent instance.

    """
    if plan is None:
        plan = mock_plan()

    return PlanExecuteEvent(
        plan=plan,
        result=result,
        error=error,
    )


def create_transcription_requested_event(
    file_path: str | Path = "/test/video.mkv",
    track: TrackInfo | None = None,
    audio_data: bytes = b"\x00" * 1000,
    sample_rate: int = 16000,
    options: dict[str, Any] | None = None,
) -> TranscriptionRequestedEvent:
    """Create a TranscriptionRequestedEvent for testing.

    Args:
        file_path: Path to file.
        track: TrackInfo or None to auto-create.
        audio_data: Raw audio bytes.
        sample_rate: Audio sample rate in Hz.
        options: Transcription options dict.

    Returns:
        TranscriptionRequestedEvent instance.

    """
    if track is None:
        track = mock_track_info(index=1, track_type="audio", codec="aac")
    if options is None:
        options = {}

    return TranscriptionRequestedEvent(
        file_path=Path(file_path),
        track=track,
        audio_data=audio_data,
        sample_rate=sample_rate,
        options=options,
    )


def create_transcription_completed_event(
    file_path: str | Path = "/test/video.mkv",
    track_id: int = 1,
    result: Any | None = None,
) -> TranscriptionCompletedEvent:
    """Create a TranscriptionCompletedEvent for testing.

    Args:
        file_path: Path to file.
        track_id: Database track ID.
        result: TranscriptionResult or None for mock.

    Returns:
        TranscriptionCompletedEvent instance.

    """
    if result is None:
        result = MagicMock()
        result.detected_language = "eng"
        result.confidence_score = 0.95

    return TranscriptionCompletedEvent(
        file_path=Path(file_path),
        track_id=track_id,
        result=result,
    )


# ==============================================================================
# Test Base Class
# ==============================================================================


class PluginTestCase:
    """Base class for plugin test cases.

    Provides helper methods for creating test events and fixtures.

    Example:
        class TestMyPlugin(PluginTestCase):
            def test_file_scanned(self):
                plugin = MyPlugin()
                event = self.create_file_scanned_event()
                result = plugin.on_file_scanned(event)
                assert result is None

    """

    def create_file_scanned_event(
        self,
        file_path: str | Path = "/test/video.mkv",
        file_info: FileInfo | None = None,
        tracks: list[TrackInfo] | None = None,
    ) -> FileScannedEvent:
        """Create a FileScannedEvent for testing."""
        return create_file_scanned_event(
            file_path=file_path,
            file_info=file_info,
            tracks=tracks,
        )

    def create_policy_evaluate_event(
        self,
        file_path: str | Path = "/test/video.mkv",
        file_info: FileInfo | None = None,
        policy: Any | None = None,
        plan: Plan | None = None,
    ) -> PolicyEvaluateEvent:
        """Create a PolicyEvaluateEvent for testing."""
        return create_policy_evaluate_event(
            file_path=file_path,
            file_info=file_info,
            policy=policy,
            plan=plan,
        )

    def create_plan_execute_event(
        self,
        plan: Plan | None = None,
        result: ExecutorResult | None = None,
        error: Exception | None = None,
    ) -> PlanExecuteEvent:
        """Create a PlanExecuteEvent for testing."""
        return create_plan_execute_event(
            plan=plan,
            result=result,
            error=error,
        )

    def create_transcription_requested_event(
        self,
        file_path: str | Path = "/test/video.mkv",
        track: TrackInfo | None = None,
        audio_data: bytes = b"\x00" * 1000,
        sample_rate: int = 16000,
        options: dict[str, Any] | None = None,
    ) -> TranscriptionRequestedEvent:
        """Create a TranscriptionRequestedEvent for testing."""
        return create_transcription_requested_event(
            file_path=file_path,
            track=track,
            audio_data=audio_data,
            sample_rate=sample_rate,
            options=options,
        )

    def create_transcription_completed_event(
        self,
        file_path: str | Path = "/test/video.mkv",
        track_id: int = 1,
        result: Any | None = None,
    ) -> TranscriptionCompletedEvent:
        """Create a TranscriptionCompletedEvent for testing."""
        return create_transcription_completed_event(
            file_path=file_path,
            track_id=track_id,
            result=result,
        )


# ==============================================================================
# Pytest Fixtures (for import in conftest.py)
# ==============================================================================


@pytest.fixture
def mock_file_info_fixture() -> FileInfo:
    """Pytest fixture for mock FileInfo."""
    return mock_file_info()


@pytest.fixture
def mock_tracks_fixture() -> list[TrackInfo]:
    """Pytest fixture for mock tracks."""
    return mock_tracks()


@pytest.fixture
def mock_plan_fixture(tmp_path: Path) -> Plan:
    """Pytest fixture for mock Plan."""
    return mock_plan(file_path=tmp_path / "test.mkv")
