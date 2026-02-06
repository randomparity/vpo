"""Tests for EnvReader class."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from vpo.config.env import EnvReader


class TestEnvReaderGetStr:
    """Tests for EnvReader.get_str method."""

    def test_returns_value_when_set(self) -> None:
        """Should return the value when environment variable is set."""
        reader = EnvReader(env={"MY_VAR": "hello"})
        assert reader.get_str("MY_VAR") == "hello"

    def test_returns_none_when_not_set(self) -> None:
        """Should return None when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_str("MY_VAR") is None

    def test_returns_default_when_not_set(self) -> None:
        """Should return default when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_str("MY_VAR", "default") == "default"

    def test_returns_value_over_default_when_set(self) -> None:
        """Should return value, not default, when variable is set."""
        reader = EnvReader(env={"MY_VAR": "actual"})
        assert reader.get_str("MY_VAR", "default") == "actual"

    def test_returns_empty_string_when_set_to_empty(self) -> None:
        """Should return empty string when variable is set to empty."""
        reader = EnvReader(env={"MY_VAR": ""})
        assert reader.get_str("MY_VAR", "default") == ""


class TestEnvReaderGetInt:
    """Tests for EnvReader.get_int method."""

    def test_returns_value_when_set(self) -> None:
        """Should parse and return integer when environment variable is set."""
        reader = EnvReader(env={"MY_VAR": "42"})
        assert reader.get_int("MY_VAR") == 42

    def test_returns_none_when_not_set(self) -> None:
        """Should return None when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_int("MY_VAR") is None

    def test_returns_default_when_not_set(self) -> None:
        """Should return default when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_int("MY_VAR", 100) == 100

    def test_parses_negative_integer(self) -> None:
        """Should parse negative integers correctly."""
        reader = EnvReader(env={"MY_VAR": "-5"})
        assert reader.get_int("MY_VAR") == -5

    def test_returns_default_and_warns_for_invalid(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should return default and log warning for invalid integer."""
        reader = EnvReader(env={"MY_VAR": "not_a_number"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_int("MY_VAR", 100)
        assert result == 100
        assert "Invalid integer value for MY_VAR: not_a_number" in caplog.text

    def test_returns_default_for_float_string(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should return default for float strings (not valid int)."""
        reader = EnvReader(env={"MY_VAR": "3.14"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_int("MY_VAR", 100)
        assert result == 100
        assert "Invalid integer value" in caplog.text

    def test_strict_raises_on_invalid(self) -> None:
        """strict=True should raise ValueError on invalid int."""
        reader = EnvReader(env={"MY_VAR": "not_a_number"})
        with pytest.raises(ValueError, match="Invalid integer value"):
            reader.get_int("MY_VAR", strict=True)

    def test_strict_false_preserves_default_behavior(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """strict=False should log warning and return default."""
        reader = EnvReader(env={"MY_VAR": "bad"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_int("MY_VAR", 42, strict=False)
        assert result == 42
        assert "Invalid integer value" in caplog.text


class TestEnvReaderGetFloat:
    """Tests for EnvReader.get_float method."""

    def test_returns_value_when_set(self) -> None:
        """Should parse and return float when environment variable is set."""
        reader = EnvReader(env={"MY_VAR": "3.14"})
        assert reader.get_float("MY_VAR") == pytest.approx(3.14)

    def test_returns_none_when_not_set(self) -> None:
        """Should return None when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_float("MY_VAR") is None

    def test_returns_default_when_not_set(self) -> None:
        """Should return default when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_float("MY_VAR", 2.5) == 2.5

    def test_parses_integer_as_float(self) -> None:
        """Should parse integer strings as floats."""
        reader = EnvReader(env={"MY_VAR": "42"})
        assert reader.get_float("MY_VAR") == 42.0

    def test_parses_negative_float(self) -> None:
        """Should parse negative floats correctly."""
        reader = EnvReader(env={"MY_VAR": "-2.5"})
        assert reader.get_float("MY_VAR") == pytest.approx(-2.5)

    def test_returns_default_and_warns_for_invalid(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should return default and log warning for invalid float."""
        reader = EnvReader(env={"MY_VAR": "not_a_number"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_float("MY_VAR", 1.0)
        assert result == 1.0
        assert "Invalid float value for MY_VAR: not_a_number" in caplog.text

    def test_rejects_nan_value(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should reject 'nan' string from environment."""
        reader = EnvReader(env={"MY_VAR": "nan"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_float("MY_VAR", 1.0)
        assert result == 1.0
        assert "NaN/infinity not allowed" in caplog.text

    def test_rejects_infinity_value(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should reject 'inf' string from environment."""
        reader = EnvReader(env={"MY_VAR": "inf"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_float("MY_VAR", 1.0)
        assert result == 1.0
        assert "NaN/infinity not allowed" in caplog.text

    def test_rejects_negative_infinity(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should reject '-inf' string from environment."""
        reader = EnvReader(env={"MY_VAR": "-inf"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_float("MY_VAR", 1.0)
        assert result == 1.0
        assert "NaN/infinity not allowed" in caplog.text

    def test_strict_raises_on_invalid(self) -> None:
        """strict=True should raise ValueError on invalid float."""
        reader = EnvReader(env={"MY_VAR": "not_a_number"})
        with pytest.raises(ValueError, match="Invalid float value"):
            reader.get_float("MY_VAR", strict=True)

    def test_strict_raises_on_nan(self) -> None:
        """strict=True should raise ValueError on NaN."""
        reader = EnvReader(env={"MY_VAR": "nan"})
        with pytest.raises(ValueError, match="NaN/infinity"):
            reader.get_float("MY_VAR", strict=True)

    def test_strict_false_preserves_default_behavior(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """strict=False should log warning and return default."""
        reader = EnvReader(env={"MY_VAR": "bad"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_float("MY_VAR", 1.0, strict=False)
        assert result == 1.0
        assert "Invalid float value" in caplog.text


class TestEnvReaderGetBool:
    """Tests for EnvReader.get_bool method."""

    def test_returns_none_when_not_set(self) -> None:
        """Should return None when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_bool("MY_VAR") is None

    def test_returns_default_when_not_set(self) -> None:
        """Should return default when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_bool("MY_VAR", True) is True
        assert reader.get_bool("MY_VAR", False) is False

    @pytest.mark.parametrize(
        "value", ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]
    )
    def test_recognizes_true_values(self, value: str) -> None:
        """Should recognize various true values (case-insensitive)."""
        reader = EnvReader(env={"MY_VAR": value})
        assert reader.get_bool("MY_VAR") is True

    @pytest.mark.parametrize(
        "value", ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]
    )
    def test_recognizes_false_values(self, value: str) -> None:
        """Should treat non-true values as false."""
        reader = EnvReader(env={"MY_VAR": value})
        assert reader.get_bool("MY_VAR") is False

    def test_empty_string_returns_default(self) -> None:
        """Empty string should be treated as unset (return default)."""
        reader = EnvReader(env={"MY_VAR": ""})
        assert reader.get_bool("MY_VAR") is None
        assert reader.get_bool("MY_VAR", True) is True
        assert reader.get_bool("MY_VAR", False) is False

    def test_unknown_string_is_false(self) -> None:
        """Should treat unknown strings as false."""
        reader = EnvReader(env={"MY_VAR": "maybe"})
        assert reader.get_bool("MY_VAR") is False


class TestEnvReaderGetPath:
    """Tests for EnvReader.get_path method."""

    def test_returns_none_when_not_set(self) -> None:
        """Should return None when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_path("MY_VAR") is None

    def test_returns_default_when_not_set(self, tmp_path: Path) -> None:
        """Should return default when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_path("MY_VAR", default=tmp_path) == tmp_path

    def test_returns_path_when_exists(self, tmp_path: Path) -> None:
        """Should return Path when file/directory exists."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        reader = EnvReader(env={"MY_VAR": str(test_file)})
        assert reader.get_path("MY_VAR") == test_file

    def test_returns_default_and_warns_when_not_exists(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should return default and log warning for non-existent path."""
        reader = EnvReader(env={"MY_VAR": "/nonexistent/path"})
        with caplog.at_level(logging.WARNING):
            result = reader.get_path("MY_VAR", default=Path("/default"))
        assert result == Path("/default")
        assert "Environment variable MY_VAR points to non-existent path" in caplog.text

    def test_returns_path_when_must_exist_false(self) -> None:
        """Should return path without checking existence when must_exist=False."""
        reader = EnvReader(env={"MY_VAR": "/nonexistent/path"})
        result = reader.get_path("MY_VAR", must_exist=False)
        assert result == Path("/nonexistent/path")

    def test_expands_tilde(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should expand tilde in paths."""
        # Set HOME to tmp_path so ~/ expands to it
        monkeypatch.setenv("HOME", str(tmp_path))
        test_file = tmp_path / "test.txt"
        test_file.touch()

        reader = EnvReader(env={"MY_VAR": "~/test.txt"})
        result = reader.get_path("MY_VAR")
        assert result == test_file


class TestEnvReaderGetPathList:
    """Tests for EnvReader.get_path_list method."""

    def test_returns_empty_list_when_not_set(self) -> None:
        """Should return empty list when environment variable is not set."""
        reader = EnvReader(env={})
        assert reader.get_path_list("MY_VAR") == []

    def test_returns_default_when_not_set(self) -> None:
        """Should return default when environment variable is not set."""
        default = [Path("/a"), Path("/b")]
        reader = EnvReader(env={})
        assert reader.get_path_list("MY_VAR", default=default) == default

    def test_parses_single_path(self) -> None:
        """Should parse a single path."""
        reader = EnvReader(env={"MY_VAR": "/path/to/dir"})
        result = reader.get_path_list("MY_VAR")
        assert result == [Path("/path/to/dir")]

    def test_parses_colon_separated_paths(self) -> None:
        """Should parse colon-separated paths."""
        reader = EnvReader(env={"MY_VAR": "/a:/b:/c"})
        result = reader.get_path_list("MY_VAR")
        assert result == [Path("/a"), Path("/b"), Path("/c")]

    def test_uses_custom_separator(self) -> None:
        """Should use custom separator when provided."""
        reader = EnvReader(env={"MY_VAR": "/a;/b;/c"})
        result = reader.get_path_list("MY_VAR", separator=";")
        assert result == [Path("/a"), Path("/b"), Path("/c")]

    def test_filters_empty_paths(self) -> None:
        """Should filter out empty paths from the list."""
        reader = EnvReader(env={"MY_VAR": "/a::/b:"})
        result = reader.get_path_list("MY_VAR")
        assert result == [Path("/a"), Path("/b")]

    def test_strips_whitespace(self) -> None:
        """Should strip whitespace from paths."""
        reader = EnvReader(env={"MY_VAR": " /a : /b : /c "})
        result = reader.get_path_list("MY_VAR")
        assert result == [Path("/a"), Path("/b"), Path("/c")]

    def test_expands_tilde_in_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should expand tilde in all paths."""
        monkeypatch.setenv("HOME", str(tmp_path))
        reader = EnvReader(env={"MY_VAR": "~/a:~/b"})
        result = reader.get_path_list("MY_VAR")
        assert result == [tmp_path / "a", tmp_path / "b"]


class TestEnvReaderWithOsEnviron:
    """Tests for EnvReader with real os.environ."""

    def test_default_reads_from_os_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should read from os.environ when no env mapping provided."""
        monkeypatch.setenv("TEST_VAR_XYZ", "from_os")
        reader = EnvReader()  # No env param, uses os.environ
        assert reader.get_str("TEST_VAR_XYZ") == "from_os"

    def test_injected_env_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Injected env should be used instead of os.environ."""
        monkeypatch.setenv("TEST_VAR_XYZ", "from_os")
        reader = EnvReader(env={"TEST_VAR_XYZ": "from_injected"})
        assert reader.get_str("TEST_VAR_XYZ") == "from_injected"
