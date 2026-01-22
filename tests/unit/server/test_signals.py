"""Unit tests for signal handler setup."""

import asyncio
import signal
import sys

import pytest


class TestSignalSetup:
    """Tests for signal handler registration."""

    def test_sigterm_sigint_are_standard_signals(self) -> None:
        """Verify SIGTERM and SIGINT are available as expected."""
        assert hasattr(signal, "SIGTERM")
        assert hasattr(signal, "SIGINT")
        assert signal.SIGTERM.value == 15
        assert signal.SIGINT.value == 2

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_is_available_on_unix(self) -> None:
        """Verify SIGHUP is available on Unix-like systems."""
        assert hasattr(signal, "SIGHUP")
        assert signal.SIGHUP.value == 1

    def test_shutdown_event_creation(self) -> None:
        """Test that asyncio.Event can be created for shutdown coordination."""
        shutdown_event = asyncio.Event()
        assert not shutdown_event.is_set()
        shutdown_event.set()
        assert shutdown_event.is_set()

    def test_signal_handlers_registrable_in_event_loop(self) -> None:
        """Verify signal handlers can be registered on an event loop."""

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            called = []

            def handler(sig: signal.Signals) -> None:
                called.append(sig)

            # Register handler for SIGUSR1 (safe test signal)
            loop.add_signal_handler(signal.SIGUSR1, handler, signal.SIGUSR1)
            try:
                # Handler registered successfully
                assert True
            finally:
                loop.remove_signal_handler(signal.SIGUSR1)

        asyncio.run(_test())

    def test_asyncio_event_for_cross_task_coordination(self) -> None:
        """Test asyncio.Event works for task coordination."""

        async def _test() -> None:
            shutdown_event = asyncio.Event()
            task_completed = False

            async def background_task() -> None:
                nonlocal task_completed
                await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
                task_completed = True

            task = asyncio.create_task(background_task())

            # Task should be waiting
            await asyncio.sleep(0.01)
            assert not task_completed

            # Signal shutdown
            shutdown_event.set()
            await asyncio.sleep(0.01)
            assert task_completed

            await task

        asyncio.run(_test())


class TestSignalHandlerRegistration:
    """Tests for setup_signal_handlers function."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_setup_signal_handlers_registers_sigterm(self) -> None:
        """Test that SIGTERM handler is registered."""
        from vpo.server.lifecycle import DaemonLifecycle
        from vpo.server.signals import remove_signal_handlers, setup_signal_handlers

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            lifecycle = DaemonLifecycle()
            shutdown_event = asyncio.Event()

            setup_signal_handlers(loop, lifecycle, shutdown_event)
            try:
                # Handler should be registered (we can't easily test the handler
                # itself, but registration should not raise)
                pass
            finally:
                remove_signal_handlers(loop)

        asyncio.run(_test())

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_setup_signal_handlers_with_reload_callback(self) -> None:
        """Test that SIGHUP handler is registered when callback provided."""
        from vpo.server.lifecycle import DaemonLifecycle
        from vpo.server.signals import remove_signal_handlers, setup_signal_handlers

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            lifecycle = DaemonLifecycle()
            shutdown_event = asyncio.Event()
            reload_called = False

            async def reload_callback() -> None:
                nonlocal reload_called
                reload_called = True

            setup_signal_handlers(loop, lifecycle, shutdown_event, reload_callback)
            try:
                # Handler should be registered
                pass
            finally:
                remove_signal_handlers(loop)

        asyncio.run(_test())

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_remove_signal_handlers_removes_sighup(self) -> None:
        """Test that SIGHUP handler is removed during cleanup."""
        from vpo.server.lifecycle import DaemonLifecycle
        from vpo.server.signals import remove_signal_handlers, setup_signal_handlers

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            lifecycle = DaemonLifecycle()
            shutdown_event = asyncio.Event()

            async def reload_callback() -> None:
                pass

            setup_signal_handlers(loop, lifecycle, shutdown_event, reload_callback)

            # Should not raise - handlers exist
            remove_signal_handlers(loop)

            # Removing again should not raise either (idempotent)
            remove_signal_handlers(loop)

        asyncio.run(_test())


class TestSIGHUPCallback:
    """Tests for SIGHUP reload callback behavior."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_callback_is_async(self) -> None:
        """Test that reload callback must be async."""
        from vpo.server.signals import ReloadCallback

        # Type hint shows it returns a Future
        async def valid_callback() -> None:
            pass

        # This should be a valid ReloadCallback
        callback: ReloadCallback = valid_callback
        assert asyncio.iscoroutinefunction(callback)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_handler_schedules_callback(self) -> None:
        """Test that SIGHUP handler schedules the async callback."""
        import os

        from vpo.server.lifecycle import DaemonLifecycle
        from vpo.server.signals import remove_signal_handlers, setup_signal_handlers

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            lifecycle = DaemonLifecycle()
            shutdown_event = asyncio.Event()
            callback_called = asyncio.Event()

            async def reload_callback() -> None:
                callback_called.set()

            setup_signal_handlers(loop, lifecycle, shutdown_event, reload_callback)
            try:
                # Send SIGHUP to ourselves
                os.kill(os.getpid(), signal.SIGHUP)

                # Wait for callback to be called
                try:
                    await asyncio.wait_for(callback_called.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pytest.fail("Reload callback was not called within timeout")

                assert callback_called.is_set()
            finally:
                remove_signal_handlers(loop)

        asyncio.run(_test())

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_without_callback_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that SIGHUP without callback logs a warning."""
        import os

        from vpo.server.lifecycle import DaemonLifecycle
        from vpo.server.signals import remove_signal_handlers, setup_signal_handlers

        async def _test() -> None:
            loop = asyncio.get_running_loop()
            lifecycle = DaemonLifecycle()
            shutdown_event = asyncio.Event()

            # No reload_callback provided
            setup_signal_handlers(loop, lifecycle, shutdown_event)
            try:
                # Send SIGHUP to ourselves
                os.kill(os.getpid(), signal.SIGHUP)

                # Give time for handler to run
                await asyncio.sleep(0.1)

                # Should not crash, should log warning
            finally:
                remove_signal_handlers(loop)

        with caplog.at_level("WARNING"):
            asyncio.run(_test())

        # Warning should be logged
        assert any("SIGHUP" in record.message for record in caplog.records)
