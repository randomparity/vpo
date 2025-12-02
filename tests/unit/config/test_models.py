"""Tests for config models module."""

import pytest

from video_policy_orchestrator.config.models import ProcessingConfig


class TestProcessingConfig:
    """Tests for ProcessingConfig dataclass."""

    def test_default_values(self) -> None:
        """Default values should be applied."""
        config = ProcessingConfig()
        assert config.workers == 2

    def test_workers_can_be_set(self) -> None:
        """Workers can be set via constructor."""
        config = ProcessingConfig(workers=4)
        assert config.workers == 4

    def test_workers_minimum_is_one(self) -> None:
        """Workers must be at least 1."""
        with pytest.raises(ValueError, match="workers must be at least 1"):
            ProcessingConfig(workers=0)

    def test_workers_negative_raises(self) -> None:
        """Negative worker count should raise."""
        with pytest.raises(ValueError, match="workers must be at least 1"):
            ProcessingConfig(workers=-1)

    def test_workers_one_is_valid(self) -> None:
        """Workers = 1 (sequential) is valid."""
        config = ProcessingConfig(workers=1)
        assert config.workers == 1

    def test_workers_large_value_allowed(self) -> None:
        """Large worker values are allowed at config level (capped at runtime)."""
        config = ProcessingConfig(workers=100)
        assert config.workers == 100
