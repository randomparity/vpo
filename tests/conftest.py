"""Shared test fixtures for Video Policy Orchestrator."""

import json
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
    with patch("vpo.executor.transcode.require_tool") as mock_require:
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
