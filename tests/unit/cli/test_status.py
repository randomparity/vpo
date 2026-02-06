"""Tests for vpo status dashboard command."""

import json
import sqlite3

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.db.schema import create_schema


@pytest.fixture
def db_conn(tmp_path):
    """Create an in-memory database with schema."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


class TestStatusCommand:
    """Tests for vpo status command."""

    def test_status_shows_sections(self, runner: CliRunner, db_conn) -> None:
        """Test that status command shows Library, Jobs, and Tools sections."""
        result = runner.invoke(main, ["status"], obj={"db_conn": db_conn})

        assert result.exit_code == 0
        assert "Library:" in result.output
        assert "Jobs:" in result.output
        assert "Tools:" in result.output

    def test_status_shows_file_counts(self, runner: CliRunner, db_conn) -> None:
        """Test that status shows file total."""
        result = runner.invoke(main, ["status"], obj={"db_conn": db_conn})

        assert result.exit_code == 0
        assert "Files:" in result.output
        assert "0 total" in result.output

    def test_status_json_output(self, runner: CliRunner, db_conn) -> None:
        """Test that --format json produces valid JSON with expected keys."""
        result = runner.invoke(
            main, ["status", "--format", "json"], obj={"db_conn": db_conn}
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "library" in data
        assert "jobs" in data
        assert "tools" in data
        assert data["library"]["total_files"] == 0

    def test_status_json_backward_compat(self, runner: CliRunner, db_conn) -> None:
        """Test that --json (hidden flag) works."""
        result = runner.invoke(main, ["status", "--json"], obj={"db_conn": db_conn})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "library" in data

    def test_status_no_db(self, runner: CliRunner) -> None:
        """Test status when no database connection is available."""
        result = runner.invoke(main, ["status"], obj={"db_conn": None})

        assert result.exit_code == 0
        assert "no database connection" in result.output

    def test_status_help(self, runner: CliRunner) -> None:
        """Test that status --help shows usage."""
        result = runner.invoke(main, ["status", "--help"])

        assert result.exit_code == 0
        assert (
            "summary" in result.output.lower() or "dashboard" in result.output.lower()
        )
