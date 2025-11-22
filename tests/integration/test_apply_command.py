"""Integration tests for the vpo apply command."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from video_policy_orchestrator.cli import main
from video_policy_orchestrator.db.models import FileRecord, TrackRecord
from video_policy_orchestrator.db.schema import create_schema

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def policy_file(temp_dir: Path) -> Path:
    """Create a minimal valid policy file."""
    policy_path = temp_dir / "test-policy.yaml"
    policy_path.write_text("""
schema_version: 1
track_order:
  - video
  - audio_main
  - subtitle_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def invalid_policy_file(temp_dir: Path) -> Path:
    """Create an invalid policy file (invalid YAML)."""
    policy_path = temp_dir / "invalid-policy.yaml"
    policy_path.write_text("""
schema_version: "not_an_integer"
track_order: invalid
""")
    return policy_path


@pytest.fixture
def test_mkv(temp_dir: Path) -> Path:
    """Create a test MKV file."""
    mkv_path = temp_dir / "test.mkv"
    mkv_path.write_bytes(b"fake mkv content")
    return mkv_path


@pytest.fixture
def test_mp4(temp_dir: Path) -> Path:
    """Create a test MP4 file."""
    mp4_path = temp_dir / "test.mp4"
    mp4_path.write_bytes(b"fake mp4 content")
    return mp4_path


@pytest.fixture
def db_with_file(temp_db: Path, test_mkv: Path) -> tuple[Path, int]:
    """Create a database with a scanned file and tracks."""
    conn = sqlite3.connect(str(temp_db))
    create_schema(conn)

    # Insert file record
    conn.execute(
        """
        INSERT INTO files (path, filename, directory, extension, size_bytes,
                          modified_at, content_hash, container_format)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(test_mkv),
            test_mkv.name,
            str(test_mkv.parent),
            ".mkv",
            test_mkv.stat().st_size,
            "2024-01-01T00:00:00Z",
            "abc123",
            "matroska",
        ),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert track records
    tracks = [
        (file_id, 0, "video", "h264", None, None, 1, 0, None, None, 1920, 1080, "24"),
        (file_id, 1, "audio", "aac", "eng", None, 1, 0, 2, "stereo", None, None, None),
        (
            file_id,
            2,
            "subtitle",
            "subrip",
            "eng",
            None,
            0,
            0,
            None,
            None,
            None,
            None,
            None,
        ),  # noqa: E501
    ]
    conn.executemany(
        """
        INSERT INTO tracks (file_id, track_index, track_type, codec, language,
                           title, is_default, is_forced, channels, channel_layout,
                           width, height, frame_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tracks,
    )
    conn.commit()
    conn.close()

    return temp_db, file_id


# =============================================================================
# Help and Basic Validation Tests
# =============================================================================


class TestApplyCommandBasics:
    """Basic tests for apply command help and validation."""

    def test_apply_help(self) -> None:
        """Test that apply --help displays usage information."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--help"])

        assert result.exit_code == 0
        assert "Apply a policy to a media file" in result.output
        assert "--policy" in result.output
        assert "--dry-run" in result.output
        assert "--json" in result.output

    def test_apply_missing_policy_option(self, test_mkv: Path) -> None:
        """Test that apply fails when --policy is not provided."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply", str(test_mkv)])

        assert result.exit_code == 2  # Click's error for missing required option
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_apply_missing_target(self, policy_file: Path) -> None:
        """Test that apply fails when target file is not provided."""
        runner = CliRunner()
        result = runner.invoke(main, ["apply", "--policy", str(policy_file)])

        assert result.exit_code == 2  # Click's error for missing argument


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestApplyErrorHandling:
    """Tests for apply command error handling."""

    def test_apply_policy_not_found(self, test_mkv: Path) -> None:
        """Test exit code 2 when policy file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", "/nonexistent/policy.yaml", str(test_mkv)]
        )

        assert result.exit_code == 2
        assert "Policy file not found" in result.output or "not found" in result.output

    def test_apply_policy_validation_error(
        self, invalid_policy_file: Path, test_mkv: Path
    ) -> None:
        """Test exit code 2 when policy file is invalid."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(invalid_policy_file), str(test_mkv)]
        )

        assert result.exit_code == 2

    def test_apply_target_not_found(self, policy_file: Path, temp_dir: Path) -> None:
        """Test exit code 3 when target file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["apply", "--policy", str(policy_file), str(temp_dir / "nonexistent.mkv")],
        )

        assert result.exit_code == 3
        assert "Target file not found" in result.output or "not found" in result.output

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    def test_apply_target_not_in_database(
        self, mock_get_conn: MagicMock, policy_file: Path, test_mkv: Path
    ) -> None:
        """Test exit code 3 when target file is not in database."""
        # Mock an empty database response
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(policy_file), str(test_mkv)]
        )

        assert result.exit_code == 3
        assert "not found in database" in result.output or "scan" in result.output


# =============================================================================
# Dry-Run Mode Tests
# =============================================================================


class TestApplyDryRun:
    """Tests for apply command dry-run mode."""

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    def test_apply_dry_run_human_output(
        self,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mkv: Path,
    ) -> None:
        """Test dry-run mode produces human-readable output."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mkv),
            filename=test_mkv.name,
            directory=str(test_mkv.parent),
            extension=".mkv",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=True,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
            TrackRecord(
                id=2,
                file_id=1,
                track_index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title=None,
                is_default=False,
                is_forced=False,
                channels=2,
                channel_layout="stereo",
                width=None,
                height=None,
                frame_rate=None,
            ),
        ]

        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(policy_file), "--dry-run", str(test_mkv)]
        )

        assert result.exit_code == 0
        assert "Policy:" in result.output
        assert "Target:" in result.output

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    def test_apply_dry_run_json_output(
        self,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mkv: Path,
    ) -> None:
        """Test dry-run mode produces valid JSON output."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mkv),
            filename=test_mkv.name,
            directory=str(test_mkv.parent),
            extension=".mkv",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=True,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
        ]

        runner = CliRunner()
        args = ["apply", "-p", str(policy_file), "--dry-run", "--json", str(test_mkv)]
        result = runner.invoke(main, args)

        assert result.exit_code == 0

        # Parse JSON output
        data = json.loads(result.output)
        assert data["status"] == "dry_run"
        assert "policy" in data
        assert "target" in data
        assert "plan" in data

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    def test_apply_dry_run_no_changes(
        self,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mkv: Path,
    ) -> None:
        """Test dry-run mode when file already matches policy."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mkv),
            filename=test_mkv.name,
            directory=str(test_mkv.parent),
            extension=".mkv",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        # Tracks that already match policy (video default=True, audio eng default=True)
        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=True,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
            TrackRecord(
                id=2,
                file_id=1,
                track_index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title=None,
                is_default=True,
                is_forced=False,
                channels=2,
                channel_layout="stereo",
                width=None,
                height=None,
                frame_rate=None,
            ),
        ]

        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(policy_file), "--dry-run", str(test_mkv)]
        )

        assert result.exit_code == 0
        assert "No changes required" in result.output


# =============================================================================
# Tool Availability Tests
# =============================================================================


class TestApplyToolAvailability:
    """Tests for apply command tool availability checks."""

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    @patch("video_policy_orchestrator.cli.apply.check_tool_availability")
    def test_apply_tool_not_available_mkv(
        self,
        mock_tools: MagicMock,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mkv: Path,
    ) -> None:
        """Test exit code 4 when mkvpropedit is not available for MKV."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mkv),
            filename=test_mkv.name,
            directory=str(test_mkv.parent),
            extension=".mkv",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="mkv",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=False,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
        ]

        # No mkvpropedit available
        mock_tools.return_value = {
            "ffmpeg": True,
            "ffprobe": True,
            "mkvpropedit": False,
        }

        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(policy_file), str(test_mkv)]
        )

        assert result.exit_code == 4
        assert "mkvpropedit" in result.output.lower()

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    @patch("video_policy_orchestrator.cli.apply.check_tool_availability")
    def test_apply_tool_not_available_mp4(
        self,
        mock_tools: MagicMock,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mp4: Path,
    ) -> None:
        """Test exit code 4 when ffmpeg is not available for MP4."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mp4),
            filename=test_mp4.name,
            directory=str(test_mp4.parent),
            extension=".mp4",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="mp4",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=False,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
        ]

        # No ffmpeg available
        mock_tools.return_value = {
            "ffmpeg": False,
            "ffprobe": True,
            "mkvpropedit": True,
        }

        runner = CliRunner()
        result = runner.invoke(
            main, ["apply", "--policy", str(policy_file), str(test_mp4)]
        )

        assert result.exit_code == 4
        assert "ffmpeg" in result.output.lower()


# =============================================================================
# Verbose Output Tests
# =============================================================================


class TestApplyVerbose:
    """Tests for apply command verbose output."""

    @patch("video_policy_orchestrator.cli.apply.get_connection")
    @patch("video_policy_orchestrator.cli.apply.get_file_by_path")
    @patch("video_policy_orchestrator.cli.apply.get_tracks_for_file")
    def test_apply_verbose_output(
        self,
        mock_get_tracks: MagicMock,
        mock_get_file: MagicMock,
        mock_get_conn: MagicMock,
        policy_file: Path,
        test_mkv: Path,
    ) -> None:
        """Test verbose output shows additional details."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_file.return_value = FileRecord(
            id=1,
            path=str(test_mkv),
            filename=test_mkv.name,
            directory=str(test_mkv.parent),
            extension=".mkv",
            size_bytes=100,
            modified_at="2024-01-01T00:00:00Z",
            content_hash="abc123",
            container_format="matroska",
            scanned_at="2024-01-01T00:00:00Z",
            scan_status="completed",
            scan_error=None,
        )

        mock_get_tracks.return_value = [
            TrackRecord(
                id=1,
                file_id=1,
                track_index=0,
                track_type="video",
                codec="h264",
                language=None,
                title=None,
                is_default=True,
                is_forced=False,
                channels=None,
                channel_layout=None,
                width=1920,
                height=1080,
                frame_rate="24/1",
            ),
        ]

        runner = CliRunner()
        args = ["apply", "-p", str(policy_file), "--dry-run", "-v", str(test_mkv)]
        result = runner.invoke(main, args)

        assert result.exit_code == 0
        # Verbose mode should show evaluation info
        assert "Evaluating" in result.output or "tracks" in result.output


# =============================================================================
# JSON Output Error Tests
# =============================================================================


class TestApplyJsonErrors:
    """Tests for apply command JSON error output."""

    def test_apply_json_error_policy_not_found(self, test_mkv: Path) -> None:
        """Test JSON error output when policy not found."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["apply", "--policy", "/nonexistent/policy.yaml", "--json", str(test_mkv)],
        )

        assert result.exit_code == 2
        # Error output goes to stderr
        data = json.loads(result.output)
        assert data["status"] == "failed"
        assert "error" in data
        assert data["error"]["code"] == "POLICY_VALIDATION_ERROR"

    def test_apply_json_error_target_not_found(
        self, policy_file: Path, temp_dir: Path
    ) -> None:
        """Test JSON error output when target not found."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "apply",
                "--policy",
                str(policy_file),
                "--json",
                str(temp_dir / "nonexistent.mkv"),
            ],
        )

        assert result.exit_code == 3
        data = json.loads(result.output)
        assert data["status"] == "failed"
        assert data["error"]["code"] == "TARGET_NOT_FOUND"
