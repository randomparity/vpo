"""Database connection management for Video Policy Orchestrator."""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

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
            if "locked" in str(e).lower():
                raise DatabaseLockedError(
                    "Database is locked. Another process may be using it."
                ) from e
            raise

    return wrapper


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

    Maintains a single connection that's safely shared across threads
    using a lock. This is appropriate for SQLite with WAL mode where
    readers don't block each other.

    The pool applies standard PRAGMAs (WAL, foreign keys, busy_timeout)
    and uses check_same_thread=False with explicit locking for safety.
    """

    def __init__(self, db_path: Path, timeout: float = 30.0) -> None:
        """Initialize the connection pool.

        Args:
            db_path: Path to SQLite database file.
            timeout: Connection timeout in seconds.
        """
        self.db_path = db_path
        self.timeout = timeout
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._closed = False

    def _get_connection_unlocked(self) -> sqlite3.Connection:
        """Get the shared connection. Must be called with lock held."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                check_same_thread=False,  # Safe with our locking
            )

            # Apply standard PRAGMAs
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA busy_timeout = 10000")
            self._conn.execute("PRAGMA temp_store = MEMORY")
            self._conn.row_factory = sqlite3.Row

        return self._conn

    def get_connection(self) -> sqlite3.Connection:
        """Get the shared connection, creating if needed.

        Returns:
            The shared SQLite connection.

        Raises:
            RuntimeError: If the pool has been closed.
        """
        with self._lock:
            return self._get_connection_unlocked()

    def execute_read(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a read-only query safely.

        This method acquires the lock to ensure thread-safe access
        to the shared connection.

        Args:
            query: SQL query to execute.
            params: Query parameters.

        Returns:
            List of result rows.
        """
        with self._lock:
            conn = self._get_connection_unlocked()
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a write query safely (INSERT/UPDATE/DELETE).

        This method acquires the lock to ensure thread-safe access
        to the shared connection and commits the transaction.

        Args:
            query: SQL query to execute.
            params: Query parameters.

        Returns:
            Number of affected rows.
        """
        with self._lock:
            conn = self._get_connection_unlocked()
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for atomic database transactions.

        Automatically commits on success, rolls back on exception.
        Uses BEGIN IMMEDIATE for write-intent transactions.

        The connection is yielded to allow direct execution of multiple
        statements within the transaction. Do NOT use execute_write()
        inside a transaction as it will commit automatically.

        Example:
            with pool.transaction() as conn:
                conn.execute("INSERT INTO ...", (...))
                conn.execute("UPDATE ...", (...))

        Yields:
            The database connection for direct query execution.

        Raises:
            Exception: Re-raises any exception after rollback.
        """
        with self._lock:
            conn = self._get_connection_unlocked()
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def close(self) -> None:
        """Close the connection pool.

        After closing, the pool cannot be reused. Any attempts to
        get a connection will raise RuntimeError.
        """
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception as e:
                    logger.warning("Error closing connection pool: %s", e)
                self._conn = None
            self._closed = True

    @property
    def is_closed(self) -> bool:
        """Check if the pool has been closed."""
        with self._lock:
            return self._closed
