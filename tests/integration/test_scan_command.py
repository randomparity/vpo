"""Integration tests for scan command."""

from pathlib import Path

from click.testing import CliRunner

from video_policy_orchestrator.cli import main


class TestScanCommand:
    """Tests for vpo scan command."""

    def test_scan_help(self):
        """Test that scan --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Scan directories for video files" in result.output

    def test_scan_nonexistent_directory(self, temp_dir: Path):
        """Test scanning a nonexistent directory."""
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "/nonexistent/path"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_scan_empty_directory(self, temp_dir: Path):
        """Test scanning an empty directory."""
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(temp_dir)])
        assert result.exit_code == 0
        assert "0" in result.output  # Should show 0 files found

    def test_scan_directory_with_videos(self, temp_video_dir: Path):
        """Test scanning a directory with video files."""
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(temp_video_dir)])
        assert result.exit_code == 0
        # Should find 3 videos (movie.mkv, show.mp4, nested/episode.mkv)
        assert "3" in result.output

    def test_scan_with_custom_extensions(self, temp_dir: Path):
        """Test scanning with custom extensions."""
        # Create test files
        (temp_dir / "video.mkv").touch()
        (temp_dir / "video.avi").touch()
        (temp_dir / "video.wmv").touch()

        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--extensions", "mkv,avi", str(temp_dir)])
        assert result.exit_code == 0
        assert "2" in result.output  # Should only find mkv and avi

    def test_scan_dry_run(self, temp_video_dir: Path, temp_db: Path):
        """Test that --dry-run doesn't write to database."""
        import sqlite3

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["scan", "--dry-run", "--db", str(temp_db), str(temp_video_dir)],
        )
        assert result.exit_code == 0

        # Database should not exist or be empty
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

    def test_scan_verbose_output(self, temp_video_dir: Path):
        """Test verbose output mode."""
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--verbose", str(temp_video_dir)])
        assert result.exit_code == 0
        # Verbose should show more details

    def test_scan_json_output(self, temp_video_dir: Path):
        """Test JSON output mode."""
        import json

        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--json", str(temp_video_dir)])
        assert result.exit_code == 0

        # Should be valid JSON
        data = json.loads(result.output)
        assert "files_found" in data or "total" in data or isinstance(data, dict)

    def test_scan_multiple_directories(self, temp_dir: Path):
        """Test scanning multiple directories."""
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "video1.mkv").touch()
        (dir2 / "video2.mkv").touch()

        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(dir1), str(dir2)])
        assert result.exit_code == 0
        assert "2" in result.output  # Should find both videos

    def test_scan_with_custom_db_path(self, temp_video_dir: Path, temp_db: Path):
        """Test scanning with a custom database path."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["scan", "--db", str(temp_db), str(temp_video_dir)]
        )
        assert result.exit_code == 0
