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
    """Prevent logging output from contaminating CliRunner results.

    When no log file is configured (the CI default), configure_logging()
    adds a StreamHandler(sys.stderr).  Click 8.2+ CliRunner mixes stderr
    into result.output, so ANY log message at INFO+ appears in the CLI
    output and breaks JSON assertions.

    This fixture sets _logging_configured = True so that _configure_logging()
    is skipped entirely during CLI invocations — no stderr handler is created
    and no log output contaminates CliRunner results.  Handlers are cleared
    to remove any stale references from a previous test's CliRunner.
    """
    import vpo.cli as cli_module

    cli_module._logging_configured = True
    cli_module._startup_logged = True

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers.clear()

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
# CLI Testing Fixtures
# =============================================================================


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()


# =============================================================================
# Database Record Factories
# =============================================================================
#
# Three abstraction levels for test data:
#
# 1. Record factories (make_file_record, make_track_record, make_job):
#    Create database record dataclasses. Use for tests that need
#    objects but don't need them persisted.
#
# 2. Insertion helpers (insert_test_file, insert_test_track):
#    Factory + DB insertion. Returns the new row ID. Does NOT commit —
#    callers manage transactions.
#
# 3. Domain model factories (make_file_info, make_track_info — above):
#    Create domain model objects. Use for business logic / policy tests.


@pytest.fixture
def make_file_record():
    """Factory for FileRecord with sensible defaults."""
    from vpo.db.types import FileRecord

    def _make(
        id: int | None = None,
        path: str = "/media/test.mkv",
        filename: str | None = None,
        directory: str | None = None,
        extension: str = "mkv",  # no dot — matches scanner convention
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
    """Create and insert a FileRecord, returning the file ID.

    Does NOT call conn.commit(). Callers that need persistence
    across rollback boundaries must commit explicitly.
    """
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
def insert_audio_track(insert_test_track):
    """Insert an audio track with standard defaults for language analysis tests.

    Wraps insert_test_track with audio-specific defaults so callers
    only need to specify file_id and the fields they care about.
    """

    def _insert(
        file_id: int,
        track_index: int = 0,
        language: str = "eng",
        is_default: bool = True,
        **kwargs,
    ) -> int:
        return insert_test_track(
            file_id=file_id,
            track_index=track_index,
            track_type="audio",
            codec=kwargs.pop("codec", "aac"),
            language=language,
            is_default=is_default,
            channels=kwargs.pop("channels", 2),
            channel_layout=kwargs.pop("channel_layout", "stereo"),
            duration_seconds=kwargs.pop("duration_seconds", 3600.0),
            **kwargs,
        )

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
def insert_test_job(db_conn, make_job):
    """Create and insert a Job, returning the Job object.

    Does NOT call conn.commit(). Callers that need persistence
    across rollback boundaries must commit explicitly.
    """
    from vpo.db.queries import insert_job

    def _insert(**kwargs):
        job = make_job(**kwargs)
        insert_job(db_conn, job)
        return job

    return _insert
