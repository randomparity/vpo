"""Unit tests for DaemonConnectionPool and execute_with_retry."""

import concurrent.futures
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.db.connection import (
    DaemonConnectionPool,
    execute_with_retry,
)


class TestDaemonConnectionPool:
    """Tests for DaemonConnectionPool thread-safety and lifecycle."""

    def test_pool_creates_connection_lazily(self, tmp_path: Path) -> None:
        """Test that connection is created on first access, not at init."""
        db_path = tmp_path / "test.db"
        # Create empty database
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)
        # Connection should not exist yet
        assert pool._write_conn is None

        # Access connection
        pool.get_connection()
        assert pool._write_conn is not None

        pool.close()

    def test_pool_reuses_connection(self, tmp_path: Path) -> None:
        """Test that multiple get_connection calls return same connection."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)

        conn1 = pool.get_connection()
        conn2 = pool.get_connection()
        assert conn1 is conn2

        pool.close()

    def test_pool_applies_pragmas(self, tmp_path: Path) -> None:
        """Test that standard PRAGMAs are applied to connections."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)
        conn = pool.get_connection()

        # Check WAL mode
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

        # Check foreign keys
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

        # Check busy timeout
        result = conn.execute("PRAGMA busy_timeout").fetchone()
        assert result[0] == 10000

        pool.close()

    def test_pool_close_prevents_new_connections(self, tmp_path: Path) -> None:
        """Test that closed pool raises on get_connection."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)
        pool.close()

        assert pool.is_closed
        with pytest.raises(RuntimeError, match="Connection pool is closed"):
            pool.get_connection()

    def test_pool_close_is_idempotent(self, tmp_path: Path) -> None:
        """Test that close() can be called multiple times safely."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)
        pool.get_connection()

        # Close multiple times - should not raise
        pool.close()
        pool.close()
        pool.close()

        assert pool.is_closed

    def test_execute_read_returns_results(self, tmp_path: Path) -> None:
        """Test that execute_read returns query results."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'foo'), (2, 'bar')")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)
        results = pool.execute_read("SELECT * FROM test ORDER BY id")

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["name"] == "foo"
        assert results[1]["id"] == 2
        assert results[1]["name"] == "bar"

        pool.close()

    def test_execute_read_with_params(self, tmp_path: Path) -> None:
        """Test that execute_read supports parameterized queries."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'foo'), (2, 'bar')")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)
        results = pool.execute_read("SELECT * FROM test WHERE id = ?", (1,))

        assert len(results) == 1
        assert results[0]["name"] == "foo"

        pool.close()

    def test_thread_safety_concurrent_reads(self, tmp_path: Path) -> None:
        """Test that concurrent reads from multiple threads are safe."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Set WAL mode before creating tables to allow concurrent reads
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("CREATE TABLE test (id INTEGER)")
        for i in range(100):
            conn.execute("INSERT INTO test VALUES (?)", (i,))
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)
        results: list = []
        errors: list = []

        def read_from_pool():
            try:
                result = pool.execute_read("SELECT COUNT(*) as cnt FROM test")
                results.append(result[0]["cnt"])
            except Exception as e:
                errors.append(str(e))

        # Run 50 concurrent reads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_from_pool) for _ in range(50)]
            concurrent.futures.wait(futures)

        pool.close()

        # All reads should succeed
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 50
        assert all(r == 100 for r in results)

    def test_thread_safety_with_locking(self, tmp_path: Path) -> None:
        """Test that lock prevents concurrent access corruption."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Set WAL mode before pool uses it to avoid concurrent WAL mode switching
        conn.execute("PRAGMA journal_mode = WAL")
        conn.close()

        pool = DaemonConnectionPool(db_path)

        # Track which threads acquired the lock
        lock_order: list[str] = []
        lock = threading.Lock()

        def access_pool(thread_id: str):
            # This will acquire the pool's internal lock
            pool.execute_read("SELECT 1")
            with lock:
                lock_order.append(thread_id)

        threads = [
            threading.Thread(target=access_pool, args=(f"t{i}",)) for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pool.close()

        # All threads should have completed
        assert len(lock_order) == 10

    def test_is_closed_property(self, tmp_path: Path) -> None:
        """Test is_closed property reflects pool state."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path)
        assert not pool.is_closed

        pool.close()
        assert pool.is_closed

    def test_pool_with_custom_timeout(self, tmp_path: Path) -> None:
        """Test that custom timeout is passed to connection."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        pool = DaemonConnectionPool(db_path, timeout=60.0)
        assert pool.timeout == 60.0

        pool.close()

    def test_execute_write_returns_rowcount(self, tmp_path: Path) -> None:
        """Test that execute_write returns the number of affected rows."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'foo'), (2, 'bar'), (3, 'baz')")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)

        # UPDATE should return number of affected rows
        rowcount = pool.execute_write(
            "UPDATE test SET name = ? WHERE id > ?", ("updated", 1)
        )
        assert rowcount == 2

        pool.close()

    def test_execute_write_commits_changes(self, tmp_path: Path) -> None:
        """Test that execute_write commits changes to the database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)

        # Insert a row
        pool.execute_write("INSERT INTO test VALUES (?, ?)", (1, "foo"))
        pool.close()

        # Verify the change persisted by opening a fresh connection
        conn = sqlite3.connect(str(db_path))
        result = conn.execute("SELECT * FROM test").fetchall()
        conn.close()

        assert len(result) == 1
        assert result[0] == (1, "foo")

    def test_transaction_commits_on_success(self, tmp_path: Path) -> None:
        """Test that transaction context manager commits on success."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)

        with pool.transaction() as conn:
            conn.execute("INSERT INTO test VALUES (?, ?)", (1, "foo"))
            conn.execute("INSERT INTO test VALUES (?, ?)", (2, "bar"))

        pool.close()

        # Verify both rows persisted
        conn = sqlite3.connect(str(db_path))
        result = conn.execute("SELECT * FROM test ORDER BY id").fetchall()
        conn.close()

        assert len(result) == 2
        assert result[0] == (1, "foo")
        assert result[1] == (2, "bar")

    def test_transaction_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Test that transaction context manager rolls back on exception."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)

        with pytest.raises(ValueError, match="test error"):
            with pool.transaction() as conn:
                conn.execute("INSERT INTO test VALUES (?, ?)", (1, "foo"))
                raise ValueError("test error")

        pool.close()

        # Verify no rows were inserted (rolled back)
        conn = sqlite3.connect(str(db_path))
        result = conn.execute("SELECT * FROM test").fetchall()
        conn.close()

        assert len(result) == 0

    def test_concurrent_read_write_operations(self, tmp_path: Path) -> None:
        """Test that concurrent read and write operations are thread-safe."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Set WAL mode before creating tables to allow concurrent reads
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, value INTEGER)")
        conn.execute("INSERT INTO counter VALUES (1, 0)")
        conn.commit()
        conn.close()

        pool = DaemonConnectionPool(db_path)
        errors: list = []

        def increment_counter():
            try:
                # Read current value
                result = pool.execute_read("SELECT value FROM counter WHERE id = 1")
                current = result[0]["value"]
                # Write incremented value
                pool.execute_write(
                    "UPDATE counter SET value = ? WHERE id = 1", (current + 1,)
                )
            except Exception as e:
                errors.append(str(e))

        def read_counter():
            try:
                pool.execute_read("SELECT value FROM counter WHERE id = 1")
            except Exception as e:
                errors.append(str(e))

        # Run mixed concurrent reads and writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(20):
                if i % 2 == 0:
                    futures.append(executor.submit(increment_counter))
                else:
                    futures.append(executor.submit(read_counter))
            concurrent.futures.wait(futures)

        pool.close()

        # No errors should have occurred
        assert len(errors) == 0, f"Errors: {errors}"


class TestExecuteWithRetry:
    """Tests for execute_with_retry function."""

    def test_succeeds_on_first_attempt(self) -> None:
        """Test that successful function returns immediately."""
        call_count = 0

        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = execute_with_retry(successful_func)

        assert result == "success"
        assert call_count == 1

    def test_retries_on_database_locked_error(self) -> None:
        """Test that database locked errors trigger retry."""
        call_count = 0

        def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        with patch("time.sleep"):  # Skip actual delays
            result = execute_with_retry(fail_then_succeed, base_delay=0.01)

        assert result == "success"
        assert call_count == 3

    def test_retries_on_database_busy_error(self) -> None:
        """Test that database busy errors trigger retry."""
        call_count = 0

        def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise sqlite3.OperationalError("database table is busy")
            return "success"

        with patch("time.sleep"):
            result = execute_with_retry(fail_then_succeed, base_delay=0.01)

        assert result == "success"
        assert call_count == 2

    def test_raises_after_max_retries_exhausted(self) -> None:
        """Test that error is raised after max retries."""

        def always_fails() -> str:
            raise sqlite3.OperationalError("database is locked")

        with patch("time.sleep"):
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                execute_with_retry(always_fails, max_retries=3, base_delay=0.01)

    def test_does_not_retry_non_lock_errors(self) -> None:
        """Test that non-lock OperationalErrors are not retried."""
        call_count = 0

        def non_lock_error() -> str:
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("no such table: foo")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            execute_with_retry(non_lock_error)

        assert call_count == 1  # Should not retry

    def test_does_not_retry_other_exceptions(self) -> None:
        """Test that non-OperationalError exceptions are not retried."""
        call_count = 0

        def value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("something else")

        with pytest.raises(ValueError, match="something else"):
            execute_with_retry(value_error)

        assert call_count == 1

    def test_exponential_backoff(self) -> None:
        """Test that delays increase exponentially."""
        call_count = 0
        sleep_calls: list[float] = []

        def fail_three_times() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("time.sleep", side_effect=mock_sleep):
            # No jitter for predictable test
            with patch("random.uniform", return_value=0):
                result = execute_with_retry(
                    fail_three_times,
                    base_delay=0.1,
                    max_delay=10.0,
                    jitter=0,
                )

        assert result == "success"
        assert len(sleep_calls) == 3
        # Delays should be 0.1, 0.2, 0.4 (exponential)
        assert sleep_calls[0] == pytest.approx(0.1)
        assert sleep_calls[1] == pytest.approx(0.2)
        assert sleep_calls[2] == pytest.approx(0.4)

    def test_max_delay_caps_backoff(self) -> None:
        """Test that max_delay caps the backoff."""
        call_count = 0
        sleep_calls: list[float] = []

        def fail_many_times() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("random.uniform", return_value=0):
                result = execute_with_retry(
                    fail_many_times,
                    base_delay=1.0,
                    max_delay=2.0,
                    jitter=0,
                    max_retries=5,
                )

        assert result == "success"
        # Delays should be 1.0, 2.0, 2.0, 2.0, 2.0 (capped at max_delay)
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)
        assert sleep_calls[2] == pytest.approx(2.0)
        assert all(d <= 2.0 for d in sleep_calls)

    def test_jitter_adds_randomness(self) -> None:
        """Test that jitter adds randomness to delays."""
        call_count = 0
        sleep_calls: list[float] = []

        def fail_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError("database is locked")
            return "success"

        def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        # Mock random.uniform to return 0.05 (5% jitter)
        with patch("time.sleep", side_effect=mock_sleep):
            with patch("random.uniform", return_value=0.05):
                execute_with_retry(
                    fail_once,
                    base_delay=1.0,
                    jitter=0.1,  # 10% max jitter
                )

        # Delay should be 1.0 * (1 + 0.05) = 1.05
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == pytest.approx(1.05)
