"""Tests for the auto-prune background task and configuration."""

import asyncio

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

    def test_is_healthy_default(self):
        task = AutoPruneTask(interval_seconds=3600)
        assert task.is_healthy is True

    def test_accepts_connection_pool_and_lifecycle(self):
        task = AutoPruneTask(
            interval_seconds=3600,
            connection_pool="mock_pool",
            lifecycle="mock_lifecycle",
        )
        assert task._pool == "mock_pool"
        assert task._lifecycle == "mock_lifecycle"


@pytest.mark.asyncio
class TestAutoPruneTaskAsync:
    """Async tests for AutoPruneTask.run() and _run_prune()."""

    async def test_run_executes_prune_and_stops(self):
        """run() calls _run_prune and exits cleanly on stop()."""
        task = AutoPruneTask(
            interval_seconds=1,
            startup_delay_seconds=0,
        )

        prune_called = asyncio.Event()

        async def mock_run_prune():
            prune_called.set()
            task.stop()

        task._run_prune = mock_run_prune

        await asyncio.wait_for(task.run(), timeout=5)
        assert prune_called.is_set()

    async def test_run_already_running_returns_early(self):
        """If _running is True, run() returns immediately."""
        task = AutoPruneTask(
            interval_seconds=1,
            startup_delay_seconds=0,
        )
        # Simulate already running
        task._running = True

        # Should return quickly without error
        await asyncio.wait_for(task.run(), timeout=2)
        # _running should still be True (not reset by the early return)
        assert task._running is True

    async def test_stop_during_startup_delay(self):
        """Calling stop() during startup delay exits early."""
        task = AutoPruneTask(
            interval_seconds=3600,
            startup_delay_seconds=60,  # Long delay
        )

        async def stop_soon():
            await asyncio.sleep(0.1)
            task.stop()

        asyncio.create_task(stop_soon())
        await asyncio.wait_for(task.run(), timeout=5)
        assert task.is_running is False

    async def test_run_prune_success_updates_last_run(self):
        """Successful prune updates _last_run timestamp."""
        from unittest.mock import MagicMock

        from vpo.jobs.services.prune import PruneJobResult

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.get_connection.return_value = mock_conn

        task = AutoPruneTask(
            interval_seconds=3600,
            connection_pool=mock_pool,
        )

        # Mock the prune internals to avoid real DB calls
        import vpo.server.auto_prune as auto_prune_mod

        original_create = auto_prune_mod.create_prune_job
        original_complete = auto_prune_mod.complete_prune_job

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        auto_prune_mod.create_prune_job = MagicMock(return_value=mock_job)
        auto_prune_mod.complete_prune_job = MagicMock()

        original_service_cls = auto_prune_mod.PruneJobService

        class MockService:
            def __init__(self, conn):
                pass

            def process(self):
                return PruneJobResult(success=True, files_pruned=0)

        auto_prune_mod.PruneJobService = MockService

        try:
            assert task.last_run is None
            await task._run_prune()
            assert task.last_run is not None
        finally:
            auto_prune_mod.create_prune_job = original_create
            auto_prune_mod.complete_prune_job = original_complete
            auto_prune_mod.PruneJobService = original_service_cls

    async def test_run_prune_no_pool_warns(self):
        """When pool is None, _run_prune logs warning and returns."""
        task = AutoPruneTask(
            interval_seconds=3600,
            connection_pool=None,
        )

        # Should not raise
        await task._run_prune()
        # last_run should NOT be set (prune did not run)
        assert task.last_run is None

    async def test_run_prune_exception_tracks_failures(self):
        """Exceptions increment consecutive failures and mark unhealthy."""
        from unittest.mock import MagicMock

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = RuntimeError("pool error")

        task = AutoPruneTask(
            interval_seconds=3600,
            connection_pool=mock_pool,
        )

        assert task.is_healthy is True
        assert task._consecutive_failures == 0

        # Run prune 3 times to trigger unhealthy threshold
        await task._run_prune()
        assert task._consecutive_failures == 1
        assert task.is_healthy is True

        await task._run_prune()
        assert task._consecutive_failures == 2
        assert task.is_healthy is True

        await task._run_prune()
        assert task._consecutive_failures == 3
        assert task.is_healthy is False
