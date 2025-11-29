"""Shared test fixtures for Video Policy Orchestrator."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


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
