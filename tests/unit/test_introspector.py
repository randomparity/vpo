"""Unit tests for MediaIntrospector."""

from pathlib import Path


class TestMediaIntrospectorProtocol:
    """Tests for MediaIntrospector protocol compliance."""

    def test_stub_introspector_implements_protocol(self):
        """Test that StubIntrospector implements MediaIntrospector protocol."""
        from vpo.introspector.stub import StubIntrospector

        introspector = StubIntrospector()

        # Check that StubIntrospector is an instance of MediaIntrospector
        # (structural typing via Protocol)
        assert hasattr(introspector, "get_file_info")
        assert callable(introspector.get_file_info)

    def test_media_introspection_error_exists(self):
        """Test that MediaIntrospectionError exception is defined."""
        from vpo.introspector.interface import (
            MediaIntrospectionError,
        )

        error = MediaIntrospectionError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)


class TestStubIntrospector:
    """Tests for StubIntrospector implementation."""

    def test_get_file_info_returns_introspection_result(self, temp_dir: Path):
        """Test that get_file_info returns an IntrospectionResult object."""
        from vpo.db import IntrospectionResult
        from vpo.introspector.stub import StubIntrospector

        # Create a test file
        file_path = temp_dir / "test.mkv"
        file_path.write_bytes(b"fake video content")

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert isinstance(result, IntrospectionResult)
        assert result.file_path == file_path
        assert result.container_format == "matroska"

    def test_container_format_mkv(self, temp_dir: Path):
        """Test that .mkv files get matroska container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.mkv"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "matroska"

    def test_container_format_mp4(self, temp_dir: Path):
        """Test that .mp4 files get mp4 container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.mp4"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "mp4"

    def test_container_format_avi(self, temp_dir: Path):
        """Test that .avi files get avi container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.avi"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "avi"

    def test_container_format_webm(self, temp_dir: Path):
        """Test that .webm files get webm container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.webm"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "webm"

    def test_container_format_mov(self, temp_dir: Path):
        """Test that .mov files get quicktime container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.mov"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "quicktime"

    def test_container_format_m4v(self, temp_dir: Path):
        """Test that .m4v files get mp4 container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.m4v"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format == "mp4"

    def test_container_format_unknown_extension(self, temp_dir: Path):
        """Test that unknown extensions get None container format."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.xyz"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.container_format is None

    def test_stub_returns_placeholder_tracks(self, temp_dir: Path):
        """Test that stub returns placeholder track information."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "video.mkv"
        file_path.touch()

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        # Stub returns at least one video track
        assert len(result.tracks) >= 1
        assert any(t.track_type == "video" for t in result.tracks)

    def test_introspection_result_has_correct_structure(self, temp_dir: Path):
        """Test that IntrospectionResult has correct structure."""
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "test_video.mkv"
        content = b"some fake video content"
        file_path.write_bytes(content)

        introspector = StubIntrospector()
        result = introspector.get_file_info(file_path)

        assert result.file_path == file_path
        assert result.container_format == "matroska"
        assert isinstance(result.tracks, list)
        assert isinstance(result.warnings, list)
        assert result.success is True

    def test_nonexistent_file_raises_error(self, temp_dir: Path):
        """Test that nonexistent file raises MediaIntrospectionError."""
        import pytest

        from vpo.introspector.interface import (
            MediaIntrospectionError,
        )
        from vpo.introspector.stub import StubIntrospector

        file_path = temp_dir / "nonexistent.mkv"

        introspector = StubIntrospector()
        with pytest.raises(MediaIntrospectionError):
            introspector.get_file_info(file_path)
