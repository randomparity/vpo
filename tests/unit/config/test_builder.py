"""Tests for ConfigBuilder module."""

from __future__ import annotations

from pathlib import Path

import pytest

from vpo.config.builder import (
    ConfigBuilder,
    ConfigSource,
    source_from_env,
    source_from_file,
)
from vpo.config.env import EnvReader


class TestConfigSource:
    """Tests for ConfigSource dataclass."""

    def test_all_fields_default_to_none(self) -> None:
        """All fields should default to None."""
        source = ConfigSource()
        assert source.ffmpeg_path is None
        assert source.server_port is None
        assert source.warn_on_missing_features is None

    def test_fields_can_be_set(self) -> None:
        """Fields can be set via constructor."""
        source = ConfigSource(
            ffmpeg_path=Path("/usr/bin/ffmpeg"),
            server_port=8080,
            warn_on_missing_features=True,
        )
        assert source.ffmpeg_path == Path("/usr/bin/ffmpeg")
        assert source.server_port == 8080
        assert source.warn_on_missing_features is True


class TestConfigBuilder:
    """Tests for ConfigBuilder class."""

    def test_build_with_no_sources_uses_defaults(self, tmp_path: Path) -> None:
        """Should use default values when no sources applied."""
        builder = ConfigBuilder()
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        # Check defaults
        assert config.tools.ffmpeg is None
        assert config.detection.cache_ttl_hours == 24
        assert config.behavior.warn_on_missing_features is True
        assert config.server.port == 8321
        assert config.server.bind == "127.0.0.1"
        assert config.language.standard == "639-2/B"
        assert config.jobs.retention_days == 30
        assert config.logging.level == "info"

    def test_apply_overrides_defaults(self, tmp_path: Path) -> None:
        """Applied source should override defaults."""
        builder = ConfigBuilder()
        source = ConfigSource(
            server_port=9000,
            cache_ttl_hours=48,
        )
        builder.apply(source)
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.server.port == 9000
        assert config.detection.cache_ttl_hours == 48
        # Other defaults still apply
        assert config.server.bind == "127.0.0.1"

    def test_none_values_do_not_override(self, tmp_path: Path) -> None:
        """None values in source should not override existing values."""
        builder = ConfigBuilder()

        # First source sets port
        builder.apply(ConfigSource(server_port=9000))

        # Second source has None for port (should not override)
        builder.apply(ConfigSource(server_port=None, server_bind="0.0.0.0"))

        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        # Port preserved from first source
        assert config.server.port == 9000
        # Bind updated by second source
        assert config.server.bind == "0.0.0.0"

    def test_later_sources_override_earlier(self, tmp_path: Path) -> None:
        """Later applied sources should override earlier ones."""
        builder = ConfigBuilder()

        builder.apply(ConfigSource(server_port=8000))
        builder.apply(ConfigSource(server_port=9000))

        config = builder.build(default_plugins_dir=tmp_path / "plugins")
        assert config.server.port == 9000

    def test_tool_paths_configured(self, tmp_path: Path) -> None:
        """Should configure tool paths correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                ffmpeg_path=Path("/usr/bin/ffmpeg"),
                ffprobe_path=Path("/usr/bin/ffprobe"),
                mkvmerge_path=Path("/usr/bin/mkvmerge"),
                mkvpropedit_path=Path("/usr/bin/mkvpropedit"),
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.tools.ffmpeg == Path("/usr/bin/ffmpeg")
        assert config.tools.ffprobe == Path("/usr/bin/ffprobe")
        assert config.tools.mkvmerge == Path("/usr/bin/mkvmerge")
        assert config.tools.mkvpropedit == Path("/usr/bin/mkvpropedit")

    def test_database_path_configured(self, tmp_path: Path) -> None:
        """Should configure database path correctly."""
        db_path = tmp_path / "library.db"
        builder = ConfigBuilder()
        builder.apply(ConfigSource(database_path=db_path))
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.database_path == db_path

    def test_detection_config(self, tmp_path: Path) -> None:
        """Should configure detection settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                cache_ttl_hours=12,
                auto_detect_on_startup=False,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.detection.cache_ttl_hours == 12
        assert config.detection.auto_detect_on_startup is False

    def test_behavior_config(self, tmp_path: Path) -> None:
        """Should configure behavior settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                warn_on_missing_features=False,
                show_upgrade_suggestions=False,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.behavior.warn_on_missing_features is False
        assert config.behavior.show_upgrade_suggestions is False

    def test_jobs_config(self, tmp_path: Path) -> None:
        """Should configure jobs settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                jobs_retention_days=60,
                jobs_auto_purge=False,
                jobs_temp_directory=tmp_path / "temp",
                jobs_backup_original=False,
                jobs_log_compression_days=14,
                jobs_log_deletion_days=180,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.jobs.retention_days == 60
        assert config.jobs.auto_purge is False
        assert config.jobs.temp_directory == tmp_path / "temp"
        assert config.jobs.backup_original is False
        assert config.jobs.log_compression_days == 14
        assert config.jobs.log_deletion_days == 180

    def test_worker_config(self, tmp_path: Path) -> None:
        """Should configure worker settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                worker_max_files=100,
                worker_max_duration=3600,
                worker_end_by="23:00",
                worker_cpu_cores=4,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.worker.max_files == 100
        assert config.worker.max_duration == 3600
        assert config.worker.end_by == "23:00"
        assert config.worker.cpu_cores == 4

    def test_worker_zero_values_become_none(self, tmp_path: Path) -> None:
        """Worker limits of 0 should become None (no limit)."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                worker_max_files=0,
                worker_max_duration=0,
                worker_cpu_cores=0,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.worker.max_files is None
        assert config.worker.max_duration is None
        assert config.worker.cpu_cores is None

    def test_server_config(self, tmp_path: Path) -> None:
        """Should configure server settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                server_bind="0.0.0.0",
                server_port=8080,
                server_shutdown_timeout=60.0,
                server_auth_token="secret",
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.server.bind == "0.0.0.0"
        assert config.server.port == 8080
        assert config.server.shutdown_timeout == 60.0
        assert config.server.auth_token == "secret"

    def test_language_config(self, tmp_path: Path) -> None:
        """Should configure language settings correctly."""
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                language_standard="639-1",
                language_warn_on_conversion=False,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.language.standard == "639-1"
        assert config.language.warn_on_conversion is False

    def test_logging_config(self, tmp_path: Path) -> None:
        """Should configure logging settings correctly."""
        log_file = tmp_path / "vpo.log"
        builder = ConfigBuilder()
        builder.apply(
            ConfigSource(
                logging_level="debug",
                logging_file=log_file,
                logging_format="json",
                logging_include_stderr=False,
                logging_max_bytes=5_000_000,
                logging_backup_count=3,
            )
        )
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.logging.level == "debug"
        assert config.logging.file == log_file
        assert config.logging.format == "json"
        assert config.logging.include_stderr is False
        assert config.logging.max_bytes == 5_000_000
        assert config.logging.backup_count == 3


class TestConfigBuilderPluginDirs:
    """Tests for plugin directory handling in ConfigBuilder."""

    def test_default_plugins_dir_always_included(self, tmp_path: Path) -> None:
        """Default plugins dir should always be in the final list."""
        default_dir = tmp_path / "default_plugins"
        builder = ConfigBuilder()
        config = builder.build(default_plugins_dir=default_dir)

        assert default_dir in config.plugins.plugin_dirs

    def test_plugin_dirs_from_file(self, tmp_path: Path) -> None:
        """Should include plugin dirs from config file."""
        default_dir = tmp_path / "default"
        file_dir = tmp_path / "from_file"

        builder = ConfigBuilder()
        builder.set_plugin_dirs_from_file([file_dir])
        config = builder.build(default_plugins_dir=default_dir)

        assert file_dir in config.plugins.plugin_dirs
        assert default_dir in config.plugins.plugin_dirs

    def test_plugin_dirs_env_overrides_file(self, tmp_path: Path) -> None:
        """Plugin dirs from env should override file (not merge)."""
        default_dir = tmp_path / "default"
        file_dir = tmp_path / "from_file"
        env_dir = tmp_path / "from_env"

        builder = ConfigBuilder()
        builder.set_plugin_dirs_from_file([file_dir])
        builder.set_plugin_dirs_from_env([env_dir])
        config = builder.build(default_plugins_dir=default_dir)

        # Env takes precedence, file is not included
        assert env_dir in config.plugins.plugin_dirs
        assert file_dir not in config.plugins.plugin_dirs
        assert default_dir in config.plugins.plugin_dirs

    def test_default_not_duplicated(self, tmp_path: Path) -> None:
        """Default plugins dir should not be duplicated."""
        default_dir = tmp_path / "default"

        builder = ConfigBuilder()
        builder.set_plugin_dirs_from_file([default_dir])  # Same as default
        config = builder.build(default_plugins_dir=default_dir)

        # Should only appear once
        assert config.plugins.plugin_dirs.count(default_dir) == 1


class TestSourceFromFile:
    """Tests for source_from_file function."""

    def test_empty_config(self) -> None:
        """Should handle empty config dict."""
        source = source_from_file({})
        assert source.ffmpeg_path is None
        assert source.server_port is None

    def test_parses_tool_paths(self) -> None:
        """Should parse tool paths from config."""
        config = {
            "tools": {
                "ffmpeg": "/usr/bin/ffmpeg",
                "ffprobe": "/usr/bin/ffprobe",
            }
        }
        source = source_from_file(config)
        assert source.ffmpeg_path == Path("/usr/bin/ffmpeg")
        assert source.ffprobe_path == Path("/usr/bin/ffprobe")

    def test_parses_nested_detection_config(self) -> None:
        """Should parse detection config from tools.detection."""
        config = {
            "tools": {
                "detection": {
                    "cache_ttl_hours": 12,
                    "auto_detect_on_startup": False,
                }
            }
        }
        source = source_from_file(config)
        assert source.cache_ttl_hours == 12
        assert source.auto_detect_on_startup is False

    def test_parses_server_config(self) -> None:
        """Should parse server config."""
        config = {
            "server": {
                "bind": "0.0.0.0",
                "port": 8080,
                "shutdown_timeout": 60.0,
                "auth_token": "secret",
            }
        }
        source = source_from_file(config)
        assert source.server_bind == "0.0.0.0"
        assert source.server_port == 8080
        assert source.server_shutdown_timeout == 60.0
        assert source.server_auth_token == "secret"

    def test_parses_plugin_dirs(self) -> None:
        """Should parse plugin directories as list of Paths."""
        config = {
            "plugins": {
                "plugin_dirs": ["/path/to/plugins", "~/my_plugins"],
            }
        }
        source = source_from_file(config)
        assert source.plugin_dirs is not None
        assert len(source.plugin_dirs) == 2
        assert source.plugin_dirs[0] == Path("/path/to/plugins")
        # Tilde should be expanded
        assert "~" not in str(source.plugin_dirs[1])

    def test_parses_jobs_temp_directory(self) -> None:
        """Should parse jobs temp directory with tilde expansion."""
        config = {
            "jobs": {
                "temp_directory": "~/vpo_temp",
            }
        }
        source = source_from_file(config)
        assert source.jobs_temp_directory is not None
        assert "~" not in str(source.jobs_temp_directory)

    def test_parses_database_path(self) -> None:
        """Should parse database path."""
        config = {"database_path": "/var/lib/vpo/library.db"}
        source = source_from_file(config)
        assert source.database_path == Path("/var/lib/vpo/library.db")


class TestSourceFromEnv:
    """Tests for source_from_env function."""

    def test_empty_env(self) -> None:
        """Should handle empty environment."""
        reader = EnvReader(env={})
        source = source_from_env(reader)
        assert source.ffmpeg_path is None
        assert source.server_port is None

    def test_reads_tool_paths(self, tmp_path: Path) -> None:
        """Should read tool paths from environment."""
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.touch()

        reader = EnvReader(env={"VPO_FFMPEG_PATH": str(ffmpeg)})
        source = source_from_env(reader)
        assert source.ffmpeg_path == ffmpeg

    def test_reads_server_config(self) -> None:
        """Should read server config from environment."""
        reader = EnvReader(
            env={
                "VPO_SERVER_BIND": "0.0.0.0",
                "VPO_SERVER_PORT": "9000",
                "VPO_SERVER_SHUTDOWN_TIMEOUT": "45.0",
                "VPO_AUTH_TOKEN": "secret123",
            }
        )
        source = source_from_env(reader)
        assert source.server_bind == "0.0.0.0"
        assert source.server_port == 9000
        assert source.server_shutdown_timeout == pytest.approx(45.0)
        assert source.server_auth_token == "secret123"

    def test_reads_detection_config(self) -> None:
        """Should read detection config from environment."""
        reader = EnvReader(
            env={
                "VPO_CACHE_TTL_HOURS": "48",
                "VPO_AUTO_DETECT_ON_STARTUP": "false",
            }
        )
        source = source_from_env(reader)
        assert source.cache_ttl_hours == 48
        assert source.auto_detect_on_startup is False

    def test_reads_jobs_config(self) -> None:
        """Should read jobs config from environment."""
        reader = EnvReader(
            env={
                "VPO_JOBS_RETENTION_DAYS": "60",
                "VPO_JOBS_AUTO_PURGE": "false",
                "VPO_LOG_COMPRESSION_DAYS": "14",
                "VPO_LOG_DELETION_DAYS": "180",
            }
        )
        source = source_from_env(reader)
        assert source.jobs_retention_days == 60
        assert source.jobs_auto_purge is False
        assert source.jobs_log_compression_days == 14
        assert source.jobs_log_deletion_days == 180

    def test_reads_worker_config(self) -> None:
        """Should read worker config from environment."""
        reader = EnvReader(
            env={
                "VPO_WORKER_MAX_FILES": "50",
                "VPO_WORKER_MAX_DURATION": "7200",
                "VPO_WORKER_END_BY": "22:00",
                "VPO_WORKER_CPU_CORES": "8",
            }
        )
        source = source_from_env(reader)
        assert source.worker_max_files == 50
        assert source.worker_max_duration == 7200
        assert source.worker_end_by == "22:00"
        assert source.worker_cpu_cores == 8


class TestBuilderPrecedence:
    """Tests for configuration precedence handling."""

    def test_cli_overrides_env_overrides_file(self, tmp_path: Path) -> None:
        """Demonstrates: CLI > env > file > defaults."""
        file_source = ConfigSource(
            server_port=8000,  # From file
            server_bind="127.0.0.1",  # From file
            cache_ttl_hours=24,  # From file
        )
        env_source = ConfigSource(
            server_port=9000,  # Overrides file
            server_bind="0.0.0.0",  # Overrides file
        )
        cli_source = ConfigSource(
            server_port=8080,  # Overrides env and file
        )

        builder = ConfigBuilder()
        builder.apply(file_source)
        builder.apply(env_source)
        builder.apply(cli_source)

        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        # CLI wins for port
        assert config.server.port == 8080
        # ENV wins for bind (CLI didn't set it)
        assert config.server.bind == "0.0.0.0"
        # File wins for cache_ttl (env and CLI didn't set it)
        assert config.detection.cache_ttl_hours == 24
        # Default for language (nothing set it)
        assert config.language.standard == "639-2/B"


class TestProcessingConfig:
    """Tests for processing config in ConfigBuilder."""

    def test_default_processing_config(self, tmp_path: Path) -> None:
        """Should use default processing config when not specified."""
        builder = ConfigBuilder()
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.processing.workers == 2

    def test_processing_workers_from_source(self, tmp_path: Path) -> None:
        """Should configure processing workers from source."""
        builder = ConfigBuilder()
        builder.apply(ConfigSource(processing_workers=4))
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.processing.workers == 4

    def test_processing_from_file_config(self) -> None:
        """Should parse processing section from TOML config."""
        file_config = {
            "processing": {
                "workers": 8,
            }
        }
        source = source_from_file(file_config)
        assert source.processing_workers == 8

    def test_processing_from_env(self) -> None:
        """Should read processing workers from environment."""
        reader = EnvReader(env={"VPO_PROCESSING_WORKERS": "6"})
        source = source_from_env(reader)
        assert source.processing_workers == 6


class TestMinFreeDiskPercentConfig:
    """Tests for min_free_disk_percent configuration loading."""

    def test_min_free_disk_percent_default(self, tmp_path: Path) -> None:
        """Should use default 5.0 when not specified."""
        builder = ConfigBuilder()
        config = builder.build(default_plugins_dir=tmp_path / "plugins")
        assert config.jobs.min_free_disk_percent == 5.0

    def test_min_free_disk_percent_from_file(self) -> None:
        """Should parse min_free_disk_percent from TOML config."""
        file_config = {
            "jobs": {
                "min_free_disk_percent": 10.0,
            }
        }
        source = source_from_file(file_config)
        assert source.jobs_min_free_disk_percent == 10.0

    def test_min_free_disk_percent_from_env(self) -> None:
        """Should read min_free_disk_percent from environment."""
        reader = EnvReader(env={"VPO_MIN_FREE_DISK_PERCENT": "15.5"})
        source = source_from_env(reader)
        assert source.jobs_min_free_disk_percent == pytest.approx(15.5)

    def test_min_free_disk_percent_env_overrides_file(self, tmp_path: Path) -> None:
        """Environment should override file config."""
        file_source = ConfigSource(jobs_min_free_disk_percent=5.0)
        env_source = ConfigSource(jobs_min_free_disk_percent=20.0)

        builder = ConfigBuilder()
        builder.apply(file_source)
        builder.apply(env_source)
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.jobs.min_free_disk_percent == 20.0

    def test_min_free_disk_percent_zero_disables(self, tmp_path: Path) -> None:
        """Setting to 0 should disable the check."""
        builder = ConfigBuilder()
        builder.apply(ConfigSource(jobs_min_free_disk_percent=0.0))
        config = builder.build(default_plugins_dir=tmp_path / "plugins")

        assert config.jobs.min_free_disk_percent == 0.0
