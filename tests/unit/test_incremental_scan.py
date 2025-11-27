"""Unit tests for incremental scan change detection (008-operational-ux)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import FileRecord


class TestFileNeedsRescan:
    """Tests for file_needs_rescan() function."""

    def test_new_file_needs_rescan(self) -> None:
        """New file (no existing record) should need rescan."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        # No existing record means new file
        result = file_needs_rescan(
            existing_record=None,
            current_mtime=datetime.now(timezone.utc),
            current_size=1000,
        )
        assert result is True

    def test_unchanged_file_skipped(self) -> None:
        """File with same mtime and size should be skipped."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        mtime = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        size = 1000

        existing = FileRecord(
            id=1,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=size,
            modified_at=mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )

        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=mtime,
            current_size=size,
        )
        assert result is False

    def test_modified_mtime_needs_rescan(self) -> None:
        """File with changed mtime should need rescan."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        old_mtime = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        new_mtime = datetime(2025, 1, 16, 10, 30, 0, tzinfo=timezone.utc)
        size = 1000

        existing = FileRecord(
            id=1,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=size,
            modified_at=old_mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )

        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=new_mtime,
            current_size=size,
        )
        assert result is True

    def test_modified_size_needs_rescan(self) -> None:
        """File with changed size should need rescan."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        mtime = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        old_size = 1000
        new_size = 2000

        existing = FileRecord(
            id=1,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=old_size,
            modified_at=mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )

        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=mtime,
            current_size=new_size,
        )
        assert result is True

    def test_both_mtime_and_size_changed(self) -> None:
        """File with both mtime and size changed should need rescan."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        old_mtime = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        new_mtime = datetime(2025, 1, 16, 10, 30, 0, tzinfo=timezone.utc)
        old_size = 1000
        new_size = 2000

        existing = FileRecord(
            id=1,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=old_size,
            modified_at=old_mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )

        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=new_mtime,
            current_size=new_size,
        )
        assert result is True

    def test_microsecond_precision_mtime(self) -> None:
        """Mtime comparison should work with microsecond precision."""
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        mtime_with_micro = datetime(2025, 1, 15, 10, 30, 0, 123456, tzinfo=timezone.utc)
        size = 1000

        existing = FileRecord(
            id=1,
            path="/media/video.mkv",
            filename="video.mkv",
            directory="/media",
            extension="mkv",
            size_bytes=size,
            modified_at=mtime_with_micro.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )

        # Same microseconds - should not need rescan
        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=mtime_with_micro,
            current_size=size,
        )
        assert result is False

        # Different microseconds - should need rescan
        different_micro = datetime(2025, 1, 15, 10, 30, 0, 999999, tzinfo=timezone.utc)
        result = file_needs_rescan(
            existing_record=existing,
            current_mtime=different_micro,
            current_size=size,
        )
        assert result is True


class TestDetectMissingFiles:
    """Tests for detect_missing_files() function."""

    def test_no_missing_files(self, tmp_path: Path) -> None:
        """When all DB files exist on disk, return empty list."""
        from video_policy_orchestrator.scanner.orchestrator import detect_missing_files

        # Create test files
        file1 = tmp_path / "video1.mkv"
        file2 = tmp_path / "video2.mkv"
        file1.touch()
        file2.touch()

        db_paths = [str(file1), str(file2)]
        missing = detect_missing_files(db_paths)
        assert missing == []

    def test_all_files_missing(self, tmp_path: Path) -> None:
        """When no DB files exist on disk, return all paths."""
        from video_policy_orchestrator.scanner.orchestrator import detect_missing_files

        # Paths that don't exist
        db_paths = [
            str(tmp_path / "missing1.mkv"),
            str(tmp_path / "missing2.mkv"),
        ]
        missing = detect_missing_files(db_paths)
        assert set(missing) == set(db_paths)

    def test_some_files_missing(self, tmp_path: Path) -> None:
        """When some DB files are missing, return only missing paths."""
        from video_policy_orchestrator.scanner.orchestrator import detect_missing_files

        # Create one file, leave one missing
        existing_file = tmp_path / "exists.mkv"
        existing_file.touch()
        missing_path = str(tmp_path / "missing.mkv")

        db_paths = [str(existing_file), missing_path]
        missing = detect_missing_files(db_paths)
        assert missing == [missing_path]

    def test_empty_db_paths(self) -> None:
        """Empty input should return empty list."""
        from video_policy_orchestrator.scanner.orchestrator import detect_missing_files

        missing = detect_missing_files([])
        assert missing == []

    def test_directory_counts_as_missing(self, tmp_path: Path) -> None:
        """A path that is a directory (not file) should count as missing."""
        from video_policy_orchestrator.scanner.orchestrator import detect_missing_files

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        db_paths = [str(subdir)]
        missing = detect_missing_files(db_paths)
        assert missing == [str(subdir)]


class TestIncrementalScanIntegration:
    """Integration tests for incremental scan behavior."""

    def test_incremental_scan_skips_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Incremental scan should skip unchanged files."""
        import sqlite3
        from datetime import datetime, timezone

        from video_policy_orchestrator.db.models import FileRecord, upsert_file
        from video_policy_orchestrator.db.schema import initialize_database

        # Create in-memory database
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)

        # Create a test file
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"fake video content")
        stat = test_file.stat()

        # Insert existing record with matching mtime and size
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        existing = FileRecord(
            id=None,
            path=str(test_file),
            filename=test_file.name,
            directory=str(test_file.parent),
            extension="mkv",
            size_bytes=stat.st_size,
            modified_at=mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        upsert_file(conn, existing)

        # Import after DB setup
        from video_policy_orchestrator.db.models import get_file_by_path
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        # Check if file needs rescan
        record = get_file_by_path(conn, str(test_file))
        result = file_needs_rescan(
            existing_record=record,
            current_mtime=mtime,
            current_size=stat.st_size,
        )
        assert result is False

        conn.close()

    def test_incremental_scan_detects_modification(self, tmp_path: Path) -> None:
        """Incremental scan should detect modified files."""
        import sqlite3
        from datetime import datetime, timedelta, timezone

        from video_policy_orchestrator.db.models import FileRecord, upsert_file
        from video_policy_orchestrator.db.schema import initialize_database

        # Create in-memory database
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)

        # Create a test file
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"fake video content")
        stat = test_file.stat()
        current_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        # Insert existing record with OLDER mtime
        old_mtime = current_mtime - timedelta(days=1)
        existing = FileRecord(
            id=None,
            path=str(test_file),
            filename=test_file.name,
            directory=str(test_file.parent),
            extension="mkv",
            size_bytes=stat.st_size,
            modified_at=old_mtime.isoformat(),
            content_hash="abc123",
            container_format="Matroska",
            scanned_at=datetime.now(timezone.utc).isoformat(),
            scan_status="ok",
            scan_error=None,
        )
        upsert_file(conn, existing)

        # Import after DB setup
        from video_policy_orchestrator.db.models import get_file_by_path
        from video_policy_orchestrator.scanner.orchestrator import file_needs_rescan

        # Check if file needs rescan
        record = get_file_by_path(conn, str(test_file))
        result = file_needs_rescan(
            existing_record=record,
            current_mtime=current_mtime,
            current_size=stat.st_size,
        )
        assert result is True

        conn.close()
