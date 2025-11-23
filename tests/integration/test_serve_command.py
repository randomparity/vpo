"""Integration tests for the serve command and health endpoint."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


def wait_for_port(port: int, timeout: float = 5.0) -> bool:
    """Wait for a port to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(0.1)
    return False


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database for testing."""
    import sqlite3

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    # Create minimal schema so health check passes
    conn.execute("CREATE TABLE IF NOT EXISTS files (id TEXT)")
    conn.commit()
    conn.close()
    return db_path


class TestServeCommand:
    """Integration tests for vpo serve command."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_serve_starts_and_responds_to_health(self, temp_db: Path) -> None:
        """Test that serve starts and responds to health requests."""
        port = find_free_port()

        # Start the server
        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "video_policy_orchestrator.cli",
                "serve",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for server to start
            assert wait_for_port(port, timeout=10.0), f"Server didn't start on {port}"

            # Make health request
            import urllib.request

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                assert response.status == 200
                data = response.read().decode()
                assert "healthy" in data or "status" in data

        finally:
            # Clean shutdown
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_serve_graceful_shutdown_on_sigterm(self, temp_db: Path) -> None:
        """Test that serve shuts down gracefully on SIGTERM."""
        port = find_free_port()

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "video_policy_orchestrator.cli",
                "serve",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for server to start
            assert wait_for_port(port, timeout=10.0), "Server didn't start"

            # Send SIGTERM
            proc.send_signal(signal.SIGTERM)

            # Should exit cleanly within shutdown timeout
            exit_code = proc.wait(timeout=35.0)

            # Exit code 0 is clean shutdown
            # Exit code -15 (SIGTERM) is also acceptable
            assert exit_code in (0, -signal.SIGTERM), (
                f"Unexpected exit code: {exit_code}"
            )

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestHealthEndpoint:
    """Tests for the /health endpoint response format."""

    def test_health_status_dataclass_serialization(self) -> None:
        """Test that HealthStatus serializes correctly."""
        from video_policy_orchestrator.server.app import HealthStatus

        status = HealthStatus(
            status="healthy",
            database="connected",
            uptime_seconds=123.5,
            version="0.1.0",
            shutting_down=False,
        )

        data = status.to_dict()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["uptime_seconds"] == 123.5
        assert data["version"] == "0.1.0"
        assert data["shutting_down"] is False

    def test_health_status_degraded_when_shutting_down(self) -> None:
        """Test that shutting_down flag is reflected."""
        from video_policy_orchestrator.server.app import HealthStatus

        status = HealthStatus(
            status="unhealthy",
            database="connected",
            uptime_seconds=100.0,
            version="0.1.0",
            shutting_down=True,
        )

        assert status.shutting_down is True
        assert status.status == "unhealthy"
