"""Tests for cli/output.py module."""

import json

import pytest

from vpo.cli.exit_codes import ExitCode
from vpo.cli.output import error_exit, warning_output


class TestErrorExit:
    """Tests for error_exit function."""

    def test_human_format_exit(self) -> None:
        """Human format should print 'Error: message' and exit."""
        with pytest.raises(SystemExit) as exc_info:
            error_exit("Something failed", ExitCode.GENERAL_ERROR, json_output=False)

        assert exc_info.value.code == 1

    def test_json_format_exit(self, capsys) -> None:
        """JSON format should print JSON error and exit."""
        with pytest.raises(SystemExit) as exc_info:
            error_exit("Something failed", ExitCode.TARGET_NOT_FOUND, json_output=True)

        assert exc_info.value.code == 20

        captured = capsys.readouterr()
        parsed = json.loads(captured.err)
        assert parsed["status"] == "failed"
        assert parsed["error"]["code"] == "TARGET_NOT_FOUND"
        assert parsed["error"]["message"] == "Something failed"

    def test_int_exit_code(self) -> None:
        """Should work with integer exit codes."""
        with pytest.raises(SystemExit) as exc_info:
            error_exit("Failed", 42, json_output=False)

        assert exc_info.value.code == 42


class TestWarningOutput:
    """Tests for warning_output function."""

    def test_human_warning_output(self, capsys) -> None:
        """Human format should print 'Warning: message'."""
        warning_output("This is a warning", json_output=False)

        captured = capsys.readouterr()
        assert "Warning: This is a warning" in captured.err

    def test_json_warning_suppressed(self, capsys) -> None:
        """JSON mode should suppress warning output."""
        warning_output("This is a warning", json_output=True)

        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""
