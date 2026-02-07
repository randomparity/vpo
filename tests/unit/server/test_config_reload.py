"""Unit tests for configuration reload support."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.config.models import (
    JobsConfig,
    LoggingConfig,
    ProcessingConfig,
    RateLimitConfig,
    ServerConfig,
    ToolPathsConfig,
    VPOConfig,
    WorkerConfig,
)
from vpo.server.config_reload import (
    REQUIRES_RESTART_FIELDS,
    ConfigReloader,
    ReloadResult,
    ReloadState,
    _detect_changes,
    _format_change_log,
    _get_nested_attr,
)


class TestReloadState:
    """Tests for ReloadState dataclass."""

    def test_default_initialization(self) -> None:
        """Test ReloadState initializes with default values."""
        state = ReloadState()
        assert state.last_reload is None
        assert state.reload_count == 0
        assert state.last_error is None
        assert state.changes_detected == []

    def test_initialization_with_values(self) -> None:
        """Test ReloadState can be initialized with custom values."""
        now = datetime.now(timezone.utc)
        state = ReloadState(
            last_reload=now,
            reload_count=5,
            last_error="test error",
            changes_detected=["jobs.retention_days"],
        )
        assert state.last_reload == now
        assert state.reload_count == 5
        assert state.last_error == "test error"
        assert state.changes_detected == ["jobs.retention_days"]


class TestReloadResult:
    """Tests for ReloadResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful reload result."""
        result = ReloadResult(
            success=True,
            changes=["jobs.retention_days", "logging.level"],
        )
        assert result.success is True
        assert len(result.changes) == 2
        assert result.error is None
        assert result.requires_restart == []

    def test_failure_result(self) -> None:
        """Test failed reload result."""
        result = ReloadResult(
            success=False,
            changes=[],
            error="Config file not found",
        )
        assert result.success is False
        assert result.changes == []
        assert result.error == "Config file not found"

    def test_result_with_restart_required(self) -> None:
        """Test result with changes requiring restart."""
        result = ReloadResult(
            success=True,
            changes=["server.port", "jobs.retention_days"],
            requires_restart=["server.port"],
        )
        assert result.success is True
        assert "server.port" in result.requires_restart
        assert "jobs.retention_days" not in result.requires_restart


class TestGetNestedAttr:
    """Tests for _get_nested_attr helper."""

    def test_single_level_attr(self) -> None:
        """Test getting a single-level attribute."""
        config = VPOConfig()
        result = _get_nested_attr(config, "database_path")
        assert result == config.database_path

    def test_nested_attr(self) -> None:
        """Test getting a nested attribute."""
        config = VPOConfig(server=ServerConfig(port=9000))
        result = _get_nested_attr(config, "server.port")
        assert result == 9000

    def test_missing_attr(self) -> None:
        """Test getting a nonexistent attribute returns None."""
        config = VPOConfig()
        result = _get_nested_attr(config, "nonexistent.field")
        assert result is None


class TestDetectChanges:
    """Tests for _detect_changes function."""

    def test_no_changes(self) -> None:
        """Test detection when configs are identical."""
        config1 = VPOConfig()
        config2 = VPOConfig()
        changes, requires_restart = _detect_changes(config1, config2)
        assert changes == []
        assert requires_restart == []

    def test_hot_reloadable_change(self) -> None:
        """Test detection of hot-reloadable changes."""
        config1 = VPOConfig(jobs=JobsConfig(retention_days=30))
        config2 = VPOConfig(jobs=JobsConfig(retention_days=60))
        changes, requires_restart = _detect_changes(config1, config2)
        assert "jobs.retention_days" in changes
        assert requires_restart == []

    def test_requires_restart_change(self) -> None:
        """Test detection of changes requiring restart."""
        config1 = VPOConfig(server=ServerConfig(port=8321))
        config2 = VPOConfig(server=ServerConfig(port=9000))
        changes, requires_restart = _detect_changes(config1, config2)
        assert "server.port" in changes
        assert "server.port" in requires_restart

    def test_multiple_changes(self) -> None:
        """Test detection of multiple changes."""
        config1 = VPOConfig(
            jobs=JobsConfig(retention_days=30),
            logging=LoggingConfig(level="info"),
            processing=ProcessingConfig(workers=2),
        )
        config2 = VPOConfig(
            jobs=JobsConfig(retention_days=60),
            logging=LoggingConfig(level="debug"),
            processing=ProcessingConfig(workers=4),
        )
        changes, _ = _detect_changes(config1, config2)
        assert "jobs.retention_days" in changes
        assert "logging.level" in changes
        assert "processing.workers" in changes

    def test_path_comparison(self) -> None:
        """Test that Path fields are compared correctly."""
        config1 = VPOConfig(tools=ToolPathsConfig(ffmpeg=Path("/usr/bin/ffmpeg")))
        config2 = VPOConfig(tools=ToolPathsConfig(ffmpeg=Path("/usr/local/bin/ffmpeg")))
        changes, requires_restart = _detect_changes(config1, config2)
        assert "tools.ffmpeg" in changes
        assert "tools.ffmpeg" in requires_restart


class TestFormatChangeLog:
    """Tests for _format_change_log function."""

    def test_format_simple_change(self) -> None:
        """Test formatting a simple value change."""
        config1 = VPOConfig(jobs=JobsConfig(retention_days=30))
        config2 = VPOConfig(jobs=JobsConfig(retention_days=60))
        msg = _format_change_log("jobs.retention_days", config1, config2)
        assert "jobs.retention_days" in msg
        assert "30" in msg
        assert "60" in msg

    def test_format_auth_token_sanitized(self) -> None:
        """Test that auth_token values are sanitized."""
        config1 = VPOConfig(server=ServerConfig(auth_token="secret-token-16ch"))
        config2 = VPOConfig(server=ServerConfig(auth_token="new-secret-token1"))
        msg = _format_change_log("server.auth_token", config1, config2)
        assert "server.auth_token" in msg
        assert "secret-token-16ch" not in msg
        assert "new-secret-token1" not in msg
        assert "****" in msg


class TestRequiresRestartFields:
    """Tests for REQUIRES_RESTART_FIELDS constant."""

    def test_server_fields_require_restart(self) -> None:
        """Test that server binding fields require restart."""
        assert "server.bind" in REQUIRES_RESTART_FIELDS
        assert "server.port" in REQUIRES_RESTART_FIELDS
        assert "server.auth_token" in REQUIRES_RESTART_FIELDS

    def test_database_path_requires_restart(self) -> None:
        """Test that database_path requires restart."""
        assert "database_path" in REQUIRES_RESTART_FIELDS

    def test_tool_paths_require_restart(self) -> None:
        """Test that tool paths require restart."""
        assert "tools.ffmpeg" in REQUIRES_RESTART_FIELDS
        assert "tools.ffprobe" in REQUIRES_RESTART_FIELDS
        assert "tools.mkvmerge" in REQUIRES_RESTART_FIELDS
        assert "tools.mkvpropedit" in REQUIRES_RESTART_FIELDS

    def test_rate_limit_fields_not_in_requires_restart(self) -> None:
        """Test that rate limit fields are hot-reloadable."""
        assert "server.rate_limit.enabled" not in REQUIRES_RESTART_FIELDS
        assert "server.rate_limit.get_max_requests" not in REQUIRES_RESTART_FIELDS
        assert "server.rate_limit.mutate_max_requests" not in REQUIRES_RESTART_FIELDS
        assert "server.rate_limit.window_seconds" not in REQUIRES_RESTART_FIELDS

    def test_jobs_config_not_in_requires_restart(self) -> None:
        """Test that jobs config fields are hot-reloadable."""
        assert "jobs.retention_days" not in REQUIRES_RESTART_FIELDS
        assert "jobs.auto_purge" not in REQUIRES_RESTART_FIELDS


class TestConfigReloader:
    """Tests for ConfigReloader class."""

    def test_initialization(self) -> None:
        """Test ConfigReloader initialization."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        assert reloader._state is state
        assert reloader._config_path is None
        assert reloader._current_config is None

    def test_initialization_with_config_path(self) -> None:
        """Test ConfigReloader initialization with config path."""
        state = ReloadState()
        config_path = Path("/etc/vpo/config.toml")
        reloader = ConfigReloader(state, config_path=config_path)
        assert reloader._config_path == config_path

    def test_set_current_config(self) -> None:
        """Test setting current configuration snapshot."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        config = VPOConfig()
        reloader.set_current_config(config)
        assert reloader._current_config is config

    @pytest.mark.asyncio
    async def test_reload_without_current_config_fails(self) -> None:
        """Test reload fails gracefully when no current config set."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        # Don't call set_current_config
        result = await reloader.reload()
        assert result.success is False
        assert "No current configuration" in result.error
        assert state.last_error is not None

    @pytest.mark.asyncio
    async def test_reload_success_no_changes(self) -> None:
        """Test reload when config is unchanged."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        config = VPOConfig()
        reloader.set_current_config(config)

        # Mock get_config to return same config
        with patch("vpo.config.loader.get_config", return_value=VPOConfig()):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert result.changes == []

    @pytest.mark.asyncio
    async def test_reload_success_with_changes(self) -> None:
        """Test reload with configuration changes."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(jobs=JobsConfig(retention_days=30))
        new_config = VPOConfig(jobs=JobsConfig(retention_days=60))
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert "jobs.retention_days" in result.changes
        assert state.reload_count == 1
        assert state.last_reload is not None
        assert state.last_error is None

    @pytest.mark.asyncio
    async def test_reload_with_restart_required(self) -> None:
        """Test reload with changes that require restart."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(server=ServerConfig(port=8321))
        new_config = VPOConfig(server=ServerConfig(port=9000))
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert "server.port" in result.changes
        assert "server.port" in result.requires_restart

    @pytest.mark.asyncio
    async def test_reload_failure_preserves_old_config(self) -> None:
        """Test that reload failure keeps old config."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig()
        reloader.set_current_config(old_config)

        with patch(
            "vpo.config.loader.get_config",
            side_effect=ValueError("Invalid config"),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is False
        assert "Invalid config" in result.error
        assert state.last_error is not None
        # Original config should be preserved
        assert reloader._current_config is old_config

    @pytest.mark.asyncio
    async def test_reload_updates_log_level(self) -> None:
        """Test that logging.level change updates root logger."""
        import logging

        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(logging=LoggingConfig(level="info"))
        new_config = VPOConfig(logging=LoggingConfig(level="debug"))
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert "logging.level" in result.changes
        # Root logger should be updated
        assert logging.getLogger().level == logging.DEBUG

    @pytest.mark.asyncio
    async def test_reload_increments_count(self) -> None:
        """Test that reload count increments on each successful reload."""
        state = ReloadState()
        reloader = ConfigReloader(state)

        # First reload
        reloader.set_current_config(VPOConfig(jobs=JobsConfig(retention_days=30)))
        with patch(
            "vpo.config.loader.get_config",
            return_value=VPOConfig(jobs=JobsConfig(retention_days=31)),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                await reloader.reload()

        assert state.reload_count == 1

        # Second reload
        with patch(
            "vpo.config.loader.get_config",
            return_value=VPOConfig(jobs=JobsConfig(retention_days=32)),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                await reloader.reload()

        assert state.reload_count == 2

    @pytest.mark.asyncio
    async def test_reload_stores_changes_detected(self) -> None:
        """Test that changes are stored in state."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(
            jobs=JobsConfig(retention_days=30),
            worker=WorkerConfig(max_files=100),
        )
        new_config = VPOConfig(
            jobs=JobsConfig(retention_days=60),
            worker=WorkerConfig(max_files=200),
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                await reloader.reload()

        assert "jobs.retention_days" in state.changes_detected
        assert "worker.max_files" in state.changes_detected

    @pytest.mark.asyncio
    async def test_reload_handles_missing_config_file(self) -> None:
        """Test reload handles FileNotFoundError gracefully."""
        state = ReloadState()
        config_path = Path("/nonexistent/config.toml")
        reloader = ConfigReloader(state, config_path=config_path)
        old_config = VPOConfig()
        reloader.set_current_config(old_config)

        with patch(
            "vpo.config.loader.get_config",
            side_effect=FileNotFoundError("No such file"),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is False
        assert "not found" in result.error.lower()
        # Original config should be preserved
        assert reloader._current_config is old_config

    @pytest.mark.asyncio
    async def test_reload_handles_permission_error(self) -> None:
        """Test reload handles PermissionError gracefully."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig()
        reloader.set_current_config(old_config)

        with patch(
            "vpo.config.loader.get_config",
            side_effect=PermissionError("Permission denied"),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is False
        assert "permission denied" in result.error.lower()
        # Original config should be preserved
        assert reloader._current_config is old_config

    @pytest.mark.asyncio
    async def test_concurrent_reload_attempts(self) -> None:
        """Test that concurrent reload attempts are properly handled."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(jobs=JobsConfig(retention_days=30))
        new_config = VPOConfig(jobs=JobsConfig(retention_days=60))
        reloader.set_current_config(old_config)

        # Track how many reloads actually execute
        reload_executions = []
        lock_acquired = asyncio.Event()

        def slow_get_config(*args, **kwargs):
            reload_executions.append(1)
            return new_config

        # We'll use a custom side effect that blocks, allowing us to test
        # concurrent access to the lock
        async def first_reload():
            # Acquire lock first and hold it
            async with reloader._reload_lock:
                lock_acquired.set()
                await asyncio.sleep(0.1)  # Hold lock
                return ReloadResult(success=True, changes=["test"])

        async def second_reload():
            # Wait for first to acquire lock
            await lock_acquired.wait()
            # Now try to reload - should fail because lock is held
            return await reloader.reload()

        # Run both concurrently
        results = await asyncio.gather(first_reload(), second_reload())

        # Second should report "already in progress"
        assert results[1].success is False
        assert results[1].error == "Reload already in progress"

    @pytest.mark.asyncio
    async def test_invalid_log_level_validation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that invalid log level doesn't crash and logs warning."""
        import logging as stdlib_logging

        from vpo.server.config_reload import ConfigReloader

        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig(logging=LoggingConfig(level="info"))
        # Use a valid level that will pass config validation
        new_config = VPOConfig(logging=LoggingConfig(level="debug"))
        reloader.set_current_config(old_config)

        # Mock getLevelName to return a string (which indicates invalid level)
        # when called with "DEBUG" (uppercase)
        original_getLevelName = stdlib_logging.getLevelName

        def mock_getLevelName(level):
            if level == "DEBUG":
                return "Level DEBUG"  # String return = invalid
            return original_getLevelName(level)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                with patch.object(
                    stdlib_logging, "getLevelName", side_effect=mock_getLevelName
                ):
                    with caplog.at_level("WARNING"):
                        result = await reloader.reload()

        assert result.success is True  # Reload succeeds overall
        assert "logging.level" in result.changes
        # Warning should be logged about invalid level
        assert any("invalid" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_reload_includes_error_type_in_message(self) -> None:
        """Test that generic exceptions include error type in message."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        old_config = VPOConfig()
        reloader.set_current_config(old_config)

        with patch(
            "vpo.config.loader.get_config",
            side_effect=RuntimeError("Something went wrong"),
        ):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is False
        assert "RuntimeError" in result.error
        assert "Something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_reload_applies_rate_limit_changes(self) -> None:
        """Test that rate limit config changes are applied dynamically."""
        from vpo.server.rate_limit import RateLimiter

        state = ReloadState()
        reloader = ConfigReloader(state)
        rate_limiter = RateLimiter(RateLimitConfig(get_max_requests=100))
        reloader.set_rate_limiter(rate_limiter)

        old_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(get_max_requests=100))
        )
        new_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(get_max_requests=50))
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert "server.rate_limit.get_max_requests" in result.changes
        assert "server.rate_limit.get_max_requests" not in result.requires_restart
        # Rate limiter should have the new config
        assert rate_limiter._config.get_max_requests == 50

    @pytest.mark.asyncio
    async def test_reload_calls_reconfigure_on_rate_limiter(self) -> None:
        """Test that reconfigure() is called on the rate limiter during reload."""
        from vpo.server.rate_limit import RateLimiter

        state = ReloadState()
        reloader = ConfigReloader(state)

        rate_limiter = RateLimiter(RateLimitConfig())
        rate_limiter.reconfigure = MagicMock()  # type: ignore[assignment]
        reloader.set_rate_limiter(rate_limiter)

        old_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=True))
        )
        new_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=False))
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                await reloader.reload()

        rate_limiter.reconfigure.assert_called_once_with(new_config.server.rate_limit)

    @pytest.mark.asyncio
    async def test_reload_skips_rate_limiter_when_not_set(self) -> None:
        """Test that reload works when no rate limiter is wired up."""
        state = ReloadState()
        reloader = ConfigReloader(state)
        # Don't call set_rate_limiter

        old_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=True))
        )
        new_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=False))
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        # Should succeed without error even though no rate limiter set
        assert result.success is True
        assert "server.rate_limit.enabled" in result.changes

    @pytest.mark.asyncio
    async def test_reload_succeeds_when_reconfigure_raises(self) -> None:
        """Test that reload succeeds even if reconfigure() raises."""
        from vpo.server.rate_limit import RateLimiter

        state = ReloadState()
        reloader = ConfigReloader(state)

        rate_limiter = RateLimiter(RateLimitConfig())
        rate_limiter.reconfigure = MagicMock(  # type: ignore[assignment]
            side_effect=ValueError("bad config")
        )
        reloader.set_rate_limiter(rate_limiter)

        old_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=True))
        )
        new_config = VPOConfig(
            server=ServerConfig(rate_limit=RateLimitConfig(enabled=False))
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        # Reload overall succeeds; the rate limiter error is logged, not raised
        assert result.success is True
        assert "server.rate_limit.enabled" in result.changes

    @pytest.mark.asyncio
    async def test_reload_applies_multiple_rate_limit_fields(self) -> None:
        """Test that changing all rate limit fields at once works."""
        from vpo.server.rate_limit import RateLimiter

        state = ReloadState()
        reloader = ConfigReloader(state)
        rate_limiter = RateLimiter(RateLimitConfig())
        reloader.set_rate_limiter(rate_limiter)

        old_config = VPOConfig(
            server=ServerConfig(
                rate_limit=RateLimitConfig(
                    enabled=True,
                    get_max_requests=120,
                    mutate_max_requests=30,
                    window_seconds=60,
                )
            )
        )
        new_config = VPOConfig(
            server=ServerConfig(
                rate_limit=RateLimitConfig(
                    enabled=False,
                    get_max_requests=60,
                    mutate_max_requests=15,
                    window_seconds=30,
                )
            )
        )
        reloader.set_current_config(old_config)

        with patch("vpo.config.loader.get_config", return_value=new_config):
            with patch("vpo.config.loader.clear_config_cache"):
                result = await reloader.reload()

        assert result.success is True
        assert "server.rate_limit.enabled" in result.changes
        assert "server.rate_limit.get_max_requests" in result.changes
        assert "server.rate_limit.mutate_max_requests" in result.changes
        assert "server.rate_limit.window_seconds" in result.changes
        # All new values should be on the rate limiter
        assert rate_limiter._config.enabled is False
        assert rate_limiter._config.get_max_requests == 60
        assert rate_limiter._config.mutate_max_requests == 15
        assert rate_limiter._config.window_seconds == 30
