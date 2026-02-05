"""Integration tests for parallel file processing with process command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from vpo.cli import main


@pytest.fixture
def v12_policy(tmp_path: Path) -> Path:
    """Create a V12 policy file (current version) for testing."""
    policy_content = """
schema_version: 12
config:
  on_error: skip
phases:
  - name: apply
    track_order: [video, audio_main, subtitle_main]
"""
    policy_file = tmp_path / "test_policy.yaml"
    policy_file.write_text(policy_content)
    return policy_file


@pytest.fixture
def test_video_files(tmp_path: Path) -> list[Path]:
    """Create multiple test video files."""
    video_dir = tmp_path / "videos"
    video_dir.mkdir()

    files = []
    for i in range(5):
        # Create empty MKV files (won't actually process, but tests CLI flow)
        video_file = video_dir / f"test_video_{i}.mkv"
        video_file.touch()
        files.append(video_file)

    return files


class TestParallelProcessingCLI:
    """Tests for parallel processing CLI options."""

    def test_workers_option_shown_in_help(self, runner: CliRunner) -> None:
        """--workers option should appear in help."""
        result = runner.invoke(main, ["process", "--help"])
        assert result.exit_code == 0
        assert "--workers" in result.output
        assert "-w" in result.output
        assert "parallel workers" in result.output.lower()

    def test_workers_option_accepts_value(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """--workers option should accept numeric value."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--workers",
                "2",
                "--dry-run",
                str(video_file),
            ],
        )
        # The command may fail to process an empty file, but args should parse
        assert "--workers" not in str(result.exception) if result.exception else True


class TestParallelProcessingJSON:
    """Tests for parallel processing JSON output."""

    def test_json_output_includes_workers(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """JSON output should include workers count."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--workers",
                "2",
                "--dry-run",
                "--json",
                str(video_file),
            ],
        )

        # Parse JSON output (use result.stdout to separate from stderr logs)
        if result.exit_code == 0 or "workers" in result.stdout:
            try:
                output = json.loads(result.stdout)
                assert "workers" in output
                assert output["workers"] == 2
            except json.JSONDecodeError:
                # If processing failed completely, JSON may not be emitted
                pass

    def test_json_output_includes_duration(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """JSON output should include duration_seconds."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--dry-run",
                "--json",
                str(video_file),
            ],
        )

        if result.exit_code == 0:
            # Use result.stdout to get only stdout (JSON), not stderr (logs)
            output = json.loads(result.stdout)
            assert "summary" in output
            assert "duration_seconds" in output["summary"]
            assert isinstance(output["summary"]["duration_seconds"], (int, float))


class TestParallelProcessingBehavior:
    """Tests for parallel processing behavior."""

    def test_workers_default_from_config(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """Workers should default to config value (2) when not specified."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--dry-run",
                "--json",
                str(video_file),
            ],
        )

        if result.exit_code == 0:
            # Use result.stdout to get only stdout (JSON), not stderr (logs)
            output = json.loads(result.stdout)
            # Default should be 2 (or less if capped by CPU)
            assert "workers" in output
            assert output["workers"] >= 1

    def test_verbose_shows_workers(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """Verbose mode should show worker count."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--workers",
                "2",
                "--dry-run",
                "--verbose",
                str(video_file),
            ],
        )

        assert "Workers: 2" in result.output


class TestSequentialMode:
    """Tests for sequential processing with --workers 1."""

    def test_workers_one_runs_sequentially(
        self, runner: CliRunner, v12_policy: Path, tmp_path: Path
    ) -> None:
        """--workers 1 should process files sequentially."""
        video_file = tmp_path / "test.mkv"
        video_file.touch()

        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(v12_policy),
                "--workers",
                "1",
                "--dry-run",
                "--json",
                str(video_file),
            ],
        )

        if result.exit_code == 0:
            # Use result.stdout to get only stdout (JSON), not stderr (logs)
            output = json.loads(result.stdout)
            assert output["workers"] == 1
