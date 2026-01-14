"""Operation context for V11 phase execution.

This module defines the operational view of a file being processed,
distinct from the domain model (FileInfo) which represents introspection
results. The executor needs database IDs for audit trails, which domain
models intentionally don't carry (per Constitution Principle IV: Identity).

Provides:
- OperationContext: Protocol defining what phase executors need
- FileOperationContext: Concrete implementation with DB lookup
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vpo.db.queries import get_file_by_path, get_tracks_for_file
from vpo.db.types import FileInfo, TrackInfo, tracks_to_track_info

if TYPE_CHECKING:
    pass


class OperationContext(Protocol):
    """Protocol defining what phase executors need to operate on files.

    This protocol represents the operational view of a file being processed,
    distinct from the domain model (FileInfo) which represents introspection
    results. The executor needs database IDs for audit trails, which domain
    models intentionally don't carry.

    Design rationale:
    - FileInfo is a domain model from introspection (no DB concerns)
    - OperationContext is an operational model for execution (includes DB ID)
    - Separation allows clean domain boundaries per Constitution Principle IV
    """

    @property
    def file_id(self) -> str:
        """Database ID for audit trail and foreign keys.

        Returns UUIDv4 string for new files, database rowid for existing.
        """
        ...

    @property
    def file_path(self) -> Path:
        """Absolute path to the media file."""
        ...

    @property
    def container(self) -> str:
        """Container format (mkv, mp4, avi, etc.)."""
        ...

    @property
    def tracks(self) -> list[TrackInfo]:
        """List of tracks in the file."""
        ...


@dataclass
class FileOperationContext:
    """Concrete implementation of OperationContext.

    This adapter bridges the gap between FileInfo (domain model) and
    operational needs (database IDs, connection access).

    Attributes:
        _file_id: Database file ID (string form).
        _file_path: Absolute path to the media file.
        _container: Container format string.
        _tracks: List of TrackInfo with database IDs populated.
    """

    _file_id: str
    _file_path: Path
    _container: str
    _tracks: list[TrackInfo]

    @property
    def file_id(self) -> str:
        """Database ID for audit trail and foreign keys."""
        return self._file_id

    @property
    def file_path(self) -> Path:
        """Absolute path to the media file."""
        return self._file_path

    @property
    def container(self) -> str:
        """Container format (mkv, mp4, avi, etc.)."""
        return self._container

    @property
    def tracks(self) -> list[TrackInfo]:
        """List of tracks in the file."""
        return self._tracks

    @classmethod
    def from_file_info(
        cls,
        file_info: FileInfo,
        conn: sqlite3.Connection,
    ) -> FileOperationContext:
        """Create context from FileInfo (requires DB lookup for ID).

        Args:
            file_info: FileInfo domain model from introspection.
            conn: Database connection.

        Returns:
            FileOperationContext with database ID populated.

        Raises:
            ValueError: If file not found in database.
        """
        file_record = get_file_by_path(conn, str(file_info.path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_info.path}")

        # Get tracks from database to ensure IDs are populated
        track_records = get_tracks_for_file(conn, file_record.id)
        tracks = tracks_to_track_info(track_records)

        return cls(
            _file_id=str(file_record.id),
            _file_path=file_info.path,
            _container=file_info.container_format or "unknown",
            _tracks=tracks,
        )

    @classmethod
    def from_file_path(
        cls,
        file_path: Path,
        conn: sqlite3.Connection,
    ) -> FileOperationContext:
        """Create context from file path (DB lookup for everything).

        Args:
            file_path: Path to the media file.
            conn: Database connection.

        Returns:
            FileOperationContext with all data from database.

        Raises:
            ValueError: If file not found in database.
        """
        file_record = get_file_by_path(conn, str(file_path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_path}")

        track_records = get_tracks_for_file(conn, file_record.id)
        tracks = tracks_to_track_info(track_records)

        return cls(
            _file_id=str(file_record.id),
            _file_path=file_path,
            _container=file_record.container_format or "unknown",
            _tracks=tracks,
        )
