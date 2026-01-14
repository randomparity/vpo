"""Unit tests for Rust core extension."""

from pathlib import Path


class TestDiscoverVideos:
    """Tests for discover_videos function."""

    def test_discover_empty_directory(self, temp_dir: Path):
        """Test discovering videos in an empty directory."""
        from vpo._core import discover_videos

        result = discover_videos(str(temp_dir), ["mkv", "mp4"])
        assert result == []

    def test_discover_videos_finds_files(self, temp_video_dir: Path):
        """Test that discover_videos finds video files."""
        from vpo._core import discover_videos

        result = discover_videos(str(temp_video_dir), ["mkv", "mp4"])

        # Should find movie.mkv, show.mp4, and nested/episode.mkv
        # Should NOT find .hidden/secret.mkv
        assert len(result) == 3

        paths = [r["path"] for r in result]
        assert any("movie.mkv" in p for p in paths)
        assert any("show.mp4" in p for p in paths)
        assert any("episode.mkv" in p for p in paths)
        assert not any(".hidden" in p for p in paths)

    def test_discover_videos_skips_hidden_directories(self, temp_video_dir: Path):
        """Test that hidden directories are skipped."""
        from vpo._core import discover_videos

        result = discover_videos(str(temp_video_dir), ["mkv"])
        paths = [r["path"] for r in result]

        # Should not find the file in .hidden
        assert not any(".hidden" in p for p in paths)

    def test_discover_videos_returns_metadata(self, temp_video_dir: Path):
        """Test that discovered files include metadata."""
        from vpo._core import discover_videos

        result = discover_videos(str(temp_video_dir), ["mkv", "mp4"])

        for file_info in result:
            assert "path" in file_info
            assert "size" in file_info
            assert "modified" in file_info
            assert isinstance(file_info["path"], str)
            assert isinstance(file_info["size"], int)
            assert isinstance(file_info["modified"], float)

    def test_discover_videos_case_insensitive_extensions(self, temp_dir: Path):
        """Test that extension matching is case-insensitive."""
        from vpo._core import discover_videos

        # Create files with mixed case extensions
        (temp_dir / "video.MKV").touch()
        (temp_dir / "video.Mp4").touch()

        result = discover_videos(str(temp_dir), ["mkv", "mp4"])
        assert len(result) == 2

    def test_discover_videos_nonexistent_directory(self):
        """Test error handling for nonexistent directory."""
        import pytest

        from vpo._core import discover_videos

        with pytest.raises(FileNotFoundError):
            discover_videos("/nonexistent/path", ["mkv"])

    def test_discover_videos_not_a_directory(self, temp_dir: Path):
        """Test error handling for file path instead of directory."""
        import pytest

        from vpo._core import discover_videos

        file_path = temp_dir / "file.txt"
        file_path.touch()

        with pytest.raises(NotADirectoryError):
            discover_videos(str(file_path), ["mkv"])

    def test_discover_videos_with_sample_fixtures(self, sample_videos_dir: Path):
        """Test discovery with sample fixtures."""
        from vpo._core import discover_videos

        result = discover_videos(str(sample_videos_dir), ["mkv", "mp4"])

        # Fixtures: video.mkv, video.mp4, nested/deep.mkv
        # NOT: .hidden/hidden.mkv
        assert len(result) == 3


class TestHashFiles:
    """Tests for hash_files function."""

    def test_hash_empty_file(self, temp_dir: Path):
        """Test hashing an empty file."""
        from vpo._core import hash_files

        file_path = temp_dir / "empty.bin"
        file_path.touch()

        result = hash_files([str(file_path)])
        assert len(result) == 1
        assert result[0]["path"] == str(file_path)
        assert result[0]["hash"] is not None
        assert result[0]["error"] is None
        assert result[0]["hash"].startswith("xxh64:")

    def test_hash_small_file(self, temp_dir: Path):
        """Test hashing a small file (under 128KB)."""
        from vpo._core import hash_files

        file_path = temp_dir / "small.bin"
        file_path.write_bytes(b"hello world")

        result = hash_files([str(file_path)])
        assert len(result) == 1
        assert result[0]["hash"] is not None
        assert result[0]["hash"].startswith("xxh64:")

    def test_hash_large_file(self, temp_dir: Path):
        """Test hashing a large file (over 128KB)."""
        from vpo._core import hash_files

        file_path = temp_dir / "large.bin"
        # Write 200KB of data
        file_path.write_bytes(b"x" * 200_000)

        result = hash_files([str(file_path)])
        assert len(result) == 1
        assert result[0]["hash"] is not None
        assert result[0]["hash"].startswith("xxh64:")
        assert ":200000" in result[0]["hash"]  # Size is in the hash

    def test_hash_multiple_files(self, temp_dir: Path):
        """Test hashing multiple files in parallel."""
        from vpo._core import hash_files

        paths = []
        for i in range(5):
            path = temp_dir / f"file{i}.bin"
            path.write_bytes(f"content{i}".encode())
            paths.append(str(path))

        result = hash_files(paths)
        assert len(result) == 5
        assert all(r["hash"] is not None for r in result)
        assert all(r["error"] is None for r in result)

    def test_hash_nonexistent_file(self):
        """Test error handling for nonexistent file."""
        from vpo._core import hash_files

        result = hash_files(["/nonexistent/file.bin"])
        assert len(result) == 1
        assert result[0]["hash"] is None
        assert result[0]["error"] is not None

    def test_hash_same_content_same_hash(self, temp_dir: Path):
        """Test that identical content produces identical hash."""
        from vpo._core import hash_files

        content = b"identical content"
        file1 = temp_dir / "file1.bin"
        file2 = temp_dir / "file2.bin"
        file1.write_bytes(content)
        file2.write_bytes(content)

        result = hash_files([str(file1), str(file2)])
        assert result[0]["hash"] == result[1]["hash"]

    def test_hash_different_content_different_hash(self, temp_dir: Path):
        """Test that different content produces different hash."""
        from vpo._core import hash_files

        file1 = temp_dir / "file1.bin"
        file2 = temp_dir / "file2.bin"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        result = hash_files([str(file1), str(file2)])
        assert result[0]["hash"] != result[1]["hash"]
