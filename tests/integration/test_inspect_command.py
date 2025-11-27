"""Integration tests for the vpo inspect command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from video_policy_orchestrator.cli import main
from video_policy_orchestrator.cli.exit_codes import ExitCode
from video_policy_orchestrator.db.models import IntrospectionResult, TrackInfo


class TestInspectCommand:
    """Tests for the vpo inspect CLI command."""

    def test_inspect_help(self) -> None:
        """Test that inspect command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", "--help"])

        assert result.exit_code == 0
        assert "Inspect a media file" in result.output
        assert "--format" in result.output

    def test_inspect_file_not_found(self, temp_dir: Path) -> None:
        """Test inspect with non-existent file returns appropriate exit code."""
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(temp_dir / "nonexistent.mkv")])

        assert result.exit_code == ExitCode.TARGET_NOT_FOUND
        assert "File not found" in result.output

    @patch(
        "video_policy_orchestrator.cli.inspect.FFprobeIntrospector.is_available",
        return_value=False,
    )
    def test_inspect_ffprobe_not_installed(
        self, mock_is_available: MagicMock, temp_dir: Path
    ) -> None:
        """Test inspect when ffprobe is not installed returns appropriate exit code."""
        # Create a file so the file-not-found check passes
        test_file = temp_dir / "test.mkv"
        test_file.touch()

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(test_file)])

        assert result.exit_code == ExitCode.FFPROBE_NOT_FOUND
        assert "ffprobe is not installed" in result.output

    @patch(
        "video_policy_orchestrator.cli.inspect.FFprobeIntrospector.is_available",
        return_value=True,
    )
    @patch("video_policy_orchestrator.cli.inspect.FFprobeIntrospector")
    def test_inspect_human_output(
        self,
        mock_introspector_class: MagicMock,
        mock_is_available: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test inspect command with human output format."""
        # Create a file
        test_file = temp_dir / "movie.mkv"
        test_file.touch()

        # Mock the introspector
        mock_instance = MagicMock()
        mock_introspector_class.return_value = mock_instance
        mock_instance.get_file_info.return_value = IntrospectionResult(
            file_path=test_file,
            container_format="matroska,webm",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="h264",
                    width=1920,
                    height=1080,
                    frame_rate="24000/1001",
                    is_default=True,
                ),
                TrackInfo(
                    index=1,
                    track_type="audio",
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    is_default=True,
                ),
            ],
            warnings=[],
        )

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(test_file)])

        assert result.exit_code == 0
        assert "movie.mkv" in result.output
        assert "Matroska" in result.output
        assert "Video:" in result.output
        assert "Audio:" in result.output
        assert "h264" in result.output
        assert "1920x1080" in result.output
        assert "stereo" in result.output

    @patch(
        "video_policy_orchestrator.cli.inspect.FFprobeIntrospector.is_available",
        return_value=True,
    )
    @patch("video_policy_orchestrator.cli.inspect.FFprobeIntrospector")
    def test_inspect_json_output(
        self,
        mock_introspector_class: MagicMock,
        mock_is_available: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test inspect command with JSON output format."""
        # Create a file
        test_file = temp_dir / "movie.mkv"
        test_file.touch()

        # Mock the introspector
        mock_instance = MagicMock()
        mock_introspector_class.return_value = mock_instance
        mock_instance.get_file_info.return_value = IntrospectionResult(
            file_path=test_file,
            container_format="matroska,webm",
            tracks=[
                TrackInfo(
                    index=0,
                    track_type="video",
                    codec="h264",
                    width=1920,
                    height=1080,
                    frame_rate="24/1",
                    is_default=True,
                ),
                TrackInfo(
                    index=1,
                    track_type="audio",
                    codec="aac",
                    language="eng",
                    channels=2,
                    channel_layout="stereo",
                    is_default=True,
                ),
            ],
            warnings=[],
        )

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(test_file), "--format", "json"])

        assert result.exit_code == 0

        # Parse JSON output
        data = json.loads(result.output)

        assert "movie.mkv" in data["file"]
        assert data["container"] == "matroska,webm"
        assert len(data["tracks"]) == 2

        # Check video track
        video = data["tracks"][0]
        assert video["type"] == "video"
        assert video["codec"] == "h264"
        assert video["width"] == 1920
        assert video["height"] == 1080

        # Check audio track
        audio = data["tracks"][1]
        assert audio["type"] == "audio"
        assert audio["codec"] == "aac"
        assert audio["channels"] == 2

    @patch(
        "video_policy_orchestrator.cli.inspect.FFprobeIntrospector.is_available",
        return_value=True,
    )
    @patch("video_policy_orchestrator.cli.inspect.FFprobeIntrospector")
    def test_inspect_with_warnings(
        self,
        mock_introspector_class: MagicMock,
        mock_is_available: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test inspect command displays warnings."""
        # Create a file
        test_file = temp_dir / "problem.mkv"
        test_file.touch()

        # Mock the introspector with warnings
        mock_instance = MagicMock()
        mock_introspector_class.return_value = mock_instance
        mock_instance.get_file_info.return_value = IntrospectionResult(
            file_path=test_file,
            container_format="matroska,webm",
            tracks=[],
            warnings=["No streams found in file"],
        )

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(test_file)])

        assert result.exit_code == 0
        assert "Warnings:" in result.output
        assert "No streams found" in result.output

    @patch(
        "video_policy_orchestrator.cli.inspect.FFprobeIntrospector.is_available",
        return_value=True,
    )
    @patch("video_policy_orchestrator.cli.inspect.FFprobeIntrospector")
    def test_inspect_parse_error(
        self,
        mock_introspector_class: MagicMock,
        mock_is_available: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test inspect command handles parse errors with appropriate exit code."""
        from video_policy_orchestrator.introspector.interface import (
            MediaIntrospectionError,
        )

        # Create a file
        test_file = temp_dir / "corrupt.mkv"
        test_file.touch()

        # Mock the introspector to raise an error
        mock_instance = MagicMock()
        mock_introspector_class.return_value = mock_instance
        mock_instance.get_file_info.side_effect = MediaIntrospectionError(
            "Invalid container format"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", str(test_file)])

        assert result.exit_code == ExitCode.PARSE_ERROR
        assert "Could not parse file" in result.output
        assert "Invalid container format" in result.output
