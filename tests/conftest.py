"""Shared test fixtures for Video Policy Orchestrator."""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.db.schema import create_schema


@pytest.fixture
def sample_videos_dir() -> Path:
    """Return the path to the sample videos fixture directory."""
    return Path(__file__).parent / "fixtures" / "sample_videos"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test isolation."""
    dir_path = tempfile.mkdtemp()
    yield Path(dir_path)
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_db(temp_dir: Path) -> Path:
    """Create a temporary database path."""
    return temp_dir / "test_library.db"


@pytest.fixture
def temp_video_dir(temp_dir: Path) -> Path:
    """Create a temporary directory with sample video files."""
    video_dir = temp_dir / "videos"
    video_dir.mkdir()

    # Create some test video files
    (video_dir / "movie.mkv").touch()
    (video_dir / "show.mp4").touch()

    # Create nested directory
    nested = video_dir / "nested"
    nested.mkdir()
    (nested / "episode.mkv").touch()

    # Create hidden directory (should be skipped)
    hidden = video_dir / ".hidden"
    hidden.mkdir()
    (hidden / "secret.mkv").touch()

    return video_dir


@pytest.fixture
def default_extensions() -> list[str]:
    """Return the default video extensions."""
    return ["mkv", "mp4", "avi", "webm", "m4v", "mov"]


@pytest.fixture
def ffprobe_fixtures_dir() -> Path:
    """Return the path to the ffprobe fixtures directory."""
    return Path(__file__).parent / "fixtures" / "ffprobe"


def load_ffprobe_fixture(name: str) -> dict:
    """Load an ffprobe JSON fixture by name.

    Args:
        name: Name of the fixture file (without .json extension).

    Returns:
        Parsed JSON data from the fixture.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "ffprobe" / f"{name}.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def simple_single_track_fixture() -> dict:
    """Load the simple single track ffprobe fixture."""
    return load_ffprobe_fixture("simple_single_track")


@pytest.fixture
def multi_audio_fixture() -> dict:
    """Load the multi-audio ffprobe fixture."""
    return load_ffprobe_fixture("multi_audio")


@pytest.fixture
def subtitle_heavy_fixture() -> dict:
    """Load the subtitle-heavy ffprobe fixture."""
    return load_ffprobe_fixture("subtitle_heavy")


@pytest.fixture
def edge_case_missing_metadata_fixture() -> dict:
    """Load the edge case missing metadata ffprobe fixture."""
    return load_ffprobe_fixture("edge_case_missing_metadata")


@pytest.fixture(autouse=True)
def vpo_initialized(temp_dir: Path):
    """Automatically set up VPO as initialized for all tests.

    This fixture creates a minimal config.toml in a temporary VPO data
    directory and sets VPO_DATA_DIR to point to it. This ensures all
    CLI commands pass the initialization check.

    The fixture is autouse=True so it applies to all tests automatically.
    """
    vpo_data_dir = temp_dir / ".vpo"
    vpo_data_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal config.toml
    config_content = """\
[logging]
level = "info"
"""
    (vpo_data_dir / "config.toml").write_text(config_content)

    # Create logs directory (expected by default config)
    (vpo_data_dir / "logs").mkdir(exist_ok=True)

    # Set the environment variable for this test
    with patch.dict(os.environ, {"VPO_DATA_DIR": str(vpo_data_dir)}):
        yield vpo_data_dir


@pytest.fixture(autouse=True)
def _isolate_logging():
    """Isolate logging state between tests.

    VPO's CLI uses module-level flags (_logging_configured, _startup_logged)
    that persist across CliRunner invocations within a pytest session.  The
    first invocation configures a StreamHandler on the root logger; subsequent
    invocations skip configuration, leaving a stale handler that writes to a
    previous CliRunner's stderr stream.

    On Python 3.10-3.12 this causes logging output to contaminate
    CliRunner's result.output, breaking JSON parsing.

    This fixture resets the flags and saves/restores root logger state so
    no test's logging configuration leaks into the next test.
    """
    import vpo.cli as cli_module

    cli_module._logging_configured = False
    cli_module._startup_logged = False

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level

    yield

    root.handlers[:] = original_handlers
    root.setLevel(original_level)
    cli_module._logging_configured = False
    cli_module._startup_logged = False


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """Create an in-memory database with schema for testing.

    This is a shared fixture for any tests that need a database connection.
    The database is created fresh for each test and uses the full schema.

    Yields:
        sqlite3.Connection: An in-memory database connection with schema.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    yield conn
    conn.close()


# =============================================================================
# Transcode Testing Fixtures
# =============================================================================


@pytest.fixture
def mock_ffmpeg():
    """Mock require_tool to return a fake ffmpeg path.

    Use this fixture when testing FFmpeg command building functions
    without actually requiring FFmpeg to be installed.

    Yields:
        MagicMock: The patched require_tool function.
    """
    with patch("vpo.executor.transcode.command.require_tool") as mock_require:
        mock_require.return_value = Path("/usr/bin/ffmpeg")
        yield mock_require


@pytest.fixture
def make_transcode_plan():
    """Factory for creating TranscodePlan objects with sensible defaults.

    Returns a callable that creates TranscodePlan instances. All parameters
    have defaults, so you can create minimal plans for simple tests or
    override specific fields for edge cases.

    Returns:
        Callable: Factory function that creates TranscodePlan instances.

    Example:
        def test_something(make_transcode_plan):
            plan = make_transcode_plan(needs_video_transcode=True)
            assert plan.needs_any_transcode is True
    """
    from vpo.executor.transcode import TranscodePlan
    from vpo.policy.types import TranscodePolicyConfig

    def _make_plan(
        input_path: Path | str = Path("/input.mkv"),
        output_path: Path | str = Path("/output.mkv"),
        policy: TranscodePolicyConfig | None = None,
        needs_video_transcode: bool = False,
        needs_video_scale: bool = False,
        target_width: int | None = None,
        target_height: int | None = None,
        video_codec: str | None = None,
        video_width: int | None = None,
        video_height: int | None = None,
        **kwargs,
    ) -> TranscodePlan:
        return TranscodePlan(
            input_path=Path(input_path) if isinstance(input_path, str) else input_path,
            output_path=(
                Path(output_path) if isinstance(output_path, str) else output_path
            ),
            policy=policy or TranscodePolicyConfig(),
            needs_video_transcode=needs_video_transcode,
            needs_video_scale=needs_video_scale,
            target_width=target_width,
            target_height=target_height,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            **kwargs,
        )

    return _make_plan


# =============================================================================
# Domain Model Factories
# =============================================================================


@pytest.fixture
def make_track_info():
    """Factory for creating TrackInfo objects with sensible defaults.

    Returns a callable that creates TrackInfo instances. All parameters
    have defaults except `index` and `track_type`.

    Returns:
        Callable: Factory function that creates TrackInfo instances.

    Example:
        def test_audio_track(make_track_info):
            track = make_track_info(index=0, track_type="audio", channels=6)
            assert track.channels == 6
    """
    from vpo.db.types import TrackInfo

    def _make_track(
        index: int = 0,
        track_type: str = "video",
        id: int | None = None,
        codec: str | None = None,
        language: str | None = None,
        title: str | None = None,
        is_default: bool = False,
        is_forced: bool = False,
        channels: int | None = None,
        channel_layout: str | None = None,
        width: int | None = None,
        height: int | None = None,
        frame_rate: str | None = None,
        color_transfer: str | None = None,
        color_primaries: str | None = None,
        color_space: str | None = None,
        color_range: str | None = None,
        duration_seconds: float | None = None,
    ) -> TrackInfo:
        return TrackInfo(
            index=index,
            track_type=track_type,
            id=id,
            codec=codec,
            language=language,
            title=title,
            is_default=is_default,
            is_forced=is_forced,
            channels=channels,
            channel_layout=channel_layout,
            width=width,
            height=height,
            frame_rate=frame_rate,
            color_transfer=color_transfer,
            color_primaries=color_primaries,
            color_space=color_space,
            color_range=color_range,
            duration_seconds=duration_seconds,
        )

    return _make_track


@pytest.fixture
def make_file_info(make_track_info):
    """Factory for creating FileInfo objects with sensible defaults.

    Returns a callable that creates FileInfo instances with optional tracks.

    Returns:
        Callable: Factory function that creates FileInfo instances.

    Example:
        def test_file_with_tracks(make_file_info):
            file_info = make_file_info(
                path=Path("/videos/movie.mkv"),
                tracks=[{"track_type": "audio", "codec": "aac"}]
            )
            assert len(file_info.tracks) == 1
    """
    from datetime import datetime, timezone

    from vpo.db.types import FileInfo

    def _make_file(
        path: Path | str = Path("/videos/movie.mkv"),
        filename: str | None = None,
        directory: Path | str | None = None,
        extension: str | None = None,
        size_bytes: int = 1024 * 1024 * 100,  # 100 MB
        modified_at: datetime | None = None,
        content_hash: str | None = None,
        container_format: str | None = "mkv",
        scanned_at: datetime | None = None,
        scan_status: str = "ok",
        scan_error: str | None = None,
        tracks: list[dict] | None = None,
    ) -> FileInfo:
        if isinstance(path, str):
            path = Path(path)

        # Derive defaults from path if not provided
        if filename is None:
            filename = path.name
        if directory is None:
            directory = path.parent
        elif isinstance(directory, str):
            directory = Path(directory)
        if extension is None:
            extension = path.suffix.lstrip(".")

        if modified_at is None:
            modified_at = datetime.now(timezone.utc)
        if scanned_at is None:
            scanned_at = datetime.now(timezone.utc)

        # Build track list from dicts
        track_list = []
        if tracks:
            for i, track_dict in enumerate(tracks):
                track_dict.setdefault("index", i)
                track_list.append(make_track_info(**track_dict))

        return FileInfo(
            path=path,
            filename=filename,
            directory=directory,
            extension=extension,
            size_bytes=size_bytes,
            modified_at=modified_at,
            content_hash=content_hash,
            container_format=container_format,
            scanned_at=scanned_at,
            scan_status=scan_status,
            scan_error=scan_error,
            tracks=track_list,
        )

    return _make_file


@pytest.fixture
def make_policy():
    """Factory for creating PolicySchema objects with sensible defaults.

    Creates a minimal valid policy with one empty phase. Override
    specific fields as needed for testing.

    Returns:
        Callable: Factory function that creates PolicySchema instances.

    Example:
        def test_policy_config(make_policy):
            policy = make_policy(config={"on_error": "fail"})
            assert policy.config.on_error == "fail"
    """
    from vpo.policy.types import GlobalConfig, PhaseDefinition, PolicySchema

    def _make_policy(
        schema_version: int = 12,
        config: dict | GlobalConfig | None = None,
        phases: list[dict | PhaseDefinition] | None = None,
    ) -> PolicySchema:
        # Build config
        if config is None:
            final_config = GlobalConfig()
        elif isinstance(config, dict):
            final_config = GlobalConfig(**config)
        else:
            final_config = config

        # Build phases - at least one phase required
        if phases is None:
            final_phases = (PhaseDefinition(name="default", conditional=()),)
        else:
            phase_list = []
            for p in phases:
                if isinstance(p, dict):
                    p.setdefault("name", f"phase_{len(phase_list)}")
                    p.setdefault("conditional", ())
                    phase_list.append(PhaseDefinition(**p))
                else:
                    phase_list.append(p)
            final_phases = tuple(phase_list)

        return PolicySchema(
            schema_version=schema_version,
            config=final_config,
            phases=final_phases,
        )

    return _make_policy


@pytest.fixture
def make_transcode_result():
    """Factory for creating TranscodeResult objects with sensible defaults.

    Using this fixture (or spec=TranscodeResult with MagicMock) ensures tests
    fail if code accesses non-existent attributes on TranscodeResult.

    Example:
        def test_failure_handling(make_transcode_result):
            result = make_transcode_result(success=False, error_message="FFmpeg error")
            assert result.error_message == "FFmpeg error"
    """
    from vpo.executor.transcode import TranscodeResult

    def _make_result(
        success: bool = True,
        output_path: Path | None = None,
        error_message: str | None = None,
        backup_path: Path | None = None,
    ) -> TranscodeResult:
        return TranscodeResult(
            success=success,
            output_path=output_path,
            error_message=error_message,
            backup_path=backup_path,
        )

    return _make_result


# =============================================================================
# Workflow Phase Execution Fixtures
# =============================================================================


@pytest.fixture
def make_phase_execution_state():
    """Factory for creating PhaseExecutionState objects with sensible defaults.

    Creates a mutable execution state for testing phase execution.

    Returns:
        Callable: Factory function that creates PhaseExecutionState instances.

    Example:
        def test_phase_state(make_phase_execution_state):
            state = make_phase_execution_state(
                file_modified=True,
                total_changes=5
            )
            assert state.file_modified is True
    """
    from vpo.policy.types import PhaseDefinition
    from vpo.workflow.phases.executor.types import PhaseExecutionState

    def _make_state(
        file_path: Path | str = Path("/videos/movie.mkv"),
        phase: PhaseDefinition | None = None,
        backup_path: Path | None = None,
        operations_completed: list[str] | None = None,
        file_modified: bool = False,
        total_changes: int = 0,
        transcode_skip_reason: str | None = None,
        encoding_fps: float | None = None,
        encoding_bitrate_kbps: int | None = None,
        total_frames: int | None = None,
        encoder_type: str | None = None,
        original_mtime: float | None = None,
    ) -> PhaseExecutionState:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        if phase is None:
            phase = PhaseDefinition(name="test_phase", conditional=())
        if operations_completed is None:
            operations_completed = []

        return PhaseExecutionState(
            file_path=file_path,
            phase=phase,
            backup_path=backup_path,
            operations_completed=operations_completed,
            file_modified=file_modified,
            total_changes=total_changes,
            transcode_skip_reason=transcode_skip_reason,
            encoding_fps=encoding_fps,
            encoding_bitrate_kbps=encoding_bitrate_kbps,
            total_frames=total_frames,
            encoder_type=encoder_type,
            original_mtime=original_mtime,
        )

    return _make_state


@pytest.fixture
def make_synthesis_plan(make_track_info):
    """Factory for creating SynthesisPlan objects with sensible defaults.

    Creates a synthesis plan for testing audio synthesis operations.

    Returns:
        Callable: Factory function that creates SynthesisPlan instances.

    Example:
        def test_synthesis(make_synthesis_plan):
            plan = make_synthesis_plan(
                operations=[...],
                skipped=[...]
            )
            assert plan.has_operations
    """
    from vpo.policy.synthesis.models import (
        SynthesisPlan,
    )

    def _make_plan(
        file_id: str = "test-file-uuid",
        file_path: Path | str = Path("/videos/movie.mkv"),
        operations: tuple | list | None = None,
        skipped: tuple | list | None = None,
        final_track_order: tuple | list | None = None,
        audio_tracks: tuple | list | None = None,
    ) -> SynthesisPlan:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        if operations is None:
            operations = ()
        if skipped is None:
            skipped = ()
        if final_track_order is None:
            final_track_order = ()
        if audio_tracks is None:
            audio_tracks = ()

        # Convert lists to tuples
        if isinstance(operations, list):
            operations = tuple(operations)
        if isinstance(skipped, list):
            skipped = tuple(skipped)
        if isinstance(final_track_order, list):
            final_track_order = tuple(final_track_order)
        if isinstance(audio_tracks, list):
            audio_tracks = tuple(audio_tracks)

        return SynthesisPlan(
            file_id=file_id,
            file_path=file_path,
            operations=operations,
            skipped=skipped,
            final_track_order=final_track_order,
            audio_tracks=audio_tracks,
        )

    return _make_plan


# =============================================================================
# Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for FFmpeg and other command-line tool tests.

    Returns a context manager that patches subprocess.run and returns
    a MagicMock that can be configured with custom return values.

    Returns:
        Callable: Context manager that yields the mock.

    Example:
        def test_ffmpeg_call(mock_subprocess_run):
            with mock_subprocess_run() as mock_run:
                mock_run.return_value.returncode = 0
                # ... run code that uses subprocess.run
                mock_run.assert_called_once()
    """
    from contextlib import contextmanager
    from unittest.mock import MagicMock, patch

    @contextmanager
    def _mock():
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            mock_run.return_value = mock_result
            yield mock_run

    return _mock


# =============================================================================
# Database Record Factories
# =============================================================================


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()


@pytest.fixture
def make_file_record():
    """Factory for FileRecord with sensible defaults."""
    from vpo.db.types import FileRecord

    def _make(
        id: int | None = None,
        path: str = "/media/test.mkv",
        filename: str | None = None,
        directory: str | None = None,
        extension: str = ".mkv",
        size_bytes: int = 1000,
        modified_at: str = "2025-01-15T10:00:00Z",
        content_hash: str | None = None,
        container_format: str | None = "mkv",
        scanned_at: str = "2025-01-15T10:00:00Z",
        scan_status: str = "ok",
        scan_error: str | None = None,
        job_id: str | None = None,
        plugin_metadata: str | None = None,
    ) -> FileRecord:
        if filename is None:
            filename = path.rsplit("/", 1)[-1]
        if directory is None:
            directory = path.rsplit("/", 1)[0] or "/"
        return FileRecord(
            id=id,
            path=path,
            filename=filename,
            directory=directory,
            extension=extension,
            size_bytes=size_bytes,
            modified_at=modified_at,
            content_hash=content_hash,
            container_format=container_format,
            scanned_at=scanned_at,
            scan_status=scan_status,
            scan_error=scan_error,
            job_id=job_id,
            plugin_metadata=plugin_metadata,
        )

    return _make


@pytest.fixture
def make_track_record():
    """Factory for TrackRecord with sensible defaults."""
    from vpo.db.types import TrackRecord

    def _make(
        file_id: int = 1,
        track_index: int = 0,
        track_type: str = "video",
        codec: str | None = "h264",
        language: str | None = None,
        title: str | None = None,
        is_default: bool = False,
        is_forced: bool = False,
        **kwargs,
    ) -> TrackRecord:
        return TrackRecord(
            id=None,
            file_id=file_id,
            track_index=track_index,
            track_type=track_type,
            codec=codec,
            language=language,
            title=title,
            is_default=is_default,
            is_forced=is_forced,
            **kwargs,
        )

    return _make


@pytest.fixture
def insert_test_file(db_conn, make_file_record):
    """Create and insert a FileRecord, returning the file ID."""
    from vpo.db.queries import insert_file

    def _insert(**kwargs) -> int:
        record = make_file_record(**kwargs)
        return insert_file(db_conn, record)

    return _insert


@pytest.fixture
def insert_test_track(db_conn, make_track_record):
    """Create and insert a TrackRecord, returning the track ID."""
    from vpo.db.queries import insert_track

    def _insert(**kwargs) -> int:
        record = make_track_record(**kwargs)
        return insert_track(db_conn, record)

    return _insert


@pytest.fixture
def make_job():
    """Factory for Job with sensible defaults."""
    import uuid
    from datetime import datetime, timezone

    from vpo.db.types import Job, JobStatus, JobType

    def _make(
        id: str | None = None,
        file_id: int | None = None,
        file_path: str = "/test/file.mkv",
        job_type: JobType = JobType.TRANSCODE,
        status: JobStatus = JobStatus.QUEUED,
        priority: int = 100,
        policy_name: str | None = "test_policy",
        policy_json: str = "{}",
        progress_percent: float = 0.0,
        progress_json: str | None = None,
        created_at: str | None = None,
        **kwargs,
    ) -> Job:
        return Job(
            id=id or str(uuid.uuid4()),
            file_id=file_id,
            file_path=file_path,
            job_type=job_type,
            status=status,
            priority=priority,
            policy_name=policy_name,
            policy_json=policy_json,
            progress_percent=progress_percent,
            progress_json=progress_json,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )

    return _make


@pytest.fixture
def mock_all_phase_handlers():
    """Mock all phase operation handlers for dispatch testing.

    Patches all handler functions in workflow.phases.executor.handlers
    to return success results. Useful for testing dispatch routing
    without executing actual operations.

    Returns:
        Callable: Context manager that yields dict of mock handlers.

    Example:
        def test_dispatch(mock_all_phase_handlers):
            with mock_all_phase_handlers() as handlers:
                # Configure specific handler
                handlers["execute_transcode"].return_value = 0
                # ... run dispatch code
                handlers["execute_transcode"].assert_called_once()
    """
    from contextlib import contextmanager
    from unittest.mock import MagicMock, patch

    @contextmanager
    def _mock():
        handlers = {}
        patches = []

        # List of handler functions to mock
        handler_names = [
            "execute_container",
            "execute_audio_filter",
            "execute_subtitle_filter",
            "execute_attachment_filter",
            "execute_conditional",
            "execute_transcode",
            "execute_audio_synthesis",
            "execute_metadata",
            "execute_timestamp",
            "execute_track_order",
            "execute_default_flags",
            "execute_move",
        ]

        base_path = "vpo.workflow.phases.executor.core"

        for name in handler_names:
            mock = MagicMock(return_value=0)
            patcher = patch(f"{base_path}.{name}", mock)
            patcher.start()
            patches.append(patcher)
            handlers[name] = mock

        try:
            yield handlers
        finally:
            for patcher in patches:
                patcher.stop()

    return _mock
