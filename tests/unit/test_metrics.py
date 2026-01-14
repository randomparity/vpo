"""Tests for metrics module."""

import time

import pytest

from vpo.metrics import (
    DurationSample,
    MetricsStore,
    get_metrics_store,
    get_metrics_summary,
    increment_counter,
    record_duration,
)


class TestMetricsStore:
    """Tests for MetricsStore class."""

    def test_increment_counter_default(self) -> None:
        """Test incrementing counter by 1."""
        store = MetricsStore()
        store.increment_counter("test.counter")
        store.increment_counter("test.counter")

        summary = store.get_summary()
        assert summary["counters"]["test.counter"] == 2

    def test_increment_counter_by_value(self) -> None:
        """Test incrementing counter by specific value."""
        store = MetricsStore()
        store.increment_counter("test.counter", 5)
        store.increment_counter("test.counter", 3)

        summary = store.get_summary()
        assert summary["counters"]["test.counter"] == 8

    def test_increment_counter_with_labels(self) -> None:
        """Test incrementing counters with different labels."""
        store = MetricsStore()
        store.increment_counter("plugin.calls", plugin_name="whisper")
        store.increment_counter("plugin.calls", plugin_name="whisper")
        store.increment_counter("plugin.calls", plugin_name="other")

        summary = store.get_summary()
        assert summary["counters"]["plugin.calls{plugin_name=whisper}"] == 2
        assert summary["counters"]["plugin.calls{plugin_name=other}"] == 1

    def test_record_duration(self) -> None:
        """Test recording duration samples."""
        store = MetricsStore()
        store.record_duration("test.duration", 1.5)
        store.record_duration("test.duration", 2.5)
        store.record_duration("test.duration", 3.0)

        summary = store.get_summary()
        duration_stats = summary["durations"]["test.duration"]
        assert duration_stats["count"] == 3
        assert duration_stats["avg_seconds"] == pytest.approx(2.33, rel=0.1)
        assert duration_stats["min_seconds"] == 1.5
        assert duration_stats["max_seconds"] == 3.0

    def test_record_duration_with_labels(self) -> None:
        """Test recording durations with labels."""
        store = MetricsStore()
        store.record_duration("plugin.duration", 1.0, plugin_name="whisper")
        store.record_duration("plugin.duration", 2.0, plugin_name="whisper")
        store.record_duration("plugin.duration", 0.5, plugin_name="other")

        summary = store.get_summary()
        assert "plugin.duration{plugin_name=whisper}" in summary["durations"]
        assert "plugin.duration{plugin_name=other}" in summary["durations"]
        assert (
            summary["durations"]["plugin.duration{plugin_name=whisper}"]["count"] == 2
        )
        assert summary["durations"]["plugin.duration{plugin_name=other}"]["count"] == 1

    def test_rolling_window_limits_samples(self) -> None:
        """Test that duration samples are limited to MAX_DURATION_SAMPLES."""
        store = MetricsStore()
        # Record more than MAX_DURATION_SAMPLES (1000)
        for i in range(1100):
            store.record_duration("test.duration", float(i))

        summary = store.get_summary()
        # Should only keep last 1000 samples
        assert summary["durations"]["test.duration"]["count"] == 1000
        # Min should be 100 (100-1099 are the last 1000 values)
        assert summary["durations"]["test.duration"]["min_seconds"] == 100.0

    def test_clear(self) -> None:
        """Test clearing all metrics."""
        store = MetricsStore()
        store.increment_counter("test.counter", 10)
        store.record_duration("test.duration", 5.0)

        store.clear()

        summary = store.get_summary()
        assert summary["counters"] == {}
        assert summary["durations"] == {}

    def test_build_key_no_labels(self) -> None:
        """Test key building without labels."""
        key = MetricsStore._build_key("test.metric", {})
        assert key == "test.metric"

    def test_build_key_with_labels(self) -> None:
        """Test key building with labels (sorted)."""
        key = MetricsStore._build_key("test.metric", {"z": "1", "a": "2"})
        assert key == "test.metric{a=2,z=1}"

    def test_get_summary_empty(self) -> None:
        """Test summary when no metrics recorded."""
        store = MetricsStore()
        summary = store.get_summary()
        assert summary == {"counters": {}, "durations": {}}


class TestDurationSample:
    """Tests for DurationSample dataclass."""

    def test_duration_sample_creation(self) -> None:
        """Test creating a DurationSample."""
        sample = DurationSample(
            duration_seconds=1.5,
            timestamp="2026-01-09T12:00:00+00:00",
            labels={"key": "value"},
        )
        assert sample.duration_seconds == 1.5
        assert sample.timestamp == "2026-01-09T12:00:00+00:00"
        assert sample.labels == {"key": "value"}

    def test_duration_sample_default_labels(self) -> None:
        """Test that labels defaults to empty dict."""
        sample = DurationSample(
            duration_seconds=1.0,
            timestamp="2026-01-09T12:00:00+00:00",
        )
        assert sample.labels == {}


class TestRecordDurationContextManager:
    """Tests for record_duration context manager."""

    def test_context_manager_timing(self) -> None:
        """Test that context manager records duration."""
        store = get_metrics_store()
        store.clear()

        with record_duration("test.operation"):
            time.sleep(0.01)  # 10ms

        summary = get_metrics_summary()
        assert "test.operation" in summary["durations"]
        assert summary["durations"]["test.operation"]["count"] == 1
        # Should be at least 10ms
        assert summary["durations"]["test.operation"]["avg_seconds"] >= 0.01

    def test_context_manager_with_labels(self) -> None:
        """Test context manager with labels."""
        store = get_metrics_store()
        store.clear()

        with record_duration("test.operation", label="value"):
            pass

        summary = get_metrics_summary()
        assert "test.operation{label=value}" in summary["durations"]

    def test_context_manager_records_on_exception(self) -> None:
        """Test that duration is recorded even when exception occurs."""
        store = get_metrics_store()
        store.clear()

        with pytest.raises(ValueError):
            with record_duration("test.exception"):
                raise ValueError("test error")

        summary = get_metrics_summary()
        assert "test.exception" in summary["durations"]
        assert summary["durations"]["test.exception"]["count"] == 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_increment_counter_function(self) -> None:
        """Test increment_counter convenience function."""
        store = get_metrics_store()
        store.clear()

        increment_counter("test.convenience")
        increment_counter("test.convenience", 5)

        summary = get_metrics_summary()
        assert summary["counters"]["test.convenience"] == 6

    def test_get_metrics_store_singleton(self) -> None:
        """Test that get_metrics_store returns singleton."""
        store1 = get_metrics_store()
        store2 = get_metrics_store()
        assert store1 is store2
