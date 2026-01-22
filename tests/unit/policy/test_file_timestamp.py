"""Tests for file_timestamp policy configuration and parsing."""

from __future__ import annotations

import pytest

from vpo.policy.loader import load_policy_from_dict
from vpo.policy.types import FileTimestampConfig, OperationType


class TestFileTimestampConfig:
    """Tests for FileTimestampConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        config = FileTimestampConfig()

        assert config.mode == "preserve"
        assert config.fallback == "preserve"
        assert config.date_source == "auto"

    def test_all_modes_valid(self) -> None:
        """Should accept all valid modes."""
        for mode in ("preserve", "release_date", "now"):
            config = FileTimestampConfig(mode=mode)
            assert config.mode == mode

    def test_all_fallbacks_valid(self) -> None:
        """Should accept all valid fallback values."""
        for fallback in ("preserve", "now", "skip"):
            config = FileTimestampConfig(fallback=fallback)
            assert config.fallback == fallback

    def test_all_date_sources_valid(self) -> None:
        """Should accept all valid date_source values."""
        for source in ("auto", "radarr", "sonarr"):
            config = FileTimestampConfig(date_source=source)
            assert config.date_source == source


class TestFileTimestampPolicyParsing:
    """Tests for parsing file_timestamp from YAML policies."""

    def test_minimal_config(self) -> None:
        """Should parse minimal file_timestamp config."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {},  # Use defaults
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.file_timestamp is not None
        assert phase.file_timestamp.mode == "preserve"
        assert phase.file_timestamp.fallback == "preserve"
        assert phase.file_timestamp.date_source == "auto"

    def test_preserve_mode(self) -> None:
        """Should parse preserve mode correctly."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "mode": "preserve",
                    },
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.file_timestamp.mode == "preserve"

    def test_release_date_mode_with_fallback(self) -> None:
        """Should parse release_date mode with custom fallback."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "mode": "release_date",
                        "fallback": "now",
                        "date_source": "radarr",
                    },
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.file_timestamp.mode == "release_date"
        assert phase.file_timestamp.fallback == "now"
        assert phase.file_timestamp.date_source == "radarr"

    def test_now_mode(self) -> None:
        """Should parse now mode correctly."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "mode": "now",
                    },
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.file_timestamp.mode == "now"

    def test_invalid_mode_rejected(self) -> None:
        """Should reject invalid mode values."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "mode": "invalid_mode",
                    },
                }
            ],
        }

        with pytest.raises(Exception):  # PolicyValidationError or similar
            load_policy_from_dict(policy_dict)

    def test_invalid_fallback_rejected(self) -> None:
        """Should reject invalid fallback values."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "fallback": "invalid_fallback",
                    },
                }
            ],
        }

        with pytest.raises(Exception):
            load_policy_from_dict(policy_dict)

    def test_invalid_date_source_rejected(self) -> None:
        """Should reject invalid date_source values."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "date_source": "invalid_source",
                    },
                }
            ],
        }

        with pytest.raises(Exception):
            load_policy_from_dict(policy_dict)


class TestFileTimestampOperationType:
    """Tests for FILE_TIMESTAMP operation type."""

    def test_operation_type_exists(self) -> None:
        """FILE_TIMESTAMP should exist in OperationType enum."""
        assert hasattr(OperationType, "FILE_TIMESTAMP")
        assert OperationType.FILE_TIMESTAMP.value == "file_timestamp"

    def test_phase_reports_file_timestamp_operation(self) -> None:
        """Phase with file_timestamp should report FILE_TIMESTAMP operation."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "file_timestamp": {
                        "mode": "preserve",
                    },
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        operations = phase.get_operations()
        assert OperationType.FILE_TIMESTAMP in operations

    def test_phase_without_file_timestamp_no_operation(self) -> None:
        """Phase without file_timestamp should not report FILE_TIMESTAMP."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "test",
                    "container": {"target": "mkv"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        operations = phase.get_operations()
        assert OperationType.FILE_TIMESTAMP not in operations


class TestFileTimestampWithOtherOperations:
    """Tests for file_timestamp combined with other operations."""

    def test_with_container_conversion(self) -> None:
        """Should work alongside container conversion."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "remux",
                    "container": {"target": "mkv"},
                    "file_timestamp": {"mode": "preserve"},
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.container is not None
        assert phase.file_timestamp is not None
        operations = phase.get_operations()
        assert OperationType.CONTAINER in operations
        assert OperationType.FILE_TIMESTAMP in operations

    def test_with_transcode(self) -> None:
        """Should work alongside transcode operations."""
        policy_dict = {
            "schema_version": 12,
            "phases": [
                {
                    "name": "transcode",
                    "transcode": {
                        "video": {
                            "target_codec": "hevc",
                        }
                    },
                    "file_timestamp": {
                        "mode": "release_date",
                        "fallback": "preserve",
                    },
                }
            ],
        }

        policy = load_policy_from_dict(policy_dict)

        phase = policy.phases[0]
        assert phase.transcode is not None
        assert phase.file_timestamp is not None
