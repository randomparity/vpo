"""Tests for config loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from vpo.config.env import EnvReader
from vpo.config.loader import (
    get_config,
    get_data_dir,
    get_default_config_path,
    load_config_file,
    validate_config,
)
from vpo.config.models import (
    MetadataPluginSettings,
    PluginConfig,
    PluginConnectionConfig,
    VPOConfig,
)
from vpo.config.toml_parser import TomlParseError


class TestGetDefaultConfigPath:
    """Tests for get_default_config_path function."""

    def test_returns_default_when_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return default path when VPO_CONFIG_PATH not set."""
        monkeypatch.delenv("VPO_CONFIG_PATH", raising=False)
        result = get_default_config_path()
        assert result == Path.home() / ".vpo" / "config.toml"

    def test_returns_env_path_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return env path when VPO_CONFIG_PATH is set."""
        monkeypatch.setenv("VPO_CONFIG_PATH", "/custom/config.toml")
        result = get_default_config_path()
        assert result == Path("/custom/config.toml")


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_default_when_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return default path when VPO_DATA_DIR not set."""
        monkeypatch.delenv("VPO_DATA_DIR", raising=False)
        result = get_data_dir()
        assert result == Path.home() / ".vpo"

    def test_returns_env_path_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return env path when VPO_DATA_DIR is set."""
        monkeypatch.setenv("VPO_DATA_DIR", "/custom/vpo")
        result = get_data_dir()
        assert result == Path("/custom/vpo")

    def test_expands_tilde(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Should expand tilde in path."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("VPO_DATA_DIR", "~/custom/vpo")
        result = get_data_dir()
        assert result == tmp_path / "custom" / "vpo"


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_returns_empty_dict_when_file_not_exists(self, tmp_path: Path) -> None:
        """Should return empty dict when file doesn't exist."""
        result = load_config_file(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_loads_valid_config_file(self, tmp_path: Path) -> None:
        """Should load and parse a valid config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 9000
        bind = "0.0.0.0"
        """)
        result = load_config_file(config_file)
        assert result["server"]["port"] == 9000
        assert result["server"]["bind"] == "0.0.0.0"


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_defaults_with_empty_config(self, tmp_path: Path) -> None:
        """Should return default values when no config sources provide values."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.server.port == 8321
        assert config.server.bind == "127.0.0.1"
        assert config.detection.cache_ttl_hours == 24
        assert config.jobs.retention_days == 30

    def test_loads_from_config_file(self, tmp_path: Path) -> None:
        """Should load configuration from file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 9000
        bind = "0.0.0.0"

        [tools.detection]
        cache_ttl_hours = 48
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.server.port == 9000
        assert config.server.bind == "0.0.0.0"
        assert config.detection.cache_ttl_hours == 48

    def test_env_overrides_file(self, tmp_path: Path) -> None:
        """Environment variables should override config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [server]
        port = 8000

        [tools.detection]
        cache_ttl_hours = 24
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(
                env={
                    "VPO_SERVER_PORT": "9000",
                    "VPO_CACHE_TTL_HOURS": "48",
                }
            ),
        )

        # Env overrides file
        assert config.server.port == 9000
        assert config.detection.cache_ttl_hours == 48

    def test_cli_overrides_env_and_file(self, tmp_path: Path) -> None:
        """CLI arguments should override env and file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [tools]
        ffmpeg = "/file/ffmpeg"
        """)

        # Create temp files for paths
        env_ffmpeg = tmp_path / "env_ffmpeg"
        env_ffmpeg.touch()
        cli_ffmpeg = tmp_path / "cli_ffmpeg"
        cli_ffmpeg.touch()

        config = get_config(
            config_path=config_file,
            ffmpeg_path=cli_ffmpeg,
            env_reader=EnvReader(env={"VPO_FFMPEG_PATH": str(env_ffmpeg)}),
        )

        # CLI wins
        assert config.tools.ffmpeg == cli_ffmpeg

    def test_database_path_from_cli(self, tmp_path: Path) -> None:
        """Should accept database path from CLI."""
        db_path = tmp_path / "library.db"
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            database_path=db_path,
            env_reader=EnvReader(env={}),
        )

        assert config.database_path == db_path

    def test_plugin_dirs_from_file(self, tmp_path: Path) -> None:
        """Should load plugin directories from config file."""
        plugin_dir = tmp_path / "my_plugins"
        plugin_dir.mkdir()

        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
        [plugins]
        plugin_dirs = ["{plugin_dir}"]
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert plugin_dir in config.plugins.plugin_dirs

    def test_plugin_dirs_env_overrides_file(self, tmp_path: Path) -> None:
        """Plugin dirs from env should override file (not merge)."""
        file_dir = tmp_path / "file_plugins"
        file_dir.mkdir()
        env_dir = tmp_path / "env_plugins"
        env_dir.mkdir()

        config_file = tmp_path / "config.toml"
        config_file.write_text(f"""
        [plugins]
        plugin_dirs = ["{file_dir}"]
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={"VPO_PLUGIN_DIRS": str(env_dir)}),
        )

        # Env takes precedence, file dir is not included
        assert env_dir in config.plugins.plugin_dirs
        assert file_dir not in config.plugins.plugin_dirs

    def test_default_plugins_dir_always_included(self, tmp_path: Path) -> None:
        """Default plugins dir should always be in the list."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        # Default dir (from DEFAULT_PLUGINS_DIR constant)
        default_plugins = Path.home() / ".vpo" / "plugins"
        assert default_plugins in config.plugins.plugin_dirs

    def test_server_auth_token(self, tmp_path: Path) -> None:
        """Should load auth token from env."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={"VPO_AUTH_TOKEN": "secret-token-16ch"}),
        )

        assert config.server.auth_token == "secret-token-16ch"

    def test_jobs_config(self, tmp_path: Path) -> None:
        """Should load jobs configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [jobs]
        retention_days = 60
        auto_purge = false
        log_compression_days = 14
        log_deletion_days = 180
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.jobs.retention_days == 60
        assert config.jobs.auto_purge is False
        assert config.jobs.log_compression_days == 14
        assert config.jobs.log_deletion_days == 180

    def test_worker_config(self, tmp_path: Path) -> None:
        """Should load worker configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [worker]
        max_files = 100
        max_duration = 3600
        end_by = "23:00"
        cpu_cores = 4
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.worker.max_files == 100
        assert config.worker.max_duration == 3600
        assert config.worker.end_by == "23:00"
        assert config.worker.cpu_cores == 4

    def test_language_config(self, tmp_path: Path) -> None:
        """Should load language configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [language]
        standard = "639-1"
        warn_on_conversion = false
        """)

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
        )

        assert config.language.standard == "639-1"
        assert config.language.warn_on_conversion is False


class TestConfigCache:
    """Tests for config file caching behavior."""

    def test_cache_automatically_reloads_on_file_change(self, tmp_path: Path) -> None:
        """Cache should automatically reload when file mtime changes."""
        import os

        from vpo.config.loader import clear_config_cache

        # Clear cache first to ensure clean state
        clear_config_cache()

        # Create a config file
        config_file = tmp_path / "config.toml"
        config_file.write_text("[server]\nport = 9000")

        # Load it (should cache)
        result1 = load_config_file(config_file)
        assert result1["server"]["port"] == 9000

        # Modify the file and explicitly bump mtime (filesystem mtime may have
        # 1-second granularity, so writes within the same second won't trigger
        # cache invalidation without this)
        config_file.write_text("[server]\nport = 8000")
        current_mtime = config_file.stat().st_mtime
        os.utime(config_file, (current_mtime + 1, current_mtime + 1))

        # Load again (should detect mtime change and reload)
        result2 = load_config_file(config_file)
        assert result2["server"]["port"] == 8000  # Auto-reloaded

    def test_clear_config_cache_clears_cache(self, tmp_path: Path) -> None:
        """clear_config_cache should explicitly clear the cache."""
        from vpo.config.loader import clear_config_cache

        # Clear cache first to ensure clean state
        clear_config_cache()

        # Create a config file
        config_file = tmp_path / "config.toml"
        config_file.write_text("[server]\nport = 9000")

        # Load it (should cache)
        result1 = load_config_file(config_file)
        assert result1["server"]["port"] == 9000

        # Clear cache explicitly
        clear_config_cache()

        # Load again (should reload since cache was cleared)
        result2 = load_config_file(config_file)
        assert result2["server"]["port"] == 9000  # Same value, but reloaded

    def test_load_config_file_caches_result(self, tmp_path: Path) -> None:
        """load_config_file should cache results and return same dict."""
        from vpo.config.loader import clear_config_cache

        # Clear cache first to ensure clean state
        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("[server]\nport = 9000")

        # Load twice
        result1 = load_config_file(config_file)
        result2 = load_config_file(config_file)

        # Should be the exact same dict object (cached)
        assert result1 is result2

    def test_config_cache_thread_safety(self, tmp_path: Path) -> None:
        """Config cache should be thread-safe for concurrent access."""
        from concurrent.futures import ThreadPoolExecutor

        from vpo.config.loader import clear_config_cache

        # Clear cache first to ensure clean state
        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("[server]\nport = 9000")

        results: list[dict] = []

        def load_config() -> dict:
            return load_config_file(config_file)

        # Spawn many threads to hit the cache concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(load_config) for _ in range(100)]
            for f in futures:
                results.append(f.result())

        # All results should be the exact same cached dict object
        first = results[0]
        assert all(r is first for r in results)


class TestGetTempDirectory:
    """Tests for get_temp_directory function."""

    def test_env_takes_precedence_over_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPO_TEMP_DIR env var should take precedence over config."""
        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory,
        )

        # Clear cache to ensure clean state
        clear_config_cache()

        # Create env temp dir
        env_temp = tmp_path / "env_temp"
        env_temp.mkdir()

        # Create config temp dir
        config_temp = tmp_path / "config_temp"
        config_temp.mkdir()

        # Set up config with temp_directory (under [jobs] section)
        config_file = tmp_path / "config.toml"
        config_file.write_text(f'[jobs]\ntemp_directory = "{config_temp}"')
        monkeypatch.setenv("VPO_CONFIG_PATH", str(config_file))

        # Set env var (should take precedence)
        monkeypatch.setenv("VPO_TEMP_DIR", str(env_temp))

        result = get_temp_directory()
        assert result == env_temp

    def test_config_takes_precedence_over_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config temp_directory should take precedence over system default."""
        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory,
        )

        # Clear cache to ensure clean state
        clear_config_cache()

        # Unset env var
        monkeypatch.delenv("VPO_TEMP_DIR", raising=False)

        # Create config temp dir
        config_temp = tmp_path / "config_temp"
        config_temp.mkdir()

        # Set up config with temp_directory (under [jobs] section)
        config_file = tmp_path / "config.toml"
        config_file.write_text(f'[jobs]\ntemp_directory = "{config_temp}"')
        monkeypatch.setenv("VPO_CONFIG_PATH", str(config_file))

        result = get_temp_directory()
        assert result == config_temp

    def test_invalid_env_path_logs_warning_and_falls_back(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Invalid VPO_TEMP_DIR should log warning and fall back."""
        import logging

        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory,
        )

        # Clear cache to ensure clean state
        clear_config_cache()

        # Set invalid env path (doesn't exist)
        invalid_path = tmp_path / "nonexistent_dir"
        monkeypatch.setenv("VPO_TEMP_DIR", str(invalid_path))

        # Set up empty config (no temp_directory)
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        monkeypatch.setenv("VPO_CONFIG_PATH", str(config_file))

        with caplog.at_level(logging.WARNING):
            result = get_temp_directory()

        # Should fall back to None (no config, no valid env)
        assert result is None

        # Should log a warning
        assert "VPO_TEMP_DIR" in caplog.text
        assert "not a valid directory" in caplog.text

    def test_default_returns_none_when_unconfigured(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should return None when no env var and no config temp_directory."""
        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory,
        )

        # Clear cache to ensure clean state
        clear_config_cache()

        # Unset env var
        monkeypatch.delenv("VPO_TEMP_DIR", raising=False)

        # Set up empty config (no temp_directory)
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        monkeypatch.setenv("VPO_CONFIG_PATH", str(config_file))

        result = get_temp_directory()
        assert result is None


class TestGetTempDirectoryForFile:
    """Tests for get_temp_directory_for_file function."""

    def test_returns_configured_dir_when_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns configured temp directory when available."""
        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory_for_file,
        )

        clear_config_cache()

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        monkeypatch.setenv("VPO_TEMP_DIR", str(temp_dir))

        source = tmp_path / "video.mkv"
        result = get_temp_directory_for_file(source)
        assert result == temp_dir

    def test_falls_back_to_source_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls back to source file's parent when unconfigured."""
        from vpo.config.loader import (
            clear_config_cache,
            get_temp_directory_for_file,
        )

        clear_config_cache()

        monkeypatch.delenv("VPO_TEMP_DIR", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        monkeypatch.setenv("VPO_CONFIG_PATH", str(config_file))

        source = tmp_path / "videos" / "movie.mkv"
        result = get_temp_directory_for_file(source)
        assert result == source.parent


class TestStrictParsing:
    """Tests for strict TOML parsing mode."""

    def test_strict_raises_on_malformed_toml(self, tmp_path: Path) -> None:
        """strict=True should raise TomlParseError on malformed TOML."""
        from vpo.config.loader import clear_config_cache

        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not [valid toml\n= broken")

        with pytest.raises(TomlParseError):
            load_config_file(config_file, strict=True)

    def test_non_strict_returns_empty_on_malformed_toml(self, tmp_path: Path) -> None:
        """strict=False should return empty dict on malformed TOML."""
        from vpo.config.loader import clear_config_cache

        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not [valid toml\n= broken")

        result = load_config_file(config_file, strict=False)
        assert result == {}

    def test_get_config_strict_raises_on_malformed_toml(self, tmp_path: Path) -> None:
        """get_config(strict=True) should raise on malformed config."""
        from vpo.config.loader import clear_config_cache

        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not [valid toml\n= broken")

        with pytest.raises(TomlParseError):
            get_config(
                config_path=config_file,
                env_reader=EnvReader(env={}),
                strict=True,
            )

    def test_get_config_non_strict_returns_defaults_on_malformed(
        self, tmp_path: Path
    ) -> None:
        """get_config(strict=False) should return defaults on malformed config."""
        from vpo.config.loader import clear_config_cache

        clear_config_cache()

        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not [valid toml\n= broken")

        config = get_config(
            config_path=config_file,
            env_reader=EnvReader(env={}),
            strict=False,
        )
        # Should get defaults
        assert config.server.port == 8321


class TestValidateConfig:
    """Tests for validate_config function."""

    # Test API key for PluginConnectionConfig
    _TEST_KEY = "test-api-key-00000"  # pragma: allowlist secret

    def test_valid_config_returns_empty(self) -> None:
        """Valid config should return empty error list."""
        config = VPOConfig()
        assert validate_config(config) == []

    def test_radarr_enabled_without_url(self) -> None:
        """Should error when radarr is enabled but url is empty."""
        radarr = PluginConnectionConfig(
            url="http://localhost:7878",
            api_key=self._TEST_KEY,
            enabled=True,
        )
        config = VPOConfig(
            plugins=PluginConfig(metadata=MetadataPluginSettings(radarr=radarr))
        )
        errors = validate_config(config)
        # Should be valid since url IS set
        assert errors == []

    def test_nonexistent_plugin_dir_errors(self, tmp_path: Path) -> None:
        """Should error for non-existent plugin directories."""
        bad_dir = tmp_path / "does_not_exist"
        config = VPOConfig(plugins=PluginConfig(plugin_dirs=[bad_dir]))
        errors = validate_config(config)
        assert any("does not exist" in e for e in errors)

    def test_existing_plugin_dir_no_error(self, tmp_path: Path) -> None:
        """Should not error for existing plugin directories."""
        good_dir = tmp_path / "plugins"
        good_dir.mkdir()
        config = VPOConfig(plugins=PluginConfig(plugin_dirs=[good_dir]))
        errors = validate_config(config)
        assert errors == []
