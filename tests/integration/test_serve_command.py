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

    from video_policy_orchestrator.db.schema import initialize_database

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    # Use proper schema initialization
    initialize_database(conn)
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


class TestConcurrentHealthRequests:
    """Tests for concurrent health endpoint access."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_concurrent_health_requests_no_connection_exhaustion(
        self, temp_db: Path
    ) -> None:
        """Test that health endpoint handles concurrent requests safely.

        This verifies that the connection pool properly handles many
        simultaneous health check requests without exhausting file
        descriptors or database connections.
        """
        import concurrent.futures
        import urllib.request

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
            assert wait_for_port(port, timeout=10.0), f"Server didn't start on {port}"

            def make_health_request():
                """Make a single health request."""
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/health", timeout=5.0
                    ) as response:
                        return response.status
                except Exception as e:
                    return str(e)

            # Make 50 concurrent health check requests using thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_health_request) for _ in range(50)]
                results = [f.result() for f in futures]

            # Count successful responses
            successes = sum(1 for r in results if r in (200, 503))
            errors = [r for r in results if r not in (200, 503)]

            # All requests should succeed
            assert successes == 50, f"Only {successes}/50 succeeded. Errors: {errors}"

        finally:
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
    def test_daemon_shutdown_closes_connections(self, temp_db: Path) -> None:
        """Test that connection pool is properly closed on shutdown.

        Verifies that no database connections are leaked when the
        daemon shuts down gracefully.
        """
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

            # Make a health request to ensure pool is initialized
            import urllib.request

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                assert response.status == 200

            # Send SIGTERM for graceful shutdown
            proc.send_signal(signal.SIGTERM)

            # Should exit cleanly
            exit_code = proc.wait(timeout=15.0)
            assert exit_code in (0, -signal.SIGTERM), f"Unexpected exit: {exit_code}"

            # After shutdown, the database should be accessible
            # (not locked by leaked connections)
            import sqlite3

            conn = sqlite3.connect(str(temp_db), timeout=1.0)
            conn.execute("SELECT 1")
            conn.close()

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_api_policies_endpoint(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that /api/policies returns policy files.

        Integration test for 023-policies-list-view: Verify the API endpoint
        correctly discovers and returns policy files from the filesystem.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create test policies directory with sample policy files
        policies_dir = tmp_path / ".vpo" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)

        # Create a valid basic policy
        basic_policy = policies_dir / "test-basic.yaml"
        basic_policy.write_text(
            "schema_version: 2\naudio_language_preference:\n  - eng\n"
        )

        # Create a policy with features
        full_policy = policies_dir / "test-full.yaml"
        full_policy.write_text(
            "schema_version: 2\n"
            "audio_language_preference:\n  - eng\n  - jpn\n"
            "transcode:\n  target_video_codec: hevc\n"
            "transcription:\n  enabled: true\n"
        )

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)  # Override home for policies discovery

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
            assert wait_for_port(port, timeout=10.0), "Server didn't start"

            # Request policies API
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/policies", timeout=5.0
            ) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            # Verify response structure
            assert "policies" in data
            assert "total" in data
            assert "policies_directory" in data
            assert data["total"] == 2

            # Verify policy names
            names = [p["name"] for p in data["policies"]]
            assert "test-basic" in names
            assert "test-full" in names

            # Verify policy metadata
            full = next(p for p in data["policies"] if p["name"] == "test-full")
            assert full["schema_version"] == 2
            assert full["has_transcode"] is True
            assert full["has_transcription"] is True

        finally:
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
    def test_policies_page_loads(self, temp_db: Path) -> None:
        """Test that /policies HTML page loads successfully.

        Integration test for 023-policies-list-view: Verify the HTML page
        renders without errors.
        """
        import urllib.request

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
            assert wait_for_port(port, timeout=10.0), "Server didn't start"

            # Request policies page
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/policies", timeout=5.0
            ) as response:
                assert response.status == 200
                html = response.read().decode()

            # Verify it's an HTML page with expected content
            assert "<!DOCTYPE html>" in html or "<html" in html
            assert "Policies" in html

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
