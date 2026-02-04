"""Tests for config models module."""

import pytest

from vpo.config.models import JobsConfig, ProcessingConfig, RateLimitConfig


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

    def test_min_free_disk_percent_decimal_precision(self) -> None:
        """Should preserve decimal precision."""
        config = JobsConfig(min_free_disk_percent=5.123456)
        assert config.min_free_disk_percent == pytest.approx(5.123456)

    def test_min_free_disk_percent_scientific_notation(self) -> None:
        """Should accept values from scientific notation (already parsed by Python)."""
        # When Python parses TOML, scientific notation is converted to float
        config = JobsConfig(min_free_disk_percent=5e0)  # 5.0
        assert config.min_free_disk_percent == 5.0

    def test_min_free_disk_percent_very_small_value(self) -> None:
        """Should accept very small positive values."""
        config = JobsConfig(min_free_disk_percent=0.001)
        assert config.min_free_disk_percent == pytest.approx(0.001)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self) -> None:
        """Default values should be applied."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.get_max_requests == 120
        assert config.mutate_max_requests == 30
        assert config.window_seconds == 60

    def test_custom_values(self) -> None:
        """Custom values should be accepted."""
        config = RateLimitConfig(
            enabled=False,
            get_max_requests=200,
            mutate_max_requests=50,
            window_seconds=120,
        )
        assert config.enabled is False
        assert config.get_max_requests == 200
        assert config.mutate_max_requests == 50
        assert config.window_seconds == 120

    def test_frozen(self) -> None:
        """RateLimitConfig should be frozen (immutable)."""
        config = RateLimitConfig()
        with pytest.raises(AttributeError):
            config.enabled = False  # type: ignore[misc]

    def test_get_max_requests_zero_raises(self) -> None:
        """get_max_requests < 1 should raise."""
        with pytest.raises(ValueError, match="get_max_requests must be at least 1"):
            RateLimitConfig(get_max_requests=0)

    def test_get_max_requests_negative_raises(self) -> None:
        """Negative get_max_requests should raise."""
        with pytest.raises(ValueError, match="get_max_requests must be at least 1"):
            RateLimitConfig(get_max_requests=-1)

    def test_mutate_max_requests_zero_raises(self) -> None:
        """mutate_max_requests < 1 should raise."""
        with pytest.raises(ValueError, match="mutate_max_requests must be at least 1"):
            RateLimitConfig(mutate_max_requests=0)

    def test_window_seconds_zero_raises(self) -> None:
        """window_seconds < 1 should raise."""
        with pytest.raises(ValueError, match="window_seconds must be at least 1"):
            RateLimitConfig(window_seconds=0)

    def test_boundary_values(self) -> None:
        """Minimum valid values (1) should be accepted."""
        config = RateLimitConfig(
            get_max_requests=1,
            mutate_max_requests=1,
            window_seconds=1,
        )
        assert config.get_max_requests == 1
        assert config.mutate_max_requests == 1
        assert config.window_seconds == 1
