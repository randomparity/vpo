"""Tests for the auto-prune background task and configuration."""

import pytest

from vpo.config.models import JobsConfig
from vpo.server.auto_prune import AutoPruneTask


class TestJobsConfigAutoPrune:
    """Tests for auto-prune configuration fields."""

    def test_default_values(self):
        config = JobsConfig()
        assert config.auto_prune_enabled is False
        assert config.auto_prune_interval_hours == 168

    def test_enabled_config(self):
        config = JobsConfig(auto_prune_enabled=True)
        assert config.auto_prune_enabled is True

    def test_custom_interval(self):
        config = JobsConfig(auto_prune_interval_hours=48)
        assert config.auto_prune_interval_hours == 48

    def test_rejects_interval_less_than_1(self):
        with pytest.raises(ValueError, match="auto_prune_interval_hours"):
            JobsConfig(auto_prune_interval_hours=0)

    def test_rejects_negative_interval(self):
        with pytest.raises(ValueError, match="auto_prune_interval_hours"):
            JobsConfig(auto_prune_interval_hours=-1)

    def test_interval_of_1_is_valid(self):
        config = JobsConfig(auto_prune_interval_hours=1)
        assert config.auto_prune_interval_hours == 1


class TestAutoPruneTask:
    """Tests for AutoPruneTask initialization and properties."""

    def test_default_initialization(self):
        task = AutoPruneTask(interval_seconds=3600)
        assert task.interval_seconds == 3600
        assert task.startup_delay_seconds == 600
        assert task.is_running is False
        assert task.last_run is None

    def test_custom_startup_delay(self):
        task = AutoPruneTask(
            interval_seconds=3600,
            startup_delay_seconds=60,
        )
        assert task.startup_delay_seconds == 60

    def test_stop_sets_event(self):
        task = AutoPruneTask(interval_seconds=3600)
        assert not task._stop_event.is_set()
        task.stop()
        assert task._stop_event.is_set()
