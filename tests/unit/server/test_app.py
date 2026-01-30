"""Tests for server app creation."""

from pathlib import Path

from vpo.server.app import create_app


class TestCreateApp:
    """Tests for create_app factory."""

    def test_create_app_with_db_path(self, tmp_path: Path):
        """create_app with a db_path initializes the database without error."""
        db_path = tmp_path / "test.db"
        # create_app requires the file to exist (serve command creates it first)
        db_path.touch()
        app = create_app(db_path=db_path, auth_token=None)

        assert app["connection_pool"] is not None
        # Database file should have been created
        assert db_path.exists()

        # Clean up pool
        app["connection_pool"].close()

    def test_create_app_without_db_path(self):
        """create_app with db_path=None skips pool creation."""
        app = create_app(db_path=None, auth_token=None)
        assert app["connection_pool"] is None
