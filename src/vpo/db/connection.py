"""Database connection management for Video Policy Orchestrator."""

from __future__ import annotations

import logging
import random
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_DB_PATH = Path.home() / ".vpo" / "library.db"


def get_default_db_path() -> Path:
    """Return the default database path (~/.vpo/library.db)."""
    return DEFAULT_DB_PATH


def ensure_db_directory(db_path: Path) -> None:
    """Ensure the database directory exists, creating it if necessary."""
    db_path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(
    db_path: Path | None = None, timeout: float = 30.0
) -> Iterator[sqlite3.Connection]:
    """Get a database connection with proper settings.

    Args:
        db_path: Path to the database file. Defaults to ~/.vpo/library.db.
        timeout: How long to wait for locks (seconds). Default 30s.

    Yields:
        An sqlite3 Connection object.

    Raises:
        sqlite3.OperationalError: If database is locked and timeout exceeded.
    """
    if db_path is None:
        db_path = get_default_db_path()

    ensure_db_directory(db_path)

    conn = sqlite3.connect(str(db_path), timeout=timeout)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Enable WAL mode for better concurrency (multiple readers, single writer)
    conn.execute("PRAGMA journal_mode = WAL")

    # Set synchronous to NORMAL for balance of safety and speed
    # NORMAL is safe with WAL mode and provides good durability
    conn.execute("PRAGMA synchronous = NORMAL")

    # Increase busy timeout for better handling of lock contention
    conn.execute("PRAGMA busy_timeout = 10000")

    # Store temp tables in memory for performance
    conn.execute("PRAGMA temp_store = MEMORY")

    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        conn.close()


class DatabaseLockedError(Exception):
    """Raised when the database is locked and cannot be accessed."""

    pass


def handle_database_locked(func):
    """Decorator to convert sqlite3.OperationalError to DatabaseLockedError."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).casefold():
                raise DatabaseLockedError(
                    "Database is locked. Another process may be using it."
                ) from e
            raise

    return wrapper


def execute_with_retry(
    func: Callable[[], T],
    max_retries: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    jitter: float = 0.1,
) -> T:
    """Execute a function with exponential backoff retry on database lock errors.

    Uses BEGIN IMMEDIATE semantics: fails fast on lock contention rather than
    waiting for busy_timeout, then retries with exponential backoff.

    Args:
        func: Function to execute. Should raise sqlite3.OperationalError
            with "locked" or "busy" message on lock contention.
        max_retries: Maximum number of retry attempts. Default 5.
        base_delay: Initial delay in seconds. Default 0.1s.
        max_delay: Maximum delay between retries. Default 5.0s.
        jitter: Random jitter factor (0-1) to avoid thundering herd. Default 0.1.

    Returns:
        The return value of func.

    Raises:
        sqlite3.OperationalError: If all retries exhausted or non-lock error.
        Any other exception raised by func.

    Example:
        def do_write():
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute("INSERT ...", params)
                conn.commit()
                return cursor.lastrowid
            except:
                conn.rollback()
                raise

        result = execute_with_retry(do_write)
    """
    last_error: sqlite3.OperationalError | None = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            result = func()
            # Log success after retry recovery
            if attempt > 0:
                logger.info(
                    "Database operation succeeded after %d retry attempt(s)",
                    attempt,
                )
            return result
        except sqlite3.OperationalError as e:
            error_msg = str(e).casefold()
            if "locked" not in error_msg and "busy" not in error_msg:
                # Not a lock error, don't retry
                raise

            last_error = e

            if attempt >= max_retries:
                logger.warning(
                    "Database lock retry exhausted after %d attempts: %s",
                    max_retries + 1,
                    e,
                )
                raise

            # Add jitter to avoid thundering herd
            jittered_delay = delay * (1 + random.uniform(-jitter, jitter))  # nosec B311
            logger.info(
                "Database locked (attempt %d/%d), retrying in %.2fs: %s",
                attempt + 1,
                max_retries + 1,
                jittered_delay,
                e,
            )
            time.sleep(jittered_delay)

            # Exponential backoff, capped at max_delay
            delay = min(delay * 2, max_delay)

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("execute_with_retry: unexpected state")


def check_database_connectivity(db_path: Path | None = None) -> bool:
    """Check if the database is accessible.

    Performs a simple SELECT 1 query to verify database connectivity.
    This is a synchronous operation intended for health checks.

    Args:
        db_path: Path to the database file. Defaults to ~/.vpo/library.db.

    Returns:
        True if database is accessible and responds to queries, False otherwise.
    """
    if db_path is None:
        db_path = get_default_db_path()

    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception:
        return False


class DaemonConnectionPool:
    """Thread-safe connection pool for daemon mode.

    Uses separate connection strategies for reads and writes to maximize
    concurrency with SQLite WAL mode:

    - Read operations: Create a new connection per operation (no locking),
      allowing concurrent reads without blocking.
    - Write operations: Use a shared connection with locking to ensure
      only one write at a time.

    The pool applies standard PRAGMAs (WAL, foreign keys, busy_timeout)
    to all connections.
    """

    def __init__(self, db_path: Path, timeout: float = 30.0) -> None:
        """Initialize the connection pool.

        Args:
            db_path: Path to SQLite database file.
            timeout: Connection timeout in seconds.
        """
        self.db_path = db_path
        self.timeout = timeout
        self._write_conn: sqlite3.Connection | None = None
        self._write_lock = threading.Lock()
        self._closed = False
        self._closed_lock = threading.Lock()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new connection with standard PRAGMAs.

        Returns:
            A configured SQLite connection.
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            check_same_thread=False,
        )

        # Apply standard PRAGMAs
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.row_factory = sqlite3.Row

        return conn

    def _get_or_create_write_connection(self) -> sqlite3.Connection:
        """Get the shared write connection, creating if needed.

        IMPORTANT: Must be called with _write_lock held. This method
        additionally acquires _closed_lock briefly to check pool state.

        Includes a health check to verify the cached connection is still valid.
        If the connection was closed externally, a new connection is created.
        """
        with self._closed_lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")

        if self._write_conn is None:
            self._write_conn = self._create_connection()
        else:
            # Verify cached connection is still valid
            try:
                self._write_conn.execute("SELECT 1")
            except (sqlite3.ProgrammingError, sqlite3.OperationalError) as e:
                logger.warning("Cached connection is invalid (%s), creating new", e)
                # Close old connection to prevent resource leak
                old_conn = self._write_conn
                self._write_conn = None
                try:
                    old_conn.close()
                except Exception:  # nosec B110 - best-effort cleanup
                    pass  # Connection may already be in bad state
                self._write_conn = self._create_connection()

        return self._write_conn

    # Legacy aliases for backward compatibility
    _get_connection_unlocked = _get_or_create_write_connection
    _get_write_connection_unlocked = _get_or_create_write_connection
    _conn = property(lambda self: self._write_conn)
    _lock = property(lambda self: self._write_lock)

    def get_connection(self) -> sqlite3.Connection:
        """Get the shared write connection, creating if needed.

        Returns:
            The shared SQLite connection.

        Raises:
            RuntimeError: If the pool has been closed.
        """
        with self._write_lock:
            return self._get_or_create_write_connection()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a read-only connection (new connection per call).

        Creates a new connection for each read operation, allowing concurrent
        reads without lock contention. The connection is closed when the
        context manager exits.

        Yields:
            A fresh SQLite connection for reading.

        Raises:
            RuntimeError: If the pool has been closed.
        """
        with self._closed_lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")
        conn = self._create_connection()
        try:
            yield conn
        finally:
            conn.close()

    def execute_read(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a read-only query with its own connection.

        Uses a fresh connection per read to avoid blocking on the write lock.
        This allows concurrent reads in WAL mode without serialization.

        Args:
            query: SQL query to execute.
            params: Query parameters.

        Returns:
            List of result rows.
        """
        with self.read_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a write query safely (INSERT/UPDATE/DELETE).

        This method acquires the write lock to ensure thread-safe access
        to the shared connection and commits the transaction.

        Args:
            query: SQL query to execute.
            params: Query parameters.

        Returns:
            Number of affected rows.
        """
        with self._write_lock:
            conn = self._get_or_create_write_connection()
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount

    @contextmanager
    def transaction(self, timeout: float | None = None) -> Iterator[sqlite3.Connection]:
        """Context manager for atomic database transactions.

        Automatically commits on success, rolls back on exception.
        Uses BEGIN IMMEDIATE for write-intent transactions.

        Includes timing instrumentation to log warnings for slow transactions
        (>80% of timeout). This helps identify performance issues before
        they cause actual timeouts.

        The connection is yielded to allow direct execution of multiple
        statements within the transaction. Do NOT use execute_write()
        inside a transaction as it will commit automatically.

        Args:
            timeout: Optional timeout threshold for slow transaction warnings.
                If not specified, uses the pool's configured timeout.

        Example:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO ...", (...))
                conn.execute("UPDATE ...", (...))

        Yields:
            The database connection for direct query execution.

        Raises:
            Exception: Re-raises any exception after rollback.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        start_time = time.monotonic()

        with self._write_lock:
            conn = self._get_or_create_write_connection()
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                elapsed = time.monotonic() - start_time
                # Warn if transaction took >80% of timeout threshold
                if elapsed > effective_timeout * 0.8:
                    logger.warning(
                        "Slow transaction: %.2fs (threshold: %.1fs)",
                        elapsed,
                        effective_timeout,
                    )

    def close(self) -> None:
        """Close the connection pool.

        After closing, the pool cannot be reused. Any attempts to
        get a connection will raise RuntimeError.

        Raises:
            Exception: Re-raises any exception from closing the connection
                (after logging and marking the pool as closed).
        """
        with self._write_lock:
            if self._write_conn is not None:
                try:
                    self._write_conn.close()
                except Exception as e:
                    logger.error("Error closing connection pool: %s", e)
                    self._write_conn = None
                    with self._closed_lock:
                        self._closed = True
                    raise
                self._write_conn = None
            with self._closed_lock:
                self._closed = True

    def __del__(self) -> None:
        """Ensure connection is closed on garbage collection.

        This is a safety net for cases where close() was not called explicitly.
        Logs a warning if the pool was not properly closed.
        """
        # Use getattr with defaults to handle partially initialized objects
        if not getattr(self, "_closed", True) and getattr(self, "_write_conn", None):
            logger.warning("DaemonConnectionPool was not properly closed")
            try:
                self._write_conn.close()
            except Exception:  # nosec B110 - Best effort cleanup in destructor
                pass

    @property
    def is_closed(self) -> bool:
        """Check if the pool has been closed."""
        with self._closed_lock:
            return self._closed
