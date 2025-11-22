"""Shared test fixtures for Video Policy Orchestrator."""

import shutil
import tempfile
from pathlib import Path

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
