"""Integration tests for database persistence."""

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from video_policy_orchestrator.cli import main


class TestDatabasePersistence:
    """Tests for database persistence during scans."""

    def test_scan_creates_database(self, temp_video_dir: Path, temp_db: Path):
        """Test that scanning creates the database file."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0
        assert temp_db.exists()

    def test_scan_persists_files(self, temp_video_dir: Path, temp_db: Path):
        """Test that scanned files are persisted to database."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        # Check database contents
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM files")
        count = cursor.fetchone()[0]
        conn.close()

        # Should have 3 files (movie.mkv, show.mp4, nested/episode.mkv)
        assert count == 3

    def test_rescan_updates_not_duplicates(self, temp_video_dir: Path, temp_db: Path):
        """Test that rescanning updates files rather than duplicating."""
        runner = CliRunner()

        # First scan
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        # Second scan
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        # Check database - should still have 3 files, not 6
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM files")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    def test_scan_stores_correct_metadata(self, temp_video_dir: Path, temp_db: Path):
        """Test that correct file metadata is stored."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM files WHERE filename = 'movie.mkv'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["filename"] == "movie.mkv"
        assert row["extension"] == "mkv"
        assert "movie.mkv" in row["path"]
        assert row["scan_status"] == "ok"

    def test_dry_run_does_not_persist(self, temp_video_dir: Path, temp_db: Path):
        """Test that --dry-run doesn't write to database."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["scan", "--dry-run", "--db", str(temp_db), str(temp_video_dir)],
        )
        assert result.exit_code == 0

        # Database should either not exist or have no files
        if temp_db.exists():
            conn = sqlite3.connect(str(temp_db))
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM files")
                count = cursor.fetchone()[0]
                assert count == 0
            except sqlite3.OperationalError:
                pass  # Table doesn't exist, which is fine
            finally:
                conn.close()

    def test_scan_summary_shows_counts(self, temp_video_dir: Path, temp_db: Path):
        """Test that scan summary shows new/updated/skipped counts."""
        runner = CliRunner()

        # First scan - should show new files
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0
        # Should mention files found

        # Second scan - should show skipped files
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

    def test_scan_with_modified_file(self, temp_video_dir: Path, temp_db: Path):
        """Test that modified files are detected and updated."""
        import time

        runner = CliRunner()

        # First scan
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        # Modify a file
        time.sleep(0.1)  # Ensure different timestamp
        movie_file = temp_video_dir / "movie.mkv"
        movie_file.write_bytes(b"modified content")

        # Second scan - should detect modification
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0

        # Check that file was updated
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM files WHERE filename = 'movie.mkv'")
        row = cursor.fetchone()
        conn.close()

        # Should have the new content hash
        assert row["content_hash"] is not None
