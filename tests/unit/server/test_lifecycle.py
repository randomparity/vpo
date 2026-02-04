"""Unit tests for server lifecycle management."""

from datetime import datetime, timedelta, timezone

from vpo.server.lifecycle import DaemonLifecycle, ShutdownState


class TestShutdownState:
    """Tests for ShutdownState dataclass."""

    def test_default_state_not_shutting_down(self) -> None:
        """Default state should not be shutting down."""
        state = ShutdownState()
        assert state.initiated is None
        assert state.timeout_deadline is None
        assert state.tasks_remaining == 0
        assert not state.is_shutting_down
        assert not state.is_timed_out

    def test_is_shutting_down_when_initiated_set(self) -> None:
        """is_shutting_down should be True when initiated is set."""
        state = ShutdownState(initiated=datetime.now(timezone.utc))
        assert state.is_shutting_down

    def test_is_timed_out_before_deadline(self) -> None:
        """is_timed_out should be False before deadline."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        state = ShutdownState(timeout_deadline=future)
        assert not state.is_timed_out

    def test_is_timed_out_after_deadline(self) -> None:
        """is_timed_out should be True after deadline."""
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        state = ShutdownState(timeout_deadline=past)
        assert state.is_timed_out

    def test_is_timed_out_no_deadline(self) -> None:
        """is_timed_out should be False when no deadline set."""
        state = ShutdownState()
        assert not state.is_timed_out


class TestDaemonLifecycle:
    """Tests for DaemonLifecycle class."""

    def test_default_state(self) -> None:
        """Default state should have sensible defaults."""
        lifecycle = DaemonLifecycle()
        assert lifecycle.shutdown_timeout == 30.0
        assert not lifecycle.is_shutting_down
        assert lifecycle.uptime_seconds >= 0

    def test_custom_timeout(self) -> None:
        """Custom shutdown timeout should be honored."""
        lifecycle = DaemonLifecycle(shutdown_timeout=60.0)
        assert lifecycle.shutdown_timeout == 60.0

    def test_uptime_increases(self) -> None:
        """Uptime should be positive and reasonable."""
        lifecycle = DaemonLifecycle()
        uptime1 = lifecycle.uptime_seconds
        assert uptime1 >= 0
        # Uptime should not be negative
        assert uptime1 < 1.0  # Should be near zero for fresh lifecycle

    def test_initiate_shutdown_sets_state(self) -> None:
        """initiate_shutdown should set shutdown state."""
        lifecycle = DaemonLifecycle(shutdown_timeout=30.0)
        assert not lifecycle.is_shutting_down

        lifecycle.initiate_shutdown()

        assert lifecycle.is_shutting_down
        assert lifecycle.shutdown_state.initiated is not None
        assert lifecycle.shutdown_state.timeout_deadline is not None

    def test_initiate_shutdown_idempotent(self) -> None:
        """Calling initiate_shutdown multiple times should be safe."""
        lifecycle = DaemonLifecycle()
        lifecycle.initiate_shutdown()
        first_initiated = lifecycle.shutdown_state.initiated

        lifecycle.initiate_shutdown()  # Second call
        assert lifecycle.shutdown_state.initiated == first_initiated

    def test_shutdown_deadline_respects_timeout(self) -> None:
        """Shutdown deadline should be start_time + timeout."""
        lifecycle = DaemonLifecycle(shutdown_timeout=45.0)
        lifecycle.initiate_shutdown()

        expected_deadline = lifecycle.shutdown_state.initiated + timedelta(seconds=45.0)
        assert lifecycle.shutdown_state.timeout_deadline == expected_deadline

    def test_set_rate_limiter_before_init_is_noop(self) -> None:
        """set_rate_limiter without init_reload_support should not error."""
        from vpo.config.models import RateLimitConfig
        from vpo.server.rate_limit import RateLimiter

        lifecycle = DaemonLifecycle()
        rate_limiter = RateLimiter(RateLimitConfig())
        # Should silently return — no error, no crash
        lifecycle.set_rate_limiter(rate_limiter)

    def test_set_rate_limiter_after_init_delegates(self) -> None:
        """set_rate_limiter after init_reload_support should wire through."""
        from vpo.config.models import RateLimitConfig, VPOConfig
        from vpo.server.rate_limit import RateLimiter

        lifecycle = DaemonLifecycle()
        config = VPOConfig()
        lifecycle.init_reload_support(config)

        rate_limiter = RateLimiter(RateLimitConfig())
        lifecycle.set_rate_limiter(rate_limiter)

        assert lifecycle._config_reloader._rate_limiter is rate_limiter
