"""Data models for scanner operations (008-operational-ux)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ScanResult:
    """Result of a directory scan operation."""

    job_id: str  # UUID of the scan job
    directory: Path  # Root directory scanned
    started_at: datetime  # UTC timestamp
    completed_at: datetime | None = None  # UTC timestamp

    # Counts
    total_discovered: int = 0  # Files found on disk
    scanned: int = 0  # Files introspected
    skipped: int = 0  # Files unchanged (incremental)
    added: int = 0  # New files added to DB
    removed: int = 0  # Files marked missing/deleted
    errors: int = 0  # Files with scan errors

    # Mode
    incremental: bool = True  # Whether incremental mode was used

    def to_summary_dict(self) -> dict[str, int]:
        """Get summary as dict for job storage."""
        return {
            "total_discovered": self.total_discovered,
            "scanned": self.scanned,
            "skipped": self.skipped,
            "added": self.added,
            "removed": self.removed,
            "errors": self.errors,
        }

    def to_summary_json(self) -> str:
        """Serialize counts for job storage."""
        return json.dumps(self.to_summary_dict())
