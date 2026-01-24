"""Tests for config models module."""

import pytest

from vpo.config.models import JobsConfig, ProcessingConfig


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


class TestJobsConfig:
    """Tests for JobsConfig dataclass."""

    def test_default_min_free_disk_percent(self) -> None:
        """Default min_free_disk_percent should be 5.0."""
        config = JobsConfig()
        assert config.min_free_disk_percent == 5.0

    def test_min_free_disk_percent_can_be_set(self) -> None:
        """min_free_disk_percent can be set via constructor."""
        config = JobsConfig(min_free_disk_percent=10.0)
        assert config.min_free_disk_percent == 10.0

    def test_min_free_disk_percent_zero_disables_check(self) -> None:
        """Setting min_free_disk_percent to 0 disables the check."""
        config = JobsConfig(min_free_disk_percent=0.0)
        assert config.min_free_disk_percent == 0.0

    def test_min_free_disk_percent_max_value(self) -> None:
        """min_free_disk_percent can be set to 100."""
        config = JobsConfig(min_free_disk_percent=100.0)
        assert config.min_free_disk_percent == 100.0

    def test_min_free_disk_percent_negative_raises(self) -> None:
        """Negative values should raise ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            JobsConfig(min_free_disk_percent=-1.0)

    def test_min_free_disk_percent_over_100_raises(self) -> None:
        """Values over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="must be between 0 and 100"):
            JobsConfig(min_free_disk_percent=101.0)
