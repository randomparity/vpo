"""Fixtures for scanner unit tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from vpo.db.types import IntrospectionResult, TrackInfo
from vpo.scanner.orchestrator import (
    ScannerOrchestrator,
)

if TYPE_CHECKING:
    import sqlite3


@pytest.fixture
def scanner() -> ScannerOrchestrator:
    """Create a ScannerOrchestrator with default settings."""
    return ScannerOrchestrator()


@pytest.fixture
def scanner_custom_extensions() -> ScannerOrchestrator:
    """Create a ScannerOrchestrator with custom extensions."""
    return ScannerOrchestrator(extensions=["mkv", "mp4"])


@pytest.fixture
def mock_discovered_files() -> Callable[..., list[dict[str, Any]]]:
    """Factory for creating mock discover_videos results."""

    def _create(
        count: int = 1, base_path: str = "/media", extension: str = "mkv"
    ) -> list[dict[str, Any]]:
        return [
            {
                "path": f"{base_path}/video{i}.{extension}",
                "size": 1000 * (i + 1),
                "modified": 1704067200.0 + i,  # 2024-01-01 + i seconds
            }
            for i in range(count)
        ]

    return _create


@pytest.fixture
def mock_hash_results() -> Callable[..., list[dict[str, Any]]]:
    """Factory for creating mock hash_files results."""

    def _create(
        paths: list[str], error_paths: list[str] | None = None
    ) -> list[dict[str, Any]]:
        error_paths = error_paths or []
        return [
            {
                "path": p,
                "hash": f"hash_{i}" if p not in error_paths else None,
                "error": "Hash error" if p in error_paths else None,
            }
            for i, p in enumerate(paths)
        ]

    return _create


@pytest.fixture
def seeded_db(db_conn: sqlite3.Connection, insert_test_file) -> sqlite3.Connection:
    """Database with pre-existing file records."""
    insert_test_file(
        path="/media/existing.mkv",
        extension="mkv",
        modified_at="2024-01-01T00:00:00+00:00",
        content_hash="existing_hash",
        container_format="matroska",
    )
    db_conn.commit()
    return db_conn


@pytest.fixture
def mock_introspector():
    """Create a mock introspector that returns configurable results."""
    from vpo.introspector.interface import MediaIntrospector

    introspector = MagicMock(spec=MediaIntrospector)
    introspector.get_file_info.return_value = IntrospectionResult(
        file_path=Path("/test.mkv"),
        container_format="matroska",
        tracks=[
            TrackInfo(index=0, track_type="video", codec="hevc"),
            TrackInfo(index=1, track_type="audio", codec="aac", language="eng"),
        ],
        warnings=[],
    )
    return introspector


@pytest.fixture
def mock_introspector_error():
    """Create a mock introspector that raises MediaIntrospectionError."""
    from vpo.introspector.interface import (
        MediaIntrospectionError,
        MediaIntrospector,
    )

    introspector = MagicMock(spec=MediaIntrospector)
    introspector.get_file_info.side_effect = MediaIntrospectionError(
        "ffprobe failed", Path("/test.mkv")
    )
    return introspector
