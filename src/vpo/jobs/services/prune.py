"""Prune job service for removing missing files from the library.

This module provides the service for processing PRUNE jobs, which
delete database records for files that are no longer on the filesystem
(scan_status='missing').
"""

import logging
import sqlite3
from dataclasses import dataclass

from vpo.db.queries import delete_file
from vpo.jobs.logs import JobLogWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PruneJobResult:
    """Result of processing a prune job."""

    success: bool
    files_pruned: int = 0
    error_message: str | None = None


class PruneJobService:
    """Service for pruning missing files from the library.

    Queries all files with scan_status='missing' and deletes their
    database records.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def process(
        self,
        *,
        job_log: JobLogWriter | None = None,
    ) -> PruneJobResult:
        """Prune all files with scan_status='missing'.

        Args:
            job_log: Optional log writer for recording progress.

        Returns:
            PruneJobResult with count of pruned files.
        """
        try:
            # Find all missing files
            cursor = self.conn.execute(
                "SELECT id, path FROM files WHERE scan_status = 'missing'"
            )
            missing_files = cursor.fetchall()

            if not missing_files:
                if job_log:
                    job_log.write_line("No missing files to prune")
                return PruneJobResult(success=True, files_pruned=0)

            if job_log:
                job_log.write_line(
                    f"Found {len(missing_files)} missing file(s) to prune"
                )

            pruned = 0
            # Ensure we start a clean transaction for atomic deletion
            if self.conn.in_transaction:
                self.conn.commit()
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                for file_id, file_path in missing_files:
                    delete_file(self.conn, file_id)
                    pruned += 1
                    if job_log:
                        job_log.write_line(f"  Pruned: {file_path}")
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

            logger.info("Pruned %d missing file(s) from library", pruned)
            if job_log:
                job_log.write_line(f"Pruned {pruned} file(s)")

            return PruneJobResult(success=True, files_pruned=pruned)

        except Exception as e:
            logger.exception("Prune job failed: %s", e)
            return PruneJobResult(
                success=False,
                error_message=str(e),
            )
