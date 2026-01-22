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

    from vpo.db.schema import initialize_database

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
                "vpo.cli",
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
                "vpo.cli",
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
        from vpo.server.app import HealthStatus

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
        from vpo.server.app import HealthStatus

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
                "vpo.cli",
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
                "vpo.cli",
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

        # Create a valid basic policy (phased format required)
        basic_policy = policies_dir / "test-basic.yaml"
        basic_policy.write_text(
            "schema_version: 12\n"
            "config:\n"
            "  audio_language_preference:\n    - eng\n"
            "phases:\n"
            "  - name: apply\n"
            "    default_flags:\n"
            "      set_first_video_default: true\n"
        )

        # Create a policy with features (phased format required)
        full_policy = policies_dir / "test-full.yaml"
        full_policy.write_text(
            "schema_version: 12\n"
            "config:\n"
            "  audio_language_preference:\n    - eng\n    - jpn\n"
            "phases:\n"
            "  - name: transcode\n"
            "    transcode:\n"
            "      video:\n"
            "        target_codec: hevc\n"
            "  - name: transcribe\n"
            "    transcription:\n"
            "      enabled: true\n"
        )

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)  # Override home for policies discovery

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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
            assert full["schema_version"] == 12
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
                "vpo.cli",
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

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Signal handling tests not supported on Windows",
    )
    def test_api_policies_malformed_yaml(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that /api/policies handles malformed YAML files gracefully.

        Integration test for 023-policies-list-view: Verify parse errors
        are captured and returned in the response.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create test policies directory with malformed policy
        policies_dir = tmp_path / ".vpo" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)

        # Create a malformed YAML file
        malformed_policy = policies_dir / "bad-policy.yaml"
        malformed_policy.write_text("invalid: yaml: content: [unclosed")

        # Create a valid policy for comparison (phased format required)
        valid_policy = policies_dir / "good-policy.yaml"
        valid_policy.write_text(
            "schema_version: 12\n"
            "phases:\n"
            "  - name: apply\n"
            "    default_flags:\n"
            "      set_first_video_default: true\n"
        )

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/policies", timeout=5.0
            ) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["total"] == 2

            # Find the malformed policy
            bad = next(p for p in data["policies"] if p["name"] == "bad-policy")
            assert bad["parse_error"] is not None
            assert "YAML" in bad["parse_error"]

            # Valid policy should have no error
            good = next(p for p in data["policies"] if p["name"] == "good-policy")
            assert good["parse_error"] is None
            assert good["schema_version"] == 12

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
    def test_api_policies_empty_directory(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that /api/policies handles empty directory.

        Integration test for 023-policies-list-view: Verify correct response
        when policies directory exists but is empty.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create empty policies directory
        policies_dir = tmp_path / ".vpo" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/policies", timeout=5.0
            ) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["total"] == 0
            assert data["policies"] == []
            assert data["directory_exists"] is True

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
    def test_api_policies_both_extensions(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that /api/policies discovers both .yaml and .yml files.

        Integration test for 023-policies-list-view: Verify both file
        extensions are discovered correctly.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create policies directory with both extensions
        policies_dir = tmp_path / ".vpo" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)

        yaml_policy = policies_dir / "policy-yaml.yaml"
        yaml_policy.write_text("schema_version: 12\n")

        yml_policy = policies_dir / "policy-yml.yml"
        yml_policy.write_text("schema_version: 12\n")

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/policies", timeout=5.0
            ) as response:
                assert response.status == 200
                data = json.loads(response.read().decode())

            assert data["total"] == 2
            names = [p["name"] for p in data["policies"]]
            assert "policy-yaml" in names
            assert "policy-yml" in names

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class TestSIGHUPReload:
    """Integration tests for SIGHUP configuration reload."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_triggers_config_reload(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that SIGHUP triggers configuration reload.

        Verifies that sending SIGHUP to the daemon process triggers
        a config reload and the health endpoint reflects the change.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create config file
        config_dir = tmp_path / ".vpo"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("[jobs]\nretention_days = 30\n")

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            # Check initial health - reload count should be 0
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())
                assert data["config_reload_count"] == 0
                assert data["last_config_reload"] is None

            # Modify config file
            config_file.write_text("[jobs]\nretention_days = 60\n")

            # Send SIGHUP to trigger reload
            proc.send_signal(signal.SIGHUP)

            # Wait for reload to complete
            time.sleep(1.0)

            # Check health after reload
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())
                assert data["config_reload_count"] == 1
                assert data["last_config_reload"] is not None
                assert data["config_reload_error"] is None

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_sighup_no_changes_detected(self, temp_db: Path, tmp_path: Path) -> None:
        """Test SIGHUP when config file has not changed.

        Verifies that SIGHUP works even when config is unchanged,
        and reload_count stays at 0 when no changes detected.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create config file
        config_dir = tmp_path / ".vpo"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("[jobs]\nretention_days = 30\n")

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            # Send SIGHUP without changing config
            proc.send_signal(signal.SIGHUP)

            # Wait for reload to complete
            time.sleep(1.0)

            # Check health - reload count should stay 0 when no changes
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())
                # No changes means reload_count stays at 0
                assert data["config_reload_count"] == 0
                assert data["config_reload_error"] is None

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_health_shows_reload_state(self, temp_db: Path, tmp_path: Path) -> None:
        """Test that health endpoint includes reload state fields.

        Verifies the health endpoint response includes config reload
        metrics in the response.
        """
        import json
        import urllib.request

        port = find_free_port()

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())

            # Check that reload fields are present
            assert "last_config_reload" in data
            assert "config_reload_count" in data
            assert "config_reload_error" in data

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGHUP not available on Windows",
    )
    def test_multiple_sighup_increments_count(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """Test that multiple SIGHUP signals increment reload count.

        Verifies that each successful reload with changes increments
        the reload_count counter.
        """
        import json
        import urllib.request

        port = find_free_port()

        # Create config file
        config_dir = tmp_path / ".vpo"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("[jobs]\nretention_days = 30\n")

        env = os.environ.copy()
        env["VPO_DATABASE_PATH"] = str(temp_db)
        env["HOME"] = str(tmp_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "vpo.cli",
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

            # First reload
            config_file.write_text("[jobs]\nretention_days = 31\n")
            proc.send_signal(signal.SIGHUP)
            time.sleep(1.0)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())
                assert data["config_reload_count"] == 1

            # Second reload
            config_file.write_text("[jobs]\nretention_days = 32\n")
            proc.send_signal(signal.SIGHUP)
            time.sleep(1.0)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=5.0
            ) as response:
                data = json.loads(response.read().decode())
                assert data["config_reload_count"] == 2

        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
