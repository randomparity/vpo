"""Unit tests for reports queries module."""

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.reports.filters import TimeFilter
from vpo.reports.queries import (
    MAX_LIMIT,
    JobReportRow,
    LibraryReportRow,
    extract_scan_summary,
    get_jobs_report,
    get_library_report,
    get_policy_apply_report,
    get_resolution_category,
    get_scans_report,
    get_transcodes_report,
)


@pytest.fixture
def test_db():
    """Create a test database with sample data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Enable foreign keys for referential integrity
    conn.execute("PRAGMA foreign_keys = ON")

    # Create minimal schema for testing
    conn.executescript("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL,
            filename TEXT,
            directory TEXT,
            extension TEXT,
            size_bytes INTEGER,
            container_format TEXT,
            scanned_at TEXT,
            scan_status TEXT DEFAULT 'ok'
        );

        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            track_type TEXT NOT NULL,
            codec TEXT,
            language TEXT,
            width INTEGER,
            height INTEGER,
            is_default INTEGER DEFAULT 0,
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            file_id INTEGER,
            file_path TEXT,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            policy_name TEXT,
            policy_json TEXT,
            progress_percent REAL DEFAULT 0,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT,
            summary_json TEXT,
            files_affected_json TEXT,
            output_path TEXT,
            backup_path TEXT
        );

        CREATE TABLE processing_stats (
            id TEXT PRIMARY KEY,
            file_id INTEGER,
            processed_at TEXT,
            policy_name TEXT,
            size_before INTEGER,
            size_after INTEGER,
            size_change INTEGER,
            audio_tracks_before INTEGER DEFAULT 0,
            subtitle_tracks_before INTEGER DEFAULT 0,
            attachments_before INTEGER DEFAULT 0,
            audio_tracks_after INTEGER DEFAULT 0,
            subtitle_tracks_after INTEGER DEFAULT 0,
            attachments_after INTEGER DEFAULT 0,
            audio_tracks_removed INTEGER DEFAULT 0,
            subtitle_tracks_removed INTEGER DEFAULT 0,
            attachments_removed INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0,
            phases_completed INTEGER DEFAULT 0,
            phases_total INTEGER DEFAULT 0,
            total_changes INTEGER DEFAULT 0,
            video_source_codec TEXT,
            video_target_codec TEXT,
            video_transcode_skipped INTEGER DEFAULT 0,
            video_skip_reason TEXT,
            audio_tracks_transcoded INTEGER DEFAULT 0,
            audio_tracks_preserved INTEGER DEFAULT 0,
            hash_before TEXT,
            hash_after TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            encoder_type TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id)
        );
    """)

    yield conn
    conn.close()


class TestGetResolutionCategory:
    """Tests for get_resolution_category function."""

    def test_4k_resolution(self):
        """Detect 4K resolution."""
        assert get_resolution_category(3840, 2160) == "4K"
        assert get_resolution_category(4096, 2160) == "4K"

    def test_1080p_resolution(self):
        """Detect 1080p resolution."""
        assert get_resolution_category(1920, 1080) == "1080p"
        assert get_resolution_category(1920, 1200) == "1080p"

    def test_720p_resolution(self):
        """Detect 720p resolution."""
        assert get_resolution_category(1280, 720) == "720p"
        assert get_resolution_category(1280, 800) == "720p"

    def test_480p_resolution(self):
        """Detect 480p resolution."""
        assert get_resolution_category(854, 480) == "480p"
        assert get_resolution_category(640, 480) == "480p"

    def test_sd_resolution(self):
        """Detect SD resolution."""
        assert get_resolution_category(640, 360) == "SD"
        assert get_resolution_category(320, 240) == "SD"

    def test_none_width(self):
        """Return unknown for None width."""
        assert get_resolution_category(None, 1080) == "unknown"

    def test_none_height(self):
        """Return unknown for None height."""
        assert get_resolution_category(1920, None) == "unknown"

    def test_both_none(self):
        """Return unknown for both None."""
        assert get_resolution_category(None, None) == "unknown"


class TestExtractScanSummary:
    """Tests for extract_scan_summary function."""

    def test_valid_json(self):
        """Extract values from valid JSON."""
        json_str = json.dumps(
            {"files_scanned": 100, "files_new": 10, "files_changed": 5}
        )
        result = extract_scan_summary(json_str)
        assert result["files_scanned"] == 100
        assert result["files_new"] == 10
        assert result["files_changed"] == 5

    def test_alternate_keys(self):
        """Handle alternate key names."""
        json_str = json.dumps({"total": 100, "new": 10, "changed": 5})
        result = extract_scan_summary(json_str)
        assert result["files_scanned"] == 100
        assert result["files_new"] == 10
        assert result["files_changed"] == 5

    def test_none_input(self):
        """Return defaults for None input."""
        result = extract_scan_summary(None)
        assert result["files_scanned"] == 0
        assert result["files_new"] == 0
        assert result["files_changed"] == 0

    def test_invalid_json(self):
        """Return defaults for invalid JSON."""
        result = extract_scan_summary("not valid json")
        assert result["files_scanned"] == 0
        assert result["files_new"] == 0
        assert result["files_changed"] == 0

    def test_empty_string(self):
        """Return defaults for empty string."""
        result = extract_scan_summary("")
        assert result["files_scanned"] == 0


class TestGetJobsReport:
    """Tests for get_jobs_report function."""

    def test_empty_database(self, test_db):
        """Return empty list for empty database."""
        result = get_jobs_report(test_db)
        assert result == []

    def test_basic_query(self, test_db):
        """Query all jobs."""
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, file_path, created_at, started_at)
            VALUES ('job-123-456', 'scan', 'completed', '/path/file.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z')
        """)

        result = get_jobs_report(test_db)
        assert len(result) == 1
        assert result[0]["job_id"] == "job-123-"
        assert result[0]["type"] == "scan"
        assert result[0]["status"] == "completed"

    def test_filter_by_type(self, test_db):
        """Filter jobs by type."""
        test_db.executemany(
            """
            INSERT INTO jobs (id, job_type, status, file_path, created_at)
            VALUES (?, ?, 'completed', '/path/file.mkv', '2025-01-15T12:00:00Z')
        """,
            [
                ("job-1", "scan"),
                ("job-2", "transcode"),
                ("job-3", "scan"),
            ],
        )

        result = get_jobs_report(test_db, job_type="scan")
        assert len(result) == 2
        assert all(r["type"] == "scan" for r in result)

    def test_filter_by_status(self, test_db):
        """Filter jobs by status."""
        test_db.executemany(
            """
            INSERT INTO jobs (id, job_type, status, file_path, created_at)
            VALUES (?, 'scan', ?, '/path/file.mkv', '2025-01-15T12:00:00Z')
        """,
            [
                ("job-1", "completed"),
                ("job-2", "failed"),
                ("job-3", "completed"),
            ],
        )

        result = get_jobs_report(test_db, status="failed")
        assert len(result) == 1
        assert result[0]["status"] == "failed"

    def test_limit(self, test_db):
        """Respect limit parameter."""
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO jobs (id, job_type, status, file_path, created_at)
                VALUES (?, 'scan', 'completed', '/path/f.mkv', '2025-01-15T12:00:00Z')
            """,
                (f"job-{i}",),
            )

        result = get_jobs_report(test_db, limit=5)
        assert len(result) == 5

    def test_no_limit(self, test_db):
        """Return all rows when limit is None."""
        for i in range(10):
            test_db.execute(
                """
                INSERT INTO jobs (id, job_type, status, file_path, created_at)
                VALUES (?, 'scan', 'completed', '/path/f.mkv', '2025-01-15T12:00:00Z')
            """,
                (f"job-{i}",),
            )

        result = get_jobs_report(test_db, limit=None)
        assert len(result) == 10

    def test_time_filter(self, test_db):
        """Filter jobs by time range."""
        test_db.executemany(
            """
            INSERT INTO jobs (id, job_type, status, file_path, created_at)
            VALUES (?, 'scan', 'completed', '/path/file.mkv', ?)
        """,
            [
                ("job-1", "2025-01-10T12:00:00Z"),
                ("job-2", "2025-01-15T12:00:00Z"),
                ("job-3", "2025-01-20T12:00:00Z"),
            ],
        )

        since = datetime(2025, 1, 12, tzinfo=timezone.utc)
        until = datetime(2025, 1, 18, tzinfo=timezone.utc)
        time_filter = TimeFilter(since=since, until=until)

        result = get_jobs_report(test_db, time_filter=time_filter)
        assert len(result) == 1
        assert result[0]["job_id"] == "job-2"[:8]


class TestGetLibraryReport:
    """Tests for get_library_report function."""

    def test_empty_database(self, test_db):
        """Return empty list for empty database."""
        result = get_library_report(test_db)
        assert result == []

    def test_basic_query(self, test_db):
        """Query all library files."""
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (1, '/path/movie.mkv', 'movie.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, width, height, language)
            VALUES (1, 'video', 1920, 1080, NULL)
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, language)
            VALUES (1, 'audio', 'eng')
        """)

        result = get_library_report(test_db)
        assert len(result) == 1
        assert result[0]["path"] == "/path/movie.mkv"
        assert result[0]["resolution"] == "1080p"
        assert "eng" in result[0]["audio_languages"]

    def test_filter_by_resolution(self, test_db):
        """Filter by resolution."""
        # 4K file
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (1, '/path/4k.mkv', '4k.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, width, height)
            VALUES (1, 'video', 3840, 2160)
        """)

        # 1080p file
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (2, '/path/1080p.mkv', '1080p.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, width, height)
            VALUES (2, 'video', 1920, 1080)
        """)

        result = get_library_report(test_db, resolution="4K")
        assert len(result) == 1
        assert result[0]["resolution"] == "4K"

    def test_filter_by_language(self, test_db):
        """Filter by audio language."""
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (1, '/path/eng.mkv', 'eng.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, language)
            VALUES (1, 'audio', 'eng')
        """)

        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (2, '/path/jpn.mkv', 'jpn.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type, language)
            VALUES (2, 'audio', 'jpn')
        """)

        result = get_library_report(test_db, language="jpn")
        assert len(result) == 1
        assert "jpn" in result[0]["audio_languages"]

    def test_filter_has_subtitles(self, test_db):
        """Filter by subtitle presence."""
        # File with subtitles
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (1, '/path/subs.mkv', 'subs.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)
        test_db.execute("""
            INSERT INTO tracks (file_id, track_type) VALUES (1, 'subtitle')
        """)

        # File without subtitles
        test_db.execute("""
            INSERT INTO files
                (id, path, filename, container_format, scanned_at, scan_status)
            VALUES (2, '/path/nosubs.mkv', 'nosubs.mkv', 'mkv',
                    '2025-01-15T12:00:00Z', 'ok')
        """)

        result = get_library_report(test_db, has_subtitles=True)
        assert len(result) == 1
        assert result[0]["has_subtitles"] == "Yes"

        result = get_library_report(test_db, has_subtitles=False)
        assert len(result) == 1
        assert result[0]["has_subtitles"] == "No"


class TestGetScansReport:
    """Tests for get_scans_report function."""

    def test_empty_database(self, test_db):
        """Return empty list for empty database."""
        result = get_scans_report(test_db)
        assert result == []

    def test_basic_query(self, test_db):
        """Query scan jobs."""
        summary = json.dumps(
            {"files_scanned": 100, "files_new": 10, "files_changed": 5}
        )
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, file_path, created_at,
                            started_at, completed_at, summary_json)
            VALUES ('scan-123', 'scan', 'completed', '/path/dir',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:05:00Z', ?)
        """,
            (summary,),
        )

        result = get_scans_report(test_db)
        assert len(result) == 1
        assert result[0]["scan_id"] == "scan-123"[:8]
        assert result[0]["files_scanned"] == 100
        assert result[0]["files_new"] == 10
        assert result[0]["files_changed"] == 5


class TestGetTranscodesReport:
    """Tests for get_transcodes_report function."""

    def test_empty_database(self, test_db):
        """Return empty list for empty database."""
        result = get_transcodes_report(test_db)
        assert result == []

    def test_basic_query(self, test_db):
        """Query transcode jobs."""
        policy = json.dumps({"source_codec": "h264", "target_codec": "hevc"})
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-123', 'transcode', 'completed', '/path/file.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:30:00Z', ?)
        """,
            (policy,),
        )

        result = get_transcodes_report(test_db)
        assert len(result) == 1
        assert result[0]["source_codec"] == "h264"
        assert result[0]["target_codec"] == "hevc"

    def test_filter_by_codec(self, test_db):
        """Filter by target codec."""
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, file_path, created_at, policy_json)
            VALUES ('tc-1', 'transcode', 'completed', '/path/file.mkv',
                    '2025-01-15T12:00:00Z', '{"target_codec": "hevc"}')
        """)
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, file_path, created_at, policy_json)
            VALUES ('tc-2', 'transcode', 'completed', '/path/file2.mkv',
                    '2025-01-15T12:00:00Z', '{"target_codec": "av1"}')
        """)

        result = get_transcodes_report(test_db, codec="hevc")
        assert len(result) == 1
        assert result[0]["target_codec"] == "hevc"

    def test_size_change_with_processing_stats(self, test_db):
        """Size change populated when processing_stats record exists."""
        # Create file
        test_db.execute("""
            INSERT INTO files (id, path, filename, size_bytes)
            VALUES (1, '/path/file.mkv', 'file.mkv', 1073741824)
        """)
        # Create transcode job
        test_db.execute("""
            INSERT INTO jobs (id, file_id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-123', 1, 'transcode', 'completed', '/path/file.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:30:00Z', '{"target_codec": "hevc"}')
        """)
        # Create processing_stats with size data (1 GB -> 500 MB = 50% reduction)
        test_db.execute("""
            INSERT INTO processing_stats (id, file_id, processed_at, policy_name,
                            size_before, size_after, size_change)
            VALUES ('stats-123', 1, '2025-01-15T12:15:00Z', 'test.yaml',
                    1073741824, 536870912, -536870912)
        """)

        result = get_transcodes_report(test_db)
        assert len(result) == 1
        # Size change should show reduction with percentage
        assert "-" in result[0]["size_change"]  # Negative (reduction)
        assert "%" in result[0]["size_change"]  # Has percentage
        assert "MB" in result[0]["size_change"]  # Has unit

    def test_size_change_na_without_processing_stats(self, test_db):
        """Size change shows N/A when no processing_stats record exists."""
        # Create transcode job without processing_stats
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-456', 'transcode', 'completed', '/path/file.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:30:00Z', '{"target_codec": "hevc"}')
        """)

        result = get_transcodes_report(test_db)
        assert len(result) == 1
        assert result[0]["size_change"] == "N/A"

    def test_size_change_stats_outside_job_window(self, test_db):
        """Size change N/A when stats record is outside job time window."""
        # Create file and job
        test_db.execute("""
            INSERT INTO files (id, path, filename, size_bytes)
            VALUES (2, '/path/file2.mkv', 'file2.mkv', 2147483648)
        """)
        test_db.execute("""
            INSERT INTO jobs (id, file_id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-789', 2, 'transcode', 'completed', '/path/file2.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:30:00Z', '{"target_codec": "hevc"}')
        """)
        # Create processing_stats BEFORE job started (should not match)
        test_db.execute("""
            INSERT INTO processing_stats (id, file_id, processed_at, policy_name,
                            size_before, size_after, size_change)
            VALUES ('stats-old', 2, '2025-01-14T12:00:00Z', 'test.yaml',
                    2147483648, 1073741824, -1073741824)
        """)

        result = get_transcodes_report(test_db)
        assert len(result) == 1
        assert result[0]["size_change"] == "N/A"

    def test_multiple_stats_records_returns_single_row(self, test_db):
        """When multiple stats records match a job, return one row with most recent."""
        # Create file
        test_db.execute("""
            INSERT INTO files (id, path, filename, size_bytes)
            VALUES (3, '/path/file3.mkv', 'file3.mkv', 2147483648)
        """)
        # Create transcode job
        test_db.execute("""
            INSERT INTO jobs (id, file_id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-multi', 3, 'transcode', 'completed', '/path/file3.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    '2025-01-15T12:30:00Z', '{"target_codec": "hevc"}')
        """)
        # Create TWO processing_stats records within job window
        # First stats record (earlier, should NOT be used)
        test_db.execute("""
            INSERT INTO processing_stats (id, file_id, processed_at, policy_name,
                            size_before, size_after, size_change)
            VALUES ('stats-early', 3, '2025-01-15T12:10:00Z', 'test.yaml',
                    2147483648, 1610612736, -536870912)
        """)
        # Second stats record (later, should be used - 50% reduction)
        test_db.execute("""
            INSERT INTO processing_stats (id, file_id, processed_at, policy_name,
                            size_before, size_after, size_change)
            VALUES ('stats-late', 3, '2025-01-15T12:20:00Z', 'test.yaml',
                    2147483648, 1073741824, -1073741824)
        """)

        result = get_transcodes_report(test_db)
        # Should return exactly 1 row (not duplicates)
        assert len(result) == 1
        # Should use the most recent stats (50% reduction = 1GB change)
        assert "-" in result[0]["size_change"]
        assert "GB" in result[0]["size_change"]
        assert "50%" in result[0]["size_change"]

    def test_in_progress_job_matches_stats(self, test_db):
        """In-progress jobs (completed_at=NULL) can match stats."""
        # Create file
        test_db.execute("""
            INSERT INTO files (id, path, filename, size_bytes)
            VALUES (4, '/path/file4.mkv', 'file4.mkv', 1073741824)
        """)
        # Create in-progress transcode job (no completed_at)
        test_db.execute("""
            INSERT INTO jobs (id, file_id, job_type, status, file_path, created_at,
                            started_at, completed_at, policy_json)
            VALUES ('tc-running', 4, 'transcode', 'running', '/path/file4.mkv',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z',
                    NULL, '{"target_codec": "hevc"}')
        """)
        # Create processing_stats within job window (after started_at, before now)
        test_db.execute("""
            INSERT INTO processing_stats (id, file_id, processed_at, policy_name,
                            size_before, size_after, size_change)
            VALUES ('stats-running', 4, '2025-01-15T12:15:00Z', 'test.yaml',
                    1073741824, 536870912, -536870912)
        """)

        result = get_transcodes_report(test_db)
        assert len(result) == 1
        # Should still match stats even with NULL completed_at
        assert "-" in result[0]["size_change"]
        assert "50%" in result[0]["size_change"]


class TestGetPolicyApplyReport:
    """Tests for get_policy_apply_report function."""

    def test_empty_database(self, test_db):
        """Return empty list for empty database."""
        result = get_policy_apply_report(test_db)
        assert result == []

    def test_basic_query(self, test_db):
        """Query policy apply jobs."""
        files_affected = json.dumps(
            [
                {"path": "/path/file1.mkv", "actions": ["set_title"]},
                {"path": "/path/file2.mkv", "actions": ["set_language"]},
            ]
        )
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, file_path, policy_name,
                            created_at, started_at, files_affected_json)
            VALUES ('apply-123', 'apply', 'completed', '/path/dir', 'normalize.yaml',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z', ?)
        """,
            (files_affected,),
        )

        result = get_policy_apply_report(test_db)
        assert len(result) == 1
        assert result[0]["policy_name"] == "normalize.yaml"
        assert result[0]["files_affected"] == 2

    def test_verbose_mode(self, test_db):
        """Return per-file details in verbose mode."""
        files_affected = json.dumps(
            [
                {"path": "/path/file1.mkv", "changes": "set_title"},
                {"path": "/path/file2.mkv", "changes": "set_language"},
            ]
        )
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, file_path, policy_name,
                            created_at, started_at, files_affected_json)
            VALUES ('apply-123', 'apply', 'completed', '/path/dir', 'normalize.yaml',
                    '2025-01-15T12:00:00Z', '2025-01-15T12:00:00Z', ?)
        """,
            (files_affected,),
        )

        result = get_policy_apply_report(test_db, verbose=True)
        assert len(result) == 2
        assert result[0]["file_path"] == "/path/file1.mkv"
        assert result[1]["file_path"] == "/path/file2.mkv"

    def test_filter_by_policy(self, test_db):
        """Filter by policy name."""
        test_db.execute("""
            INSERT INTO jobs
                (id, job_type, status, file_path, policy_name, created_at)
            VALUES ('apply-1', 'apply', 'completed', '/path',
                    'normalize.yaml', '2025-01-15T12:00:00Z')
        """)
        test_db.execute("""
            INSERT INTO jobs
                (id, job_type, status, file_path, policy_name, created_at)
            VALUES ('apply-2', 'apply', 'completed', '/path',
                    'transcode.yaml', '2025-01-15T12:00:00Z')
        """)

        result = get_policy_apply_report(test_db, policy_name="normalize")
        assert len(result) == 1
        assert "normalize" in result[0]["policy_name"]


class TestDataclassesToDict:
    """Tests for dataclass to_dict methods."""

    def test_job_report_row(self):
        """JobReportRow converts to dict."""
        row = JobReportRow(
            job_id="abc12345",
            type="scan",
            status="completed",
            target="/path/file.mkv",
            started_at="2025-01-15 12:00:00",
            completed_at="2025-01-15 12:05:00",
            duration="5m 0s",
            error="-",
        )
        d = row.to_dict()
        assert d["job_id"] == "abc12345"
        assert d["type"] == "scan"

    def test_library_report_row(self):
        """LibraryReportRow converts to dict."""
        row = LibraryReportRow(
            path="/path/movie.mkv",
            title="Movie",
            container="mkv",
            resolution="1080p",
            audio_languages="eng",
            has_subtitles="Yes",
            scanned_at="2025-01-15 12:00:00",
        )
        d = row.to_dict()
        assert d["path"] == "/path/movie.mkv"
        assert d["resolution"] == "1080p"


class TestLimitValidation:
    """Tests for limit parameter validation."""

    def test_negative_limit_rejected(self, test_db):
        """Test that negative limits are rejected."""
        with pytest.raises(ValueError, match="non-negative"):
            get_jobs_report(test_db, limit=-1)

    def test_zero_limit_accepted(self, test_db):
        """Test that zero limit is accepted."""
        # Zero is valid - returns empty result
        result = get_jobs_report(test_db, limit=0)
        assert result == []

    def test_huge_limit_rejected(self, test_db):
        """Test that limits exceeding MAX_LIMIT are rejected."""
        with pytest.raises(ValueError, match="too large"):
            get_jobs_report(test_db, limit=MAX_LIMIT + 1)

    def test_max_limit_accepted(self, test_db):
        """Test that MAX_LIMIT is accepted."""
        # Should not raise
        result = get_jobs_report(test_db, limit=MAX_LIMIT)
        assert result == []

    def test_none_limit_accepted(self, test_db):
        """Test that None limit (no limit) is accepted."""
        result = get_jobs_report(test_db, limit=None)
        assert result == []

    def test_library_report_limit_validation(self, test_db):
        """Test limit validation in get_library_report."""
        with pytest.raises(ValueError, match="non-negative"):
            get_library_report(test_db, limit=-1)

    def test_scans_report_limit_validation(self, test_db):
        """Test limit validation in get_scans_report."""
        with pytest.raises(ValueError, match="non-negative"):
            get_scans_report(test_db, limit=-1)

    def test_transcodes_report_limit_validation(self, test_db):
        """Test limit validation in get_transcodes_report."""
        with pytest.raises(ValueError, match="non-negative"):
            get_transcodes_report(test_db, limit=-1)

    def test_policy_apply_report_limit_validation(self, test_db):
        """Test limit validation in get_policy_apply_report."""
        with pytest.raises(ValueError, match="non-negative"):
            get_policy_apply_report(test_db, limit=-1)


class TestPolicyNameWildcardEscaping:
    """Tests for SQL wildcard escaping in policy name filter."""

    def test_percent_in_policy_name(self, test_db):
        """Test that % in policy names is escaped and matched literally."""
        # Insert job with policy name containing %
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, policy_name, created_at)
            VALUES (?, 'apply', 'completed', ?, '2025-01-15T12:00:00Z')
            """,
            ("job-1", "policy_50%_discount"),
        )
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, policy_name, created_at)
            VALUES (?, 'apply', 'completed', ?, '2025-01-15T12:00:00Z')
            """,
            ("job-2", "policy_normal"),
        )

        # Search for literal "50%" should find only the first one
        result = get_policy_apply_report(test_db, policy_name="50%")
        assert len(result) == 1
        assert "50%" in result[0]["policy_name"]

    def test_underscore_in_policy_name(self, test_db):
        """Test that _ in policy names is escaped and matched literally."""
        # Insert jobs with similar names
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, policy_name, created_at)
            VALUES ('job-1', 'apply', 'completed', 'policy_v1', '2025-01-15T12:00:00Z')
        """)
        test_db.execute("""
            INSERT INTO jobs (id, job_type, status, policy_name, created_at)
            VALUES ('job-2', 'apply', 'completed', 'policyXv1', '2025-01-15T12:00:00Z')
        """)

        # Search for "_v1" should match only "policy_v1", not "policyXv1"
        result = get_policy_apply_report(test_db, policy_name="_v1")
        assert len(result) == 1
        assert "_v1" in result[0]["policy_name"]

    def test_backslash_in_policy_name(self, test_db):
        """Test that backslash in policy names is escaped."""
        # Insert job with policy name containing backslash
        test_db.execute(
            """
            INSERT INTO jobs (id, job_type, status, policy_name, created_at)
            VALUES (?, 'apply', 'completed', ?, '2025-01-15T12:00:00Z')
            """,
            ("job-1", "path\\to\\policy"),
        )

        # Search for backslash should work
        result = get_policy_apply_report(test_db, policy_name="\\")
        assert len(result) == 1


class TestForeignKeysEnabled:
    """Tests to verify foreign keys are enabled in test database."""

    def test_foreign_keys_pragma_enabled(self, test_db):
        """Verify foreign keys are enabled in test database."""
        cursor = test_db.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
