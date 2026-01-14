"""Simple in-memory metrics for VPO observability.

This module provides lightweight metrics collection without external dependencies.
Designed for internal observability and health endpoint exposure.

Key patterns:
- Thread-safe in-memory storage (no external dependencies)
- Rolling windows for duration samples (last 1000 per metric)
- UTC timestamps for all timing data
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Configuration
MAX_DURATION_SAMPLES = 1000  # Per metric name


@dataclass
class DurationSample:
    """A single duration measurement."""

    duration_seconds: float
    timestamp: str  # ISO-8601 UTC
    labels: dict[str, str] = field(default_factory=dict)


class MetricsStore:
    """Thread-safe in-memory metrics storage.

    Stores counters and duration samples for health endpoint exposure.
    Uses module-level singleton pattern via get_metrics_store().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._durations: dict[str, list[DurationSample]] = defaultdict(list)

    def increment_counter(self, name: str, value: int = 1, **labels: str) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name (e.g., 'plugin.invocations')
            value: Amount to increment (default: 1)
            **labels: Optional labels (e.g., plugin_name='whisper')
        """
        key = self._build_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def record_duration(
        self,
        name: str,
        duration_seconds: float,
        **labels: str,
    ) -> None:
        """Record a duration measurement.

        Args:
            name: Metric name (e.g., 'plugin.duration')
            duration_seconds: Duration in seconds
            **labels: Optional labels
        """
        sample = DurationSample(
            duration_seconds=duration_seconds,
            timestamp=datetime.now(timezone.utc).isoformat(),
            labels=dict(labels),
        )
        key = self._build_key(name, labels)
        with self._lock:
            samples = self._durations[key]
            samples.append(sample)
            # Rolling window - keep only last N samples
            if len(samples) > MAX_DURATION_SAMPLES:
                self._durations[key] = samples[-MAX_DURATION_SAMPLES:]

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary for health endpoint.

        Returns:
            Dict with counters and duration stats suitable for JSON serialization.
        """
        with self._lock:
            result: dict[str, Any] = {
                "counters": dict(self._counters),
                "durations": {},
            }
            for key, samples in self._durations.items():
                if samples:
                    durations = [s.duration_seconds for s in samples]
                    result["durations"][key] = {
                        "count": len(durations),
                        "avg_seconds": sum(durations) / len(durations),
                        "max_seconds": max(durations),
                        "min_seconds": min(durations),
                    }
            return result

    def clear(self) -> None:
        """Clear all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._durations.clear()

    @staticmethod
    def _build_key(name: str, labels: dict[str, str]) -> str:
        """Build a unique key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Module-level singleton
_metrics_store: MetricsStore | None = None
_store_lock = threading.Lock()


def get_metrics_store() -> MetricsStore:
    """Get the global metrics store singleton."""
    global _metrics_store
    if _metrics_store is None:
        with _store_lock:
            if _metrics_store is None:
                _metrics_store = MetricsStore()
    return _metrics_store


# Convenience functions that use the singleton


def increment_counter(name: str, value: int = 1, **labels: str) -> None:
    """Increment a counter in the global store."""
    get_metrics_store().increment_counter(name, value, **labels)


@contextmanager
def record_duration(name: str, **labels: str) -> Generator[None, None, None]:
    """Context manager for timing operations.

    Usage:
        with record_duration("plugin.duration", plugin_name="whisper"):
            result = plugin.on_transcription_requested(event)
    """
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        get_metrics_store().record_duration(name, duration, **labels)


def get_metrics_summary() -> dict[str, Any]:
    """Get metrics summary from the global store."""
    return get_metrics_store().get_summary()
