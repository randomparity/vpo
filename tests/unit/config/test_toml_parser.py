"""Tests for TOML parsing module."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from video_policy_orchestrator.config.toml_parser import (
    BasicTomlParser,
    load_toml_file,
    parse_toml,
)


class TestBasicTomlParser:
    """Tests for BasicTomlParser fallback parser."""

    def test_parses_empty_content(self) -> None:
        """Should return empty dict for empty content."""
        parser = BasicTomlParser()
        assert parser.parse("") == {}

    def test_parses_comments_only(self) -> None:
        """Should return empty dict for content with only comments."""
        parser = BasicTomlParser()
        content = """
        # This is a comment
        # Another comment
        """
        assert parser.parse(content) == {}

    def test_parses_section_header(self) -> None:
        """Should parse [section] headers into nested dicts."""
        parser = BasicTomlParser()
        content = """
        [server]
        port = 8080
        """
        result = parser.parse(content)
        assert result == {"server": {"port": 8080}}

    def test_parses_nested_section(self) -> None:
        """Should parse [section.subsection] into nested dicts."""
        parser = BasicTomlParser()
        content = """
        [tools.detection]
        cache_ttl_hours = 24
        """
        result = parser.parse(content)
        assert result == {"tools": {"detection": {"cache_ttl_hours": 24}}}

    def test_parses_double_quoted_string(self) -> None:
        """Should parse double-quoted strings."""
        parser = BasicTomlParser()
        content = 'name = "hello world"'
        result = parser.parse(content)
        assert result == {"name": "hello world"}

    def test_parses_single_quoted_string(self) -> None:
        """Should parse single-quoted strings."""
        parser = BasicTomlParser()
        content = "name = 'hello world'"
        result = parser.parse(content)
        assert result == {"name": "hello world"}

    def test_parses_unquoted_string(self) -> None:
        """Should parse unquoted values as strings."""
        parser = BasicTomlParser()
        content = "path = /usr/bin/ffmpeg"
        result = parser.parse(content)
        assert result == {"path": "/usr/bin/ffmpeg"}

    def test_parses_boolean_true(self) -> None:
        """Should parse 'true' as boolean True."""
        parser = BasicTomlParser()
        content = "enabled = true"
        result = parser.parse(content)
        assert result == {"enabled": True}
        assert isinstance(result["enabled"], bool)

    def test_parses_boolean_true_case_insensitive(self) -> None:
        """Should parse 'True' and 'TRUE' as boolean True."""
        parser = BasicTomlParser()
        assert parser.parse("a = True") == {"a": True}
        assert parser.parse("a = TRUE") == {"a": True}

    def test_parses_boolean_false(self) -> None:
        """Should parse 'false' as boolean False."""
        parser = BasicTomlParser()
        content = "enabled = false"
        result = parser.parse(content)
        assert result == {"enabled": False}
        assert isinstance(result["enabled"], bool)

    def test_parses_boolean_false_case_insensitive(self) -> None:
        """Should parse 'False' and 'FALSE' as boolean False."""
        parser = BasicTomlParser()
        assert parser.parse("a = False") == {"a": False}
        assert parser.parse("a = FALSE") == {"a": False}

    def test_parses_integer(self) -> None:
        """Should parse integers."""
        parser = BasicTomlParser()
        content = "port = 8080"
        result = parser.parse(content)
        assert result == {"port": 8080}
        assert isinstance(result["port"], int)

    def test_parses_negative_integer(self) -> None:
        """Should parse negative integers."""
        parser = BasicTomlParser()
        content = "offset = -10"
        result = parser.parse(content)
        assert result == {"offset": -10}
        assert isinstance(result["offset"], int)

    def test_parses_float(self) -> None:
        """Should parse floats."""
        parser = BasicTomlParser()
        content = "ratio = 3.14"
        result = parser.parse(content)
        assert result["ratio"] == pytest.approx(3.14)
        assert isinstance(result["ratio"], float)

    def test_ignores_inline_comments(self) -> None:
        """Should strip inline comments from values."""
        parser = BasicTomlParser()
        content = "port = 8080 # default port"
        result = parser.parse(content)
        assert result == {"port": 8080}

    def test_skips_empty_lines(self) -> None:
        """Should skip empty lines."""
        parser = BasicTomlParser()
        content = """
        [server]

        port = 8080

        host = "localhost"
        """
        result = parser.parse(content)
        assert result == {"server": {"port": 8080, "host": "localhost"}}

    def test_handles_whitespace_around_equals(self) -> None:
        """Should handle whitespace around equals sign."""
        parser = BasicTomlParser()
        content = "port=8080"
        result = parser.parse(content)
        assert result == {"port": 8080}

        content = "port   =   8080"
        result = parser.parse(content)
        assert result == {"port": 8080}

    def test_top_level_keys_without_section(self) -> None:
        """Should handle keys at top level without section."""
        parser = BasicTomlParser()
        content = """
        name = "test"
        version = 1
        """
        result = parser.parse(content)
        assert result == {"name": "test", "version": 1}

    def test_multiple_sections(self) -> None:
        """Should handle multiple sections."""
        parser = BasicTomlParser()
        content = """
        [server]
        port = 8080

        [database]
        host = "localhost"
        """
        result = parser.parse(content)
        assert result == {
            "server": {"port": 8080},
            "database": {"host": "localhost"},
        }


class TestBasicTomlParserLimitations:
    """Tests documenting BasicTomlParser limitations."""

    def test_does_not_handle_arrays(self) -> None:
        """BasicTomlParser cannot parse arrays (documented limitation)."""
        parser = BasicTomlParser()
        content = "ports = [80, 443, 8080]"
        result = parser.parse(content)
        # Returns the raw string, not a list
        assert result["ports"] == "[80, 443, 8080]"
        assert not isinstance(result["ports"], list)

    def test_does_not_handle_inline_tables(self) -> None:
        """BasicTomlParser cannot parse inline tables (documented limitation)."""
        parser = BasicTomlParser()
        content = 'server = {host = "localhost", port = 8080}'
        result = parser.parse(content)
        # Returns the raw string, not a dict
        assert isinstance(result["server"], str)

    def test_does_not_handle_multiline_strings(self) -> None:
        """BasicTomlParser cannot parse multiline strings (documented limitation)."""
        parser = BasicTomlParser()
        # Triple-quoted strings are not properly handled
        content = '''description = """
        This is a
        multiline string
        """'''
        result = parser.parse(content)
        # Won't parse correctly
        assert "description" in result

    def test_does_not_handle_escape_sequences(self) -> None:
        """BasicTomlParser doesn't process escape sequences (documented limitation)."""
        parser = BasicTomlParser()
        content = r'path = "C:\\Users\\test"'
        result = parser.parse(content)
        # Returns string with backslashes intact (no escape processing)
        assert result["path"] == r"C:\\Users\\test"


class TestParseToml:
    """Tests for parse_toml function."""

    def test_parses_valid_toml(self) -> None:
        """Should parse valid TOML content."""
        content = """
        [server]
        port = 8080
        host = "localhost"
        enabled = true
        """
        result = parse_toml(content)
        assert result == {
            "server": {
                "port": 8080,
                "host": "localhost",
                "enabled": True,
            }
        }

    def test_parses_nested_sections(self) -> None:
        """Should parse nested section headers."""
        content = """
        [tools.detection]
        cache_ttl_hours = 24
        auto_detect_on_startup = true
        """
        result = parse_toml(content)
        assert result == {
            "tools": {
                "detection": {
                    "cache_ttl_hours": 24,
                    "auto_detect_on_startup": True,
                }
            }
        }

    def test_handles_empty_content(self) -> None:
        """Should return empty dict for empty content."""
        assert parse_toml("") == {}

    def test_handles_complex_config(self) -> None:
        """Should parse a complex config file."""
        content = """
        # VPO Configuration

        [tools]
        ffmpeg = "/usr/bin/ffmpeg"
        ffprobe = "/usr/bin/ffprobe"

        [tools.detection]
        cache_ttl_hours = 24

        [server]
        bind = "127.0.0.1"
        port = 8321
        shutdown_timeout = 30.0

        [behavior]
        warn_on_missing_features = true
        show_upgrade_suggestions = false
        """
        result = parse_toml(content)
        assert result["tools"]["ffmpeg"] == "/usr/bin/ffmpeg"
        assert result["tools"]["detection"]["cache_ttl_hours"] == 24
        assert result["server"]["port"] == 8321
        assert result["server"]["shutdown_timeout"] == pytest.approx(30.0)
        assert result["behavior"]["warn_on_missing_features"] is True
        assert result["behavior"]["show_upgrade_suggestions"] is False


class TestLoadTomlFile:
    """Tests for load_toml_file function."""

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path: Path) -> None:
        """Should return empty dict when file doesn't exist."""
        result = load_toml_file(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_loads_valid_toml_file(self, tmp_path: Path) -> None:
        """Should load and parse a valid TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 8080
        """)
        result = load_toml_file(config_file)
        assert result == {"server": {"port": 8080}}

    def test_returns_empty_dict_and_logs_error_on_encoding_issue(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should return empty dict and log error on encoding issue."""
        config_file = tmp_path / "config.toml"
        # Write invalid content that might cause issues
        config_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        with caplog.at_level(logging.ERROR):
            result = load_toml_file(config_file)

        assert result == {}
        assert "has encoding issues" in caplog.text

    def test_logs_debug_when_file_not_found(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should log debug message when file not found."""
        with caplog.at_level(logging.DEBUG):
            load_toml_file(tmp_path / "missing.toml")
        assert "TOML file not found" in caplog.text

    def test_logs_debug_on_successful_load(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Should log debug message on successful load."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("key = 'value'")

        with caplog.at_level(logging.DEBUG):
            load_toml_file(config_file)
        assert "Loaded TOML config from" in caplog.text
