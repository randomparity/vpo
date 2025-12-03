"""Unit tests for logging context module."""

import logging
import threading
from pathlib import Path

from video_policy_orchestrator.logging.context import (
    WorkerContextFilter,
    clear_worker_context,
    get_worker_context,
    set_worker_context,
    worker_context,
)


class TestSetAndGetWorkerContext:
    """Tests for set_worker_context and get_worker_context functions."""

    def test_set_and_get_full_context(self) -> None:
        """Test setting and getting all context values."""
        set_worker_context("01", "F001", "/path/to/file.mkv")
        worker_id, file_id, file_path = get_worker_context()

        assert worker_id == "01"
        assert file_id == "F001"
        assert file_path == "/path/to/file.mkv"

        clear_worker_context()

    def test_set_and_get_partial_context(self) -> None:
        """Test setting only worker_id."""
        set_worker_context("02")
        worker_id, file_id, file_path = get_worker_context()

        assert worker_id == "02"
        assert file_id is None
        assert file_path is None

        clear_worker_context()

    def test_set_with_path_object(self) -> None:
        """Test setting file_path as Path object."""
        set_worker_context("01", "F001", Path("/path/to/file.mkv"))
        _, _, file_path = get_worker_context()

        assert file_path == "/path/to/file.mkv"

        clear_worker_context()

    def test_clear_context(self) -> None:
        """Test clearing all context values."""
        set_worker_context("01", "F001", "/path/to/file.mkv")
        clear_worker_context()
        worker_id, file_id, file_path = get_worker_context()

        assert worker_id is None
        assert file_id is None
        assert file_path is None

    def test_default_context_is_none(self) -> None:
        """Test that default context values are None."""
        clear_worker_context()
        worker_id, file_id, file_path = get_worker_context()

        assert worker_id is None
        assert file_id is None
        assert file_path is None


class TestWorkerContextManager:
    """Tests for worker_context context manager."""

    def test_context_manager_sets_values(self) -> None:
        """Test that context manager sets values on entry."""
        with worker_context("03", "F042", "/path/to/movie.mkv"):
            worker_id, file_id, file_path = get_worker_context()
            assert worker_id == "03"
            assert file_id == "F042"
            assert file_path == "/path/to/movie.mkv"

    def test_context_manager_clears_on_exit(self) -> None:
        """Test that context manager restores previous values on exit."""
        clear_worker_context()
        with worker_context("03", "F042", "/path/to/movie.mkv"):
            pass
        worker_id, file_id, file_path = get_worker_context()

        assert worker_id is None
        assert file_id is None
        assert file_path is None

    def test_nested_context_managers(self) -> None:
        """Test nested context managers restore correctly."""
        with worker_context("01", "F001", "/first.mkv"):
            with worker_context("02", "F002", "/second.mkv"):
                worker_id, file_id, file_path = get_worker_context()
                assert worker_id == "02"
                assert file_id == "F002"
                assert file_path == "/second.mkv"

            # After inner context exits, outer should be restored
            worker_id, file_id, file_path = get_worker_context()
            assert worker_id == "01"
            assert file_id == "F001"
            assert file_path == "/first.mkv"

    def test_context_manager_on_exception(self) -> None:
        """Test that context is restored even on exception."""
        clear_worker_context()
        try:
            with worker_context("01", "F001", "/path.mkv"):
                raise ValueError("test error")
        except ValueError:
            pass

        worker_id, file_id, file_path = get_worker_context()
        assert worker_id is None
        assert file_id is None
        assert file_path is None


class TestWorkerContextFilter:
    """Tests for WorkerContextFilter logging filter."""

    def test_filter_injects_context(self) -> None:
        """Test that filter injects context into log record."""
        filter_ = WorkerContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        with worker_context("05", "F123", "/path/to/video.mkv"):
            result = filter_.filter(record)

        assert result is True
        assert record.worker_id == "05"
        assert record.file_id == "F123"
        assert record.file_path == "/path/to/video.mkv"
        assert record.worker_tag == "[W05:F123] "

    def test_filter_with_no_context(self) -> None:
        """Test filter behavior when no context is set."""
        clear_worker_context()
        filter_ = WorkerContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = filter_.filter(record)

        assert result is True
        assert record.worker_id is None
        assert record.file_id is None
        assert record.file_path is None
        assert record.worker_tag == ""

    def test_filter_with_worker_only(self) -> None:
        """Test filter when only worker_id is set."""
        filter_ = WorkerContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        with worker_context("07", None, None):
            filter_.filter(record)

        assert record.worker_tag == "[W07] "

    def test_filter_never_removes_records(self) -> None:
        """Test that filter always returns True (never filters out)."""
        filter_ = WorkerContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        # Should return True in all cases
        assert filter_.filter(record) is True

        with worker_context("01", "F001", "/path"):
            assert filter_.filter(record) is True


class TestThreadIsolation:
    """Tests for thread isolation of context."""

    def test_context_is_thread_isolated(self) -> None:
        """Test that context is isolated between threads."""
        results: dict[str, tuple] = {}

        def worker(worker_id: str, file_id: str) -> None:
            with worker_context(worker_id, file_id, f"/path/{file_id}.mkv"):
                # Simulate some work
                import time

                time.sleep(0.01)
                results[worker_id] = get_worker_context()

        # Run two workers concurrently
        thread1 = threading.Thread(target=worker, args=("01", "F001"))
        thread2 = threading.Thread(target=worker, args=("02", "F002"))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Each thread should have its own context
        assert results["01"] == ("01", "F001", "/path/F001.mkv")
        assert results["02"] == ("02", "F002", "/path/F002.mkv")

    def test_main_thread_not_affected_by_worker_threads(self) -> None:
        """Test that worker threads don't affect main thread context."""
        clear_worker_context()

        def worker() -> None:
            with worker_context("99", "F999", "/worker/path.mkv"):
                import time

                time.sleep(0.01)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        # Main thread should still have no context
        worker_id, file_id, file_path = get_worker_context()
        assert worker_id is None
        assert file_id is None
        assert file_path is None
