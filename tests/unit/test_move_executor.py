"""Tests for move executor module."""

from pathlib import Path

import pytest

from vpo.executor.move import (
    MAX_UNIQUE_PATH_ATTEMPTS,
    ensure_unique_path,
)


class TestEnsureUniquePath:
    """Tests for ensure_unique_path function."""

    def test_returns_original_if_not_exists(self, tmp_path: Path) -> None:
        """Should return original path if it doesn't exist."""
        path = tmp_path / "test.mkv"
        result = ensure_unique_path(path)
        assert result == path

    def test_adds_suffix_if_exists(self, tmp_path: Path) -> None:
        """Should add (1) suffix if path exists."""
        path = tmp_path / "test.mkv"
        path.touch()

        result = ensure_unique_path(path)
        assert result == tmp_path / "test (1).mkv"

    def test_increments_suffix(self, tmp_path: Path) -> None:
        """Should increment suffix until unique."""
        path = tmp_path / "test.mkv"
        path.touch()
        (tmp_path / "test (1).mkv").touch()
        (tmp_path / "test (2).mkv").touch()

        result = ensure_unique_path(path)
        assert result == tmp_path / "test (3).mkv"

    def test_raises_on_max_attempts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should raise RuntimeError after max attempts exceeded."""
        import vpo.executor.move as move_module

        # Temporarily set a very low max attempts
        monkeypatch.setattr(move_module, "MAX_UNIQUE_PATH_ATTEMPTS", 3)

        path = tmp_path / "test.mkv"
        path.touch()
        (tmp_path / "test (1).mkv").touch()
        (tmp_path / "test (2).mkv").touch()
        (tmp_path / "test (3).mkv").touch()

        with pytest.raises(RuntimeError, match="Could not find unique path"):
            ensure_unique_path(path, max_attempts=3)

    def test_handles_complex_filenames(self, tmp_path: Path) -> None:
        """Should handle filenames with spaces and special characters."""
        path = tmp_path / "My Video (2024) [1080p].mkv"
        path.touch()

        result = ensure_unique_path(path)
        assert result == tmp_path / "My Video (2024) [1080p] (1).mkv"

    def test_max_attempts_constant_is_reasonable(self) -> None:
        """MAX_UNIQUE_PATH_ATTEMPTS should be a reasonable value."""
        assert MAX_UNIQUE_PATH_ATTEMPTS >= 1000
        assert MAX_UNIQUE_PATH_ATTEMPTS <= 100000
