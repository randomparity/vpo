"""Tests for the serve command."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.cli.serve import serve_command


class TestServeBindWarnings:
    """Tests for non-loopback bind address warnings."""

    @pytest.fixture()
    def _mock_dependencies(self):
        """Mock all heavy dependencies so serve_command can run its checks."""
        with (
            patch("vpo.cli.serve.get_config") as mock_config,
            patch("vpo.cli.serve.check_database_connectivity", return_value=True),
            patch(
                "vpo.cli.serve.get_default_db_path",
                return_value=Path("/tmp/test.db"),
            ),
            patch("vpo.server.cleanup.cleanup_orphaned_temp_files", return_value=0),
            patch("vpo.cli.serve.asyncio.run", side_effect=SystemExit(0)),
            patch("vpo.cli.serve._configure_daemon_logging"),
        ):
            cfg = MagicMock()
            cfg.server.bind = "127.0.0.1"
            cfg.server.port = 8321
            cfg.server.shutdown_timeout = 5.0
            cfg.server.auth_token = None
            cfg.database_path = None
            mock_config.return_value = cfg
            yield cfg

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_no_warning_for_localhost(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning is emitted when binding to localhost."""
        from click.testing import CliRunner

        with caplog.at_level(logging.WARNING):
            runner = CliRunner()
            runner.invoke(
                serve_command, ["--bind", "127.0.0.1"], catch_exceptions=False
            )

        assert "exposes VPO to the network" not in caplog.text

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_warning_for_all_interfaces(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warning is emitted when binding to 0.0.0.0."""
        from click.testing import CliRunner

        with caplog.at_level(logging.WARNING):
            runner = CliRunner()
            runner.invoke(serve_command, ["--bind", "0.0.0.0"], catch_exceptions=False)

        assert "exposes VPO to the network" in caplog.text

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_auth_warning_when_no_token(
        self, _mock_dependencies: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Extra auth warning when binding to non-loopback without auth token."""
        _mock_dependencies.server.auth_token = None
        from click.testing import CliRunner

        with caplog.at_level(logging.WARNING):
            runner = CliRunner()
            runner.invoke(serve_command, ["--bind", "0.0.0.0"], catch_exceptions=False)

        assert "authentication DISABLED" in caplog.text

    @pytest.mark.usefixtures("_mock_dependencies")
    def test_no_auth_warning_when_token_set(
        self, _mock_dependencies: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No auth warning when binding to non-loopback with auth token set."""
        _mock_dependencies.server.auth_token = "secret-token"
        from click.testing import CliRunner

        with caplog.at_level(logging.WARNING):
            runner = CliRunner()
            runner.invoke(serve_command, ["--bind", "0.0.0.0"], catch_exceptions=False)

        assert "exposes VPO to the network" in caplog.text
        assert "authentication DISABLED" not in caplog.text
