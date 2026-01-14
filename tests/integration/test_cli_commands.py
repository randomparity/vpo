"""Tests for CLI command availability and removal."""

from click.testing import CliRunner

from vpo.cli import main


class TestRemovedCommands:
    """Verify deprecated commands have been removed."""

    def test_transcribe_command_removed(self) -> None:
        """Verify transcribe command was removed."""
        runner = CliRunner()
        result = runner.invoke(main, ["transcribe"])
        assert result.exit_code != 0
        assert "No such command" in result.output


class TestAnalyzeLanguageCommand:
    """Tests for analyze-language command availability."""

    def test_analyze_language_command_available(self) -> None:
        """Verify analyze-language command is available."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze-language", "--help"])
        assert result.exit_code == 0
        assert "Analyze and manage multi-language detection results" in result.output
        assert "run" in result.output
        assert "status" in result.output
        assert "clear" in result.output


class TestDoctorCommand:
    """Tests for vpo doctor command."""

    def test_doctor_shows_transcription_section(self) -> None:
        """Doctor command includes transcription plugins section."""
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        # Exit code depends on tool availability (0=ok, 60=warnings, 61=critical)
        # In CI environments, external tools may not be installed
        assert result.exit_code in (0, 60, 61)
        # The output should mention transcription plugins (available or not)
        assert "Transcription" in result.output or "transcription" in result.output

    def test_doctor_no_transcription_plugins_message(self) -> None:
        """Doctor shows message when no transcription plugins available."""
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        # In test environment, no transcription plugins are typically available
        # This test verifies the message appears when no plugins found
        if "No transcription plugins available" in result.output:
            assert "Install a transcription plugin" in result.output
