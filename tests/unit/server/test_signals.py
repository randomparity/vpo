"""Unit tests for signal handler setup."""

import asyncio
import signal


class TestSignalSetup:
    """Tests for signal handler registration."""

    def test_sigterm_sigint_are_standard_signals(self) -> None:
        """Verify SIGTERM and SIGINT are available as expected."""
        assert hasattr(signal, "SIGTERM")
        assert hasattr(signal, "SIGINT")
        assert signal.SIGTERM.value == 15
        assert signal.SIGINT.value == 2

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
