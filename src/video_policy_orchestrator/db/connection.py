"""Database connection management for Video Policy Orchestrator."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

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
