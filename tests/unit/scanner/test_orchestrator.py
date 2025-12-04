"""Unit tests for the ScannerOrchestrator class."""

from __future__ import annotations

import signal
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

from video_policy_orchestrator.scanner.orchestrator import (
    DEFAULT_EXTENSIONS,
    ScannedFile,
    ScannerOrchestrator,
    ScanProgressCallback,
    ScanResult,
    detect_missing_files,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock as MagicMockType


class TestScanResult:
    """Tests for the ScanResult dataclass."""

    def test_default_values(self) -> None:
        """Verify all default values are correct."""
        result = ScanResult()
        assert result.files_found == 0
        assert result.files_new == 0
        assert result.files_updated == 0
        assert result.files_skipped == 0
        assert result.files_errored == 0
        assert result.files_removed == 0
        assert result.errors == []
        assert result.elapsed_seconds == 0.0
        assert result.directories_scanned == []
        assert result.interrupted is False
        assert result.incremental is True
        assert result.job_id is None

    def test_fields_settable(self) -> None:
        """Verify all fields can be set and retrieved."""
        result = ScanResult(
            files_found=10,
            files_new=5,
            files_updated=3,
            files_skipped=2,
            files_errored=1,
            files_removed=1,
            errors=[("/path", "error message")],
            elapsed_seconds=5.5,
            directories_scanned=["/media"],
            interrupted=True,
            incremental=False,
            job_id="test-uuid",
        )
        assert result.files_found == 10
        assert result.files_new == 5
        assert result.files_updated == 3
        assert result.files_skipped == 2
        assert result.files_errored == 1
        assert result.files_removed == 1
        assert result.errors == [("/path", "error message")]
        assert result.elapsed_seconds == 5.5
        assert result.directories_scanned == ["/media"]
        assert result.interrupted is True
        assert result.incremental is False
        assert result.job_id == "test-uuid"

    def test_errors_is_mutable_list(self) -> None:
        """Verify errors list can be appended to."""
        result = ScanResult()
        result.errors.append(("/test", "error"))
        assert len(result.errors) == 1

    def test_errors_list_is_not_shared_between_instances(self) -> None:
        """Each ScanResult gets its own errors list."""
        result1 = ScanResult()
        result2 = ScanResult()
        result1.errors.append(("/test", "error"))
        assert len(result2.errors) == 0


class TestDetectMissingFiles:
    """Tests for detect_missing_files helper function."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty list."""
        assert detect_missing_files([]) == []

    def test_all_files_exist(self, tmp_path: Path) -> None:
        """Returns empty when all files exist."""
        f1 = tmp_path / "file1.mkv"
        f2 = tmp_path / "file2.mkv"
        f1.touch()
        f2.touch()
        result = detect_missing_files([str(f1), str(f2)])
        assert result == []

    def test_all_files_missing(self) -> None:
        """Returns all paths when none exist."""
        paths = ["/nonexistent/a.mkv", "/nonexistent/b.mkv"]
        result = detect_missing_files(paths)
        assert result == paths

    def test_mixed_existing_and_missing(self, tmp_path: Path) -> None:
        """Returns only missing paths."""
        existing = tmp_path / "exists.mkv"
        existing.touch()
        missing = "/nonexistent/missing.mkv"
        result = detect_missing_files([str(existing), missing])
        assert result == [missing]

    def test_directory_is_considered_missing(self, tmp_path: Path) -> None:
        """Directories are not valid files."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = detect_missing_files([str(subdir)])
        assert result == [str(subdir)]

    def test_broken_symlink_is_missing(self, tmp_path: Path) -> None:
        """Broken symlinks are considered missing."""
        link = tmp_path / "broken_link"
        link.symlink_to("/nonexistent/target")
        result = detect_missing_files([str(link)])
        assert result == [str(link)]


class TestScannedFile:
    """Tests for the ScannedFile dataclass."""

    def test_required_fields(self) -> None:
        """Verify path, size, modified_at are required."""
        mtime = datetime.now(timezone.utc)
        scanned = ScannedFile(path="/test.mkv", size=1000, modified_at=mtime)
        assert scanned.path == "/test.mkv"
        assert scanned.size == 1000
        assert scanned.modified_at == mtime

    def test_optional_hash_defaults_none(self) -> None:
        """Verify content_hash defaults to None."""
        scanned = ScannedFile(
            path="/test.mkv", size=1000, modified_at=datetime.now(timezone.utc)
        )
        assert scanned.content_hash is None

    def test_optional_hash_error_defaults_none(self) -> None:
        """Verify hash_error defaults to None."""
        scanned = ScannedFile(
            path="/test.mkv", size=1000, modified_at=datetime.now(timezone.utc)
        )
        assert scanned.hash_error is None


class TestScannerOrchestratorInit:
    """Tests for ScannerOrchestrator initialization."""

    def test_default_extensions(self) -> None:
        """Verify default extensions are used when None provided."""
        scanner = ScannerOrchestrator()
        assert scanner.extensions == DEFAULT_EXTENSIONS

    def test_custom_extensions(self) -> None:
        """Verify custom extensions are stored."""
        scanner = ScannerOrchestrator(extensions=["mkv", "mp4"])
        assert scanner.extensions == ["mkv", "mp4"]

    def test_default_follow_symlinks_false(self) -> None:
        """Verify follow_symlinks defaults to False."""
        scanner = ScannerOrchestrator()
        assert scanner.follow_symlinks is False

    def test_custom_follow_symlinks(self) -> None:
        """Verify follow_symlinks can be set to True."""
        scanner = ScannerOrchestrator(follow_symlinks=True)
        assert scanner.follow_symlinks is True

    def test_interrupt_event_initialized(self) -> None:
        """Verify interrupt event is created."""
        scanner = ScannerOrchestrator()
        assert scanner._interrupt_event is not None
        assert not scanner._interrupt_event.is_set()


class TestScannerOrchestratorSignalHandling:
    """Tests for signal handling in ScannerOrchestrator."""

    def test_is_interrupted_initially_false(self, scanner: ScannerOrchestrator) -> None:
        """Verify _is_interrupted() returns False initially."""
        assert scanner._is_interrupted() is False

    def test_create_signal_handler_sets_interrupt_event(
        self, scanner: ScannerOrchestrator
    ) -> None:
        """Verify handler sets interrupt event."""
        handler = scanner._create_signal_handler()
        assert callable(handler)

        # Call the handler
        handler(signal.SIGINT, None)

        # Check that interrupt event was set
        assert scanner._is_interrupted() is True

    def test_interrupt_event_can_be_cleared(self, scanner: ScannerOrchestrator) -> None:
        """Verify interrupt event can be cleared."""
        scanner._interrupt_event.set()
        assert scanner._is_interrupted() is True

        scanner._interrupt_event.clear()
        assert scanner._is_interrupted() is False


class TestScanDirectories:
    """Tests for scan_directories() method."""

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_empty_directory(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
    ) -> None:
        """Verify handling of empty directory."""
        mock_discover.return_value = []

        files, result = scanner.scan_directories([tmp_path])

        assert files == []
        assert result.files_found == 0
        mock_discover.assert_called_once()

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_single_file(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify single file discovery."""
        mock_discover.return_value = mock_discovered_files(1)

        files, result = scanner.scan_directories([tmp_path], compute_hashes=False)

        assert len(files) == 1
        assert result.files_found == 1
        assert files[0].path == "/media/video0.mkv"
        assert files[0].size == 1000

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_multiple_files(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify multiple file discovery."""
        mock_discover.return_value = mock_discovered_files(5)

        files, result = scanner.scan_directories([tmp_path], compute_hashes=False)

        assert len(files) == 5
        assert result.files_found == 5

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_multiple_directories(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify scanning multiple directories."""
        # Return different files for each call
        mock_discover.side_effect = [
            mock_discovered_files(2, base_path="/media1"),
            mock_discovered_files(3, base_path="/media2"),
        ]

        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"

        files, result = scanner.scan_directories([dir1, dir2], compute_hashes=False)

        assert len(files) == 5
        assert result.files_found == 5
        assert mock_discover.call_count == 2

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_nonexistent_directory_error(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
    ) -> None:
        """Verify FileNotFoundError handling."""
        mock_discover.side_effect = FileNotFoundError("Directory not found")

        files, result = scanner.scan_directories([tmp_path])

        assert files == []
        assert result.files_found == 0
        assert result.files_errored == 1
        assert len(result.errors) == 1
        assert "not found" in result.errors[0][1].lower()

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_not_a_directory_error(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
    ) -> None:
        """Verify NotADirectoryError handling."""
        mock_discover.side_effect = NotADirectoryError("Not a directory")

        files, result = scanner.scan_directories([tmp_path])

        assert files == []
        assert result.files_errored == 1
        assert len(result.errors) == 1

    @patch("video_policy_orchestrator.scanner.orchestrator.hash_files")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_compute_hashes_true(
        self,
        mock_discover: MagicMockType,
        mock_hash: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
        mock_hash_results,
    ) -> None:
        """Verify hashes are computed when flag is True."""
        discovered = mock_discovered_files(2)
        mock_discover.return_value = discovered
        mock_hash.return_value = mock_hash_results([f["path"] for f in discovered])

        files, result = scanner.scan_directories([tmp_path], compute_hashes=True)

        mock_hash.assert_called_once()
        assert files[0].content_hash is not None

    @patch("video_policy_orchestrator.scanner.orchestrator.hash_files")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_compute_hashes_false(
        self,
        mock_discover: MagicMockType,
        mock_hash: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify hashes not computed when flag is False."""
        mock_discover.return_value = mock_discovered_files(2)

        files, result = scanner.scan_directories([tmp_path], compute_hashes=False)

        mock_hash.assert_not_called()
        assert files[0].content_hash is None

    @patch("video_policy_orchestrator.scanner.orchestrator.hash_files")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_hash_error_recorded(
        self,
        mock_discover: MagicMockType,
        mock_hash: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify hash errors are recorded in ScannedFile and result.errors."""
        discovered = mock_discovered_files(2)
        mock_discover.return_value = discovered
        # First file has error
        error_path = discovered[0]["path"]
        mock_hash.return_value = [
            {"path": error_path, "hash": None, "error": "IO Error"},
            {"path": discovered[1]["path"], "hash": "hash_1", "error": None},
        ]

        files, result = scanner.scan_directories([tmp_path], compute_hashes=True)

        assert files[0].hash_error == "IO Error"
        assert len(result.errors) == 1
        assert result.errors[0][0] == error_path

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_discover_progress_callback(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
    ) -> None:
        """Verify discover progress callback is invoked."""
        mock_discover.return_value = []
        progress = MagicMock(spec=ScanProgressCallback)

        scanner.scan_directories([tmp_path], scan_progress=progress)

        # Verify callback was passed to discover_videos
        call_args = mock_discover.call_args
        assert call_args.kwargs["progress_callback"] == progress.on_discover_progress

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_directories_scanned_populated(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
    ) -> None:
        """Verify directories_scanned contains input dirs."""
        mock_discover.return_value = []

        files, result = scanner.scan_directories([tmp_path])

        assert str(tmp_path) in result.directories_scanned

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_modified_at_is_utc(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify modified_at timestamp is UTC."""
        mock_discover.return_value = mock_discovered_files(1)

        files, result = scanner.scan_directories([tmp_path], compute_hashes=False)

        assert files[0].modified_at.tzinfo == timezone.utc


class TestScanAndPersist:
    """Tests for scan_and_persist() method."""

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_empty_directory(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify empty directory handling."""
        mock_discover.return_value = []

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert files == []
        assert result.files_found == 0
        assert result.files_new == 0

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_single_new_file(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify new file is persisted."""
        mock_discover.return_value = mock_discovered_files(1)

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert len(files) == 1
        assert result.files_new == 1
        assert result.files_updated == 0

        # Verify file was persisted to database
        from video_policy_orchestrator.db.models import get_file_by_path

        record = get_file_by_path(db_conn, "/media/video0.mkv")
        assert record is not None
        assert record.filename == "video0.mkv"

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_files_updated_count(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify files_updated is incremented for existing files."""
        # seeded_db has /media/existing.mkv with mtime 2024-01-01
        # Return same file with different mtime to trigger update
        mock_discover.return_value = [
            {
                "path": "/media/existing.mkv",
                "size": 1000,
                "modified": 1704153600.0,  # 2024-01-02 (different from seeded)
            }
        ]

        files, result = scanner.scan_and_persist(
            [tmp_path],
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert result.files_updated == 1
        assert result.files_new == 0

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_incremental_skips_unchanged(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify unchanged files are skipped in incremental mode."""
        # Return file with SAME mtime/size as seeded record
        mock_discover.return_value = [
            {
                "path": "/media/existing.mkv",
                "size": 1000,
                "modified": datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
            }
        ]

        files, result = scanner.scan_and_persist(
            [tmp_path],
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert result.files_skipped == 1
        assert result.files_updated == 0
        assert result.files_new == 0
        # Introspector should not be called for skipped files
        mock_introspector.get_file_info.assert_not_called()

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_full_scan_processes_all(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify full=True processes all files."""
        # Return file with same mtime/size - would normally be skipped
        mock_discover.return_value = [
            {
                "path": "/media/existing.mkv",
                "size": 1000,
                "modified": datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
            }
        ]

        files, result = scanner.scan_and_persist(
            [tmp_path],
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=False,
            full=True,
        )

        assert result.files_skipped == 0
        assert result.files_updated == 1  # Processed despite same mtime/size
        assert result.incremental is False

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_prune_deletes_missing_files(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify prune=True deletes DB records for missing files."""
        # Return empty - the seeded file is now "missing"
        mock_discover.return_value = []

        from video_policy_orchestrator.db.models import get_file_by_path

        # Verify file exists before
        record = get_file_by_path(seeded_db, "/media/existing.mkv")
        assert record is not None

        files, result = scanner.scan_and_persist(
            [Path("/media")],  # Same directory as seeded file
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=False,
            prune=True,
        )

        assert result.files_removed == 1

        # Verify file was deleted
        record = get_file_by_path(seeded_db, "/media/existing.mkv")
        assert record is None

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_no_prune_marks_missing(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify prune=False marks files as 'missing' status."""
        # Return empty - the seeded file is now "missing"
        mock_discover.return_value = []

        files, result = scanner.scan_and_persist(
            [Path("/media")],  # Same directory as seeded file
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=False,
            prune=False,
        )

        assert result.files_removed == 1

        # Verify file was marked as missing, not deleted
        cursor = seeded_db.execute(
            "SELECT scan_status FROM files WHERE path = ?",
            ("/media/existing.mkv",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "missing"

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_introspection_error_sets_scan_status(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector_error,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify MediaIntrospectionError sets scan_status='error'."""
        mock_discover.return_value = mock_discovered_files(1)

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector_error,
            compute_hashes=False,
        )

        assert result.files_errored == 1

        # Verify scan_status is 'error' in database
        from video_policy_orchestrator.db.models import get_file_by_path

        record = get_file_by_path(db_conn, "/media/video0.mkv")
        assert record is not None
        assert record.scan_status == "error"
        assert record.scan_error is not None
        assert "ffprobe failed" in record.scan_error

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_unexpected_error_captured(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify unexpected Exception is captured."""
        mock_discover.return_value = mock_discovered_files(1)
        mock_introspector.get_file_info.side_effect = RuntimeError("Unexpected")

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert result.files_errored == 1

        from video_policy_orchestrator.db.models import get_file_by_path

        record = get_file_by_path(db_conn, "/media/video0.mkv")
        assert record.scan_status == "error"
        assert "Unexpected" in record.scan_error

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_tracks_persisted(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify tracks are persisted via upsert_tracks_for_file."""
        mock_discover.return_value = mock_discovered_files(1)

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        # Verify tracks were persisted
        cursor = db_conn.execute(
            "SELECT track_type, codec FROM tracks WHERE file_id = 1"
        )
        tracks = cursor.fetchall()
        assert len(tracks) == 2
        track_types = {t[0] for t in tracks}
        assert "video" in track_types
        assert "audio" in track_types

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_job_id_stored(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify job_id is stored in FileRecord."""
        mock_discover.return_value = mock_discovered_files(1)
        test_job_id = "test-job-uuid-123"

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
            job_id=test_job_id,
        )

        assert result.job_id == test_job_id

        # Verify job_id in database
        cursor = db_conn.execute(
            "SELECT job_id FROM files WHERE path = ?", ("/media/video0.mkv",)
        )
        row = cursor.fetchone()
        assert row[0] == test_job_id

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_interrupt_during_processing(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify interrupt during file processing stops."""
        mock_discover.return_value = mock_discovered_files(10)

        # Set interrupt after 2 introspector calls
        call_count = 0

        def introspect_and_interrupt(path):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scanner._interrupt_event.set()
            return mock_introspector.get_file_info.return_value

        mock_introspector.get_file_info.side_effect = introspect_and_interrupt

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        assert result.interrupted is True
        # Should have processed fewer than all 10 files
        assert result.files_new < 10

    @patch("video_policy_orchestrator.scanner.orchestrator.signal")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_signal_handler_restored(
        self,
        mock_discover: MagicMockType,
        mock_signal: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify original SIGINT handler is restored."""
        mock_discover.return_value = []
        original_handler = MagicMock()
        mock_signal.signal.return_value = original_handler
        mock_signal.SIGINT = signal.SIGINT

        scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        # Verify signal.signal was called twice: once to set, once to restore
        assert mock_signal.signal.call_count == 2
        # Last call should restore original handler
        last_call = mock_signal.signal.call_args_list[-1]
        assert last_call == call(signal.SIGINT, original_handler)

    @patch("video_policy_orchestrator.scanner.orchestrator.signal")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_signal_handler_restored_on_exception(
        self,
        mock_discover: MagicMockType,
        mock_signal: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify handler restored even on exception."""
        mock_discover.return_value = mock_discovered_files(1)
        original_handler = MagicMock()
        mock_signal.signal.return_value = original_handler
        mock_signal.SIGINT = signal.SIGINT

        # Make introspector raise to trigger exception path
        mock_introspector.get_file_info.side_effect = Exception("Unexpected")

        # Should not raise
        scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
        )

        # Verify handler was still restored
        last_call = mock_signal.signal.call_args_list[-1]
        assert last_call == call(signal.SIGINT, original_handler)

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_scan_progress_callback_called(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify scan_progress.on_scan_progress called."""
        mock_discover.return_value = mock_discovered_files(3)
        progress = MagicMock(spec=ScanProgressCallback)

        scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
            scan_progress=progress,
        )

        # on_scan_progress should be called for each file
        assert progress.on_scan_progress.call_count == 3

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_batch_commit_size_processes_all_files(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify all files are processed with batch commits."""
        mock_discover.return_value = mock_discovered_files(5)

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=False,
            batch_commit_size=2,
        )

        # All 5 files should be processed
        assert result.files_new == 5

        # Verify all files were persisted to database
        cursor = db_conn.execute("SELECT COUNT(*) FROM files")
        count = cursor.fetchone()[0]
        assert count == 5


class TestScanAndPersistHashVerification:
    """Tests for verify_hash mode in scan_and_persist."""

    @patch("video_policy_orchestrator.scanner.orchestrator.hash_files")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_verify_hash_detects_content_change(
        self,
        mock_discover: MagicMockType,
        mock_hash: MagicMockType,
        scanner: ScannerOrchestrator,
        seeded_db: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
    ) -> None:
        """Verify verify_hash=True detects content changes."""
        # Return file with same mtime/size (would be skipped normally)
        mock_discover.return_value = [
            {
                "path": "/media/existing.mkv",
                "size": 1000,
                "modified": datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
            }
        ]
        # Return different hash than stored ("existing_hash")
        mock_hash.return_value = [
            {"path": "/media/existing.mkv", "hash": "new_hash", "error": None}
        ]

        files, result = scanner.scan_and_persist(
            [tmp_path],
            seeded_db,
            introspector=mock_introspector,
            compute_hashes=True,
            verify_hash=True,
        )

        # File should be processed (not skipped) due to hash change
        assert result.files_skipped == 0
        assert result.files_updated == 1

    @patch("video_policy_orchestrator.scanner.orchestrator.hash_files")
    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_hash_error_sets_scan_status(
        self,
        mock_discover: MagicMockType,
        mock_hash: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify hash error sets scan_status='error'."""
        mock_discover.return_value = mock_discovered_files(1)
        mock_hash.return_value = [
            {"path": "/media/video0.mkv", "hash": None, "error": "IO Error"}
        ]

        files, result = scanner.scan_and_persist(
            [tmp_path],
            db_conn,
            introspector=mock_introspector,
            compute_hashes=True,
        )

        from video_policy_orchestrator.db.models import get_file_by_path

        record = get_file_by_path(db_conn, "/media/video0.mkv")
        assert record.scan_status == "error"
        assert record.scan_error == "IO Error"


class TestScanAndPersistFallbackIntrospector:
    """Tests for introspector fallback behavior."""

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_uses_ffprobe_when_available(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        tmp_path: Path,
    ) -> None:
        """Verify FFprobeIntrospector used when available."""
        mock_discover.return_value = []

        with patch(
            "video_policy_orchestrator.introspector.ffprobe.FFprobeIntrospector"
        ) as MockFFprobe:
            MockFFprobe.is_available.return_value = True

            scanner.scan_and_persist([tmp_path], db_conn, compute_hashes=False)

            MockFFprobe.is_available.assert_called_once()
            MockFFprobe.assert_called_once()

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_falls_back_to_stub(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        tmp_path: Path,
    ) -> None:
        """Verify StubIntrospector used when FFprobe unavailable."""
        mock_discover.return_value = []

        with (
            patch(
                "video_policy_orchestrator.introspector.ffprobe.FFprobeIntrospector"
            ) as MockFFprobe,
            patch(
                "video_policy_orchestrator.introspector.stub.StubIntrospector"
            ) as MockStub,
        ):
            MockFFprobe.is_available.return_value = False

            scanner.scan_and_persist([tmp_path], db_conn, compute_hashes=False)

            MockStub.assert_called_once()

    @patch("video_policy_orchestrator.scanner.orchestrator.discover_videos")
    def test_uses_provided_introspector(
        self,
        mock_discover: MagicMockType,
        scanner: ScannerOrchestrator,
        db_conn: sqlite3.Connection,
        mock_introspector,
        tmp_path: Path,
        mock_discovered_files,
    ) -> None:
        """Verify custom introspector is used."""
        mock_discover.return_value = mock_discovered_files(1)

        with patch(
            "video_policy_orchestrator.introspector.ffprobe.FFprobeIntrospector"
        ) as MockFFprobe:
            scanner.scan_and_persist(
                [tmp_path],
                db_conn,
                introspector=mock_introspector,
                compute_hashes=False,
            )

            # is_available should not be called when introspector provided
            MockFFprobe.is_available.assert_not_called()
            # Our mock introspector should be used
            mock_introspector.get_file_info.assert_called_once()
