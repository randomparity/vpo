"""Tests for core subprocess utilities."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.core.subprocess_utils import run_command


class TestRunCommand:
    """Tests for run_command function."""

    def test_successful_command(self):
        """run_command returns stdout, stderr, returncode for successful command."""
        stdout, stderr, returncode = run_command(["echo", "hello"])

        assert stdout.strip() == "hello"
        assert returncode == 0

    def test_command_with_path_args(self):
        """run_command converts Path arguments to strings."""
        test_path = Path("/tmp")
        stdout, stderr, returncode = run_command(["ls", test_path])

        assert returncode == 0

    def test_command_failure_returns_non_zero(self):
        """run_command returns non-zero returncode for failed command."""
        stdout, stderr, returncode = run_command(["ls", "/nonexistent_path_12345"])

        assert returncode != 0
        assert stderr != ""

    def test_timeout_raises_exception(self):
        """run_command raises TimeoutExpired for long-running commands."""
        with pytest.raises(subprocess.TimeoutExpired):
            run_command(["sleep", "10"], timeout=1)

    def test_captures_stderr(self):
        """run_command captures stderr output."""
        # Use Python to write to stderr
        stdout, stderr, returncode = run_command(
            ["python", "-c", "import sys; sys.stderr.write('error message')"]
        )

        assert "error message" in stderr

    def test_captures_stdout(self):
        """run_command captures stdout output."""
        stdout, stderr, returncode = run_command(
            ["python", "-c", "print('output message')"]
        )

        assert "output message" in stdout.strip()

    def test_returns_empty_string_for_no_output(self):
        """run_command returns empty string when no output."""
        stdout, stderr, returncode = run_command(["true"])

        assert stdout == ""
        assert returncode == 0

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_passes_kwargs_to_subprocess(self, mock_run: MagicMock):
        """run_command passes additional kwargs to subprocess.run."""
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"], cwd="/tmp")

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_default_capture_output_true(self, mock_run: MagicMock):
        """run_command defaults to capture_output=True."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"])

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_default_text_true(self, mock_run: MagicMock):
        """run_command defaults to text=True."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"])

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["text"] is True

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_default_errors_replace(self, mock_run: MagicMock):
        """run_command defaults to errors='replace' for encoding."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"])

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["errors"] == "replace"

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_default_timeout(self, mock_run: MagicMock):
        """run_command uses default timeout of 120 seconds."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"])

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 120

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock):
        """run_command respects custom timeout parameter."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        run_command(["echo", "test"], timeout=60)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_handles_none_stdout(self, mock_run: MagicMock):
        """run_command handles None stdout gracefully."""
        mock_result = MagicMock()
        mock_result.stdout = None
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        stdout, stderr, returncode = run_command(["echo", "test"])

        assert stdout == ""

    @patch("vpo.core.subprocess_utils.subprocess.run")
    def test_handles_none_stderr(self, mock_run: MagicMock):
        """run_command handles None stderr gracefully."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = None
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        stdout, stderr, returncode = run_command(["echo", "test"])

        assert stderr == ""
