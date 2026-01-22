"""Tests for file_timestamp operation executor."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.core.file_utils import get_file_mtime
from vpo.policy.types import FileTimestampConfig, PhaseDefinition
from vpo.workflow.phases.executor.timestamp_ops import (
    _apply_fallback,
    _get_release_date,
    _handle_preserve_mode,
    _parse_date_to_timestamp,
    execute_file_timestamp,
)
from vpo.workflow.phases.executor.types import PhaseExecutionState


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create a temporary test file."""
    test_file = tmp_path / "test.mkv"
    test_file.write_text("fake video content")
    return test_file


@pytest.fixture
def mock_phase() -> PhaseDefinition:
    """Create a mock phase with file_timestamp config."""
    return PhaseDefinition(
        name="test",
        file_timestamp=FileTimestampConfig(
            mode="preserve",
            fallback="preserve",
            date_source="auto",
        ),
    )


@pytest.fixture
def mock_state(temp_file: Path, mock_phase: PhaseDefinition) -> PhaseExecutionState:
    """Create a mock execution state."""
    state = PhaseExecutionState(file_path=temp_file, phase=mock_phase)
    state.original_mtime = 1577836800.0  # 2020-01-01 00:00:00 UTC
    return state


class TestParseDateToTimestamp:
    """Tests for _parse_date_to_timestamp function."""

    def test_parses_valid_date(self) -> None:
        """Should parse YYYY-MM-DD format to UTC timestamp."""
        result = _parse_date_to_timestamp("2024-06-15")

        # 2024-06-15 00:00:00 UTC
        expected = 1718409600.0
        assert abs(result - expected) < 1.0

    def test_parses_date_at_midnight_utc(self) -> None:
        """Should set time to midnight UTC."""
        result = _parse_date_to_timestamp("2020-01-01")

        # 2020-01-01 00:00:00 UTC
        expected = 1577836800.0
        assert abs(result - expected) < 1.0

    def test_raises_on_invalid_format(self) -> None:
        """Should raise ValueError for invalid date format."""
        with pytest.raises(ValueError):
            _parse_date_to_timestamp("06-15-2024")  # Wrong format

        with pytest.raises(ValueError):
            _parse_date_to_timestamp("2024/06/15")  # Wrong separator

        with pytest.raises(ValueError):
            _parse_date_to_timestamp("invalid")


class TestGetReleaseDate:
    """Tests for _get_release_date function."""

    def test_returns_release_date_when_present(self) -> None:
        """Should return release_date field if present."""
        metadata = {"release_date": "2024-06-15"}

        result = _get_release_date(metadata, "auto")

        assert result == "2024-06-15"

    def test_radarr_source_prefers_digital(self) -> None:
        """Should prefer digital release for Radarr."""
        metadata = {
            "external_source": "radarr",
            "digital_release": "2024-03-01",
            "physical_release": "2024-04-01",
            "cinema_release": "2024-01-01",
        }

        result = _get_release_date(metadata, "radarr")

        assert result == "2024-03-01"

    def test_radarr_fallback_to_physical(self) -> None:
        """Should fall back to physical release if no digital."""
        metadata = {
            "external_source": "radarr",
            "physical_release": "2024-04-01",
            "cinema_release": "2024-01-01",
        }

        result = _get_release_date(metadata, "radarr")

        assert result == "2024-04-01"

    def test_radarr_fallback_to_cinema(self) -> None:
        """Should fall back to cinema release if no digital/physical."""
        metadata = {
            "external_source": "radarr",
            "cinema_release": "2024-01-01",
        }

        result = _get_release_date(metadata, "radarr")

        assert result == "2024-01-01"

    def test_sonarr_source_prefers_air_date(self) -> None:
        """Should prefer episode air_date for Sonarr."""
        metadata = {
            "external_source": "sonarr",
            "air_date": "2024-02-15",
            "premiere_date": "2024-01-01",
        }

        result = _get_release_date(metadata, "sonarr")

        assert result == "2024-02-15"

    def test_sonarr_fallback_to_premiere(self) -> None:
        """Should fall back to premiere if no air_date."""
        metadata = {
            "external_source": "sonarr",
            "premiere_date": "2024-01-01",
        }

        result = _get_release_date(metadata, "sonarr")

        assert result == "2024-01-01"

    def test_auto_detects_radarr_source(self) -> None:
        """Should auto-detect Radarr from external_source."""
        metadata = {
            "external_source": "radarr",
            "digital_release": "2024-03-01",
        }

        result = _get_release_date(metadata, "auto")

        assert result == "2024-03-01"

    def test_auto_detects_sonarr_source(self) -> None:
        """Should auto-detect Sonarr from external_source."""
        metadata = {
            "external_source": "sonarr",
            "air_date": "2024-02-15",
        }

        result = _get_release_date(metadata, "auto")

        assert result == "2024-02-15"

    def test_returns_none_if_no_dates(self) -> None:
        """Should return None if no dates available."""
        metadata = {"external_source": "radarr"}

        result = _get_release_date(metadata, "auto")

        assert result is None


class TestHandlePreserveMode:
    """Tests for _handle_preserve_mode function."""

    def test_restores_original_mtime(self, temp_file: Path) -> None:
        """Should restore original mtime when available."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        original_mtime = 1577836800.0  # 2020-01-01
        state.original_mtime = original_mtime

        result = _handle_preserve_mode(state, dry_run=False)

        assert result == 1
        current_mtime = get_file_mtime(temp_file)
        assert abs(current_mtime - original_mtime) < 1.0

    def test_returns_zero_if_no_original_mtime(self, temp_file: Path) -> None:
        """Should return 0 if original_mtime is None."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        state.original_mtime = None

        result = _handle_preserve_mode(state, dry_run=False)

        assert result == 0

    def test_dry_run_does_not_modify(self, temp_file: Path) -> None:
        """Dry run should not modify file mtime."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        state.original_mtime = 1577836800.0

        # Get current mtime
        before_mtime = get_file_mtime(temp_file)

        result = _handle_preserve_mode(state, dry_run=True)

        assert result == 1
        after_mtime = get_file_mtime(temp_file)
        assert abs(after_mtime - before_mtime) < 1.0


class TestApplyFallback:
    """Tests for _apply_fallback function."""

    def test_skip_fallback(self, temp_file: Path) -> None:
        """Skip fallback should return 0."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)

        result = _apply_fallback(state, "skip", dry_run=False)

        assert result == 0

    def test_now_fallback(self, temp_file: Path) -> None:
        """Now fallback should return 0 (no-op)."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)

        result = _apply_fallback(state, "now", dry_run=False)

        assert result == 0

    def test_preserve_fallback(self, temp_file: Path) -> None:
        """Preserve fallback should restore original mtime."""
        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        state.original_mtime = 1577836800.0

        result = _apply_fallback(state, "preserve", dry_run=False)

        assert result == 1


class TestExecuteFileTimestamp:
    """Tests for execute_file_timestamp function."""

    def test_now_mode_is_noop(self, temp_file: Path) -> None:
        """Now mode should return 0 without changes."""
        phase = PhaseDefinition(
            name="test",
            file_timestamp=FileTimestampConfig(mode="now"),
        )
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        mock_conn = MagicMock()

        result = execute_file_timestamp(state, None, mock_conn, dry_run=False)

        assert result == 0

    def test_preserve_mode_restores_mtime(self, temp_file: Path) -> None:
        """Preserve mode should restore original mtime."""
        phase = PhaseDefinition(
            name="test",
            file_timestamp=FileTimestampConfig(mode="preserve"),
        )
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        state.original_mtime = 1577836800.0
        mock_conn = MagicMock()

        result = execute_file_timestamp(state, None, mock_conn, dry_run=False)

        assert result == 1
        current_mtime = get_file_mtime(temp_file)
        assert abs(current_mtime - 1577836800.0) < 1.0

    def test_no_config_returns_zero(self, temp_file: Path) -> None:
        """Should return 0 if no file_timestamp config."""
        phase = PhaseDefinition(name="test")  # No file_timestamp
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        mock_conn = MagicMock()

        result = execute_file_timestamp(state, None, mock_conn, dry_run=False)

        assert result == 0

    @patch("vpo.workflow.phases.executor.timestamp_ops.get_file_by_path")
    @patch("vpo.workflow.phases.executor.timestamp_ops.parse_plugin_metadata")
    def test_release_date_mode_sets_mtime(
        self,
        mock_parse_metadata: MagicMock,
        mock_get_file: MagicMock,
        temp_file: Path,
    ) -> None:
        """Release date mode should set mtime from metadata."""
        phase = PhaseDefinition(
            name="test",
            file_timestamp=FileTimestampConfig(
                mode="release_date",
                date_source="auto",
            ),
        )
        state = PhaseExecutionState(file_path=temp_file, phase=phase)
        state.original_mtime = time.time()

        # Mock database and metadata
        mock_record = MagicMock()
        mock_record.id = "test-id"
        mock_get_file.return_value = mock_record
        mock_parse_metadata.return_value = {
            "release_date": "2024-06-15",
        }
        mock_conn = MagicMock()

        result = execute_file_timestamp(state, None, mock_conn, dry_run=False)

        assert result == 1
        # 2024-06-15 00:00:00 UTC
        expected_mtime = 1718409600.0
        current_mtime = get_file_mtime(temp_file)
        assert abs(current_mtime - expected_mtime) < 1.0
