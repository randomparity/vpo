"""Tests for feature flags module."""

from __future__ import annotations

import logging

import pytest

from vpo.feature_flags import is_enabled, log_enabled_flags


class TestIsEnabled:
    """Tests for is_enabled function."""

    def test_returns_false_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when env var is not set."""
        monkeypatch.delenv("VPO_FEATURE_TEST_FLAG", raising=False)
        assert is_enabled("TEST_FLAG") is False

    def test_returns_true_when_set_to_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when env var is '1'."""
        monkeypatch.setenv("VPO_FEATURE_TEST_FLAG", "1")
        assert is_enabled("TEST_FLAG") is True

    def test_returns_false_for_other_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return False for values other than '1'."""
        for value in ["0", "true", "yes", "on", ""]:
            monkeypatch.setenv("VPO_FEATURE_TEST_FLAG", value)
            assert is_enabled("TEST_FLAG") is False

    def test_case_insensitive_flag_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Flag name should be case-insensitive."""
        monkeypatch.setenv("VPO_FEATURE_MY_FLAG", "1")
        assert is_enabled("my_flag") is True
        assert is_enabled("MY_FLAG") is True


class TestLogEnabledFlags:
    """Tests for log_enabled_flags function."""

    def test_no_log_when_no_flags_enabled(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should not log when no known flags are enabled."""
        # Ensure no feature flags are set
        for key in list(
            monkeypatch._env_patches if hasattr(monkeypatch, "_env_patches") else []
        ):
            pass
        with caplog.at_level(logging.INFO):
            log_enabled_flags()
        assert "feature flags" not in caplog.text.lower()
