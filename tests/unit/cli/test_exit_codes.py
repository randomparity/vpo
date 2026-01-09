"""Tests for cli/exit_codes.py module."""

from vpo.cli.exit_codes import (
    APPLY_EXIT_CODES,
    DOCTOR_EXIT_CODES,
    INSPECT_EXIT_CODES,
    ExitCode,
)


class TestExitCode:
    """Tests for ExitCode enum."""

    def test_success_is_zero(self) -> None:
        """SUCCESS should be 0."""
        assert ExitCode.SUCCESS == 0

    def test_general_error_is_one(self) -> None:
        """GENERAL_ERROR should be 1."""
        assert ExitCode.GENERAL_ERROR == 1

    def test_exit_codes_are_integers(self) -> None:
        """All exit codes should be integers."""
        for code in ExitCode:
            assert isinstance(int(code), int)

    def test_exit_codes_are_unique(self) -> None:
        """All exit codes should have unique values."""
        values = [int(code) for code in ExitCode]
        assert len(values) == len(set(values))

    def test_exit_code_name_access(self) -> None:
        """Should be able to access name from code."""
        assert ExitCode.TARGET_NOT_FOUND.name == "TARGET_NOT_FOUND"

    def test_exit_code_ranges(self) -> None:
        """Exit codes should be within expected ranges."""
        # General errors (1-9)
        assert 1 <= ExitCode.GENERAL_ERROR <= 9
        assert 1 <= ExitCode.INTERRUPTED <= 9

        # Validation errors (10-19)
        assert 10 <= ExitCode.POLICY_VALIDATION_ERROR <= 19
        assert 10 <= ExitCode.CONFIG_ERROR <= 19
        assert 10 <= ExitCode.PROFILE_NOT_FOUND <= 19

        # Target errors (20-29)
        assert 20 <= ExitCode.TARGET_NOT_FOUND <= 29
        assert 20 <= ExitCode.FILE_NOT_IN_DATABASE <= 29

        # Tool errors (30-39)
        assert 30 <= ExitCode.TOOL_NOT_AVAILABLE <= 39
        assert 30 <= ExitCode.PLUGIN_UNAVAILABLE <= 39

        # Operation errors (40-49)
        assert 40 <= ExitCode.OPERATION_FAILED <= 49
        assert 40 <= ExitCode.DATABASE_ERROR <= 49

        # Analysis errors (50-59)
        assert 50 <= ExitCode.ANALYSIS_ERROR <= 59
        assert 50 <= ExitCode.PARSE_ERROR <= 59

        # Warning states (60-69)
        assert 60 <= ExitCode.WARNINGS <= 69
        assert 60 <= ExitCode.CRITICAL <= 69


class TestMappingTables:
    """Tests for backward compatibility mapping tables."""

    def test_apply_exit_codes_mapping(self) -> None:
        """APPLY_EXIT_CODES should map to correct ExitCode values."""
        assert APPLY_EXIT_CODES["EXIT_SUCCESS"] == ExitCode.SUCCESS
        assert APPLY_EXIT_CODES["EXIT_GENERAL_ERROR"] == ExitCode.GENERAL_ERROR
        assert (
            APPLY_EXIT_CODES["EXIT_POLICY_VALIDATION_ERROR"]
            == ExitCode.POLICY_VALIDATION_ERROR
        )
        assert APPLY_EXIT_CODES["EXIT_TARGET_NOT_FOUND"] == ExitCode.TARGET_NOT_FOUND
        assert (
            APPLY_EXIT_CODES["EXIT_TOOL_NOT_AVAILABLE"] == ExitCode.TOOL_NOT_AVAILABLE
        )
        assert APPLY_EXIT_CODES["EXIT_OPERATION_FAILED"] == ExitCode.OPERATION_FAILED

    def test_inspect_exit_codes_mapping(self) -> None:
        """INSPECT_EXIT_CODES should map to correct ExitCode values."""
        assert INSPECT_EXIT_CODES["EXIT_SUCCESS"] == ExitCode.SUCCESS
        assert INSPECT_EXIT_CODES["EXIT_FILE_NOT_FOUND"] == ExitCode.TARGET_NOT_FOUND
        assert (
            INSPECT_EXIT_CODES["EXIT_FFPROBE_NOT_INSTALLED"]
            == ExitCode.FFPROBE_NOT_FOUND
        )
        assert INSPECT_EXIT_CODES["EXIT_PARSE_ERROR"] == ExitCode.PARSE_ERROR
        assert INSPECT_EXIT_CODES["EXIT_ANALYSIS_ERROR"] == ExitCode.ANALYSIS_ERROR

    def test_doctor_exit_codes_mapping(self) -> None:
        """DOCTOR_EXIT_CODES should map to correct ExitCode values."""
        assert DOCTOR_EXIT_CODES["EXIT_OK"] == ExitCode.SUCCESS
        assert DOCTOR_EXIT_CODES["EXIT_WARNINGS"] == ExitCode.WARNINGS
        assert DOCTOR_EXIT_CODES["EXIT_CRITICAL"] == ExitCode.CRITICAL
