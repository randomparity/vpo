"""Unit tests for output handling (Phase 12).

Tests temp file handling, atomic replacement, cleanup on failure,
and output integrity verification.
"""

from pathlib import Path
from unittest.mock import patch

from vpo.executor.transcode import TranscodeExecutor
from vpo.policy.types import TranscodePolicyConfig


class TestTempFilePathGeneration:
    """T080: Unit tests for temp file path generation."""

    def test_temp_path_in_same_directory(self) -> None:
        """Temp file is created in same directory as output."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        output_path = Path("/video/movie.mkv")
        temp_path = executor._get_temp_output_path(output_path)

        assert temp_path.parent == output_path.parent
        assert temp_path != output_path

    def test_temp_path_has_temp_prefix(self) -> None:
        """Temp file has a distinguishable prefix."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        output_path = Path("/video/movie.mkv")
        temp_path = executor._get_temp_output_path(output_path)

        # VPO uses .vpo_temp_ prefix for temp files
        assert ".vpo_temp_" in temp_path.name

    def test_temp_path_preserves_extension(self) -> None:
        """Temp file preserves the output extension."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        output_path = Path("/video/movie.mkv")
        temp_path = executor._get_temp_output_path(output_path)

        # Temp file should be able to hold mkv content
        assert temp_path.suffix in (".mkv", ".tmp")

    def test_temp_path_custom_directory(self) -> None:
        """Temp file can use custom directory if specified."""
        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        output_path = Path("/video/movie.mkv")
        custom_dir = Path("/tmp/vpo")

        with patch(
            "vpo.executor.transcode.executor.get_temp_directory_for_file",
            return_value=custom_dir,
        ):
            temp_path = executor._get_temp_output_path(output_path)

        # When temp directory is configured, temp file goes there
        assert temp_path.parent == custom_dir


class TestAtomicFileReplacement:
    """T081: Unit tests for atomic file replacement."""

    def test_atomic_replace_moves_temp_to_output(self, tmp_path: Path) -> None:
        """Atomic replace moves temp file to output location."""
        temp_file = tmp_path / "temp.mkv"
        output_file = tmp_path / "output.mkv"

        # Create temp file with content
        temp_file.write_bytes(b"test video content")

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        # Perform atomic replacement
        executor._atomic_replace(temp_file, output_file)

        assert output_file.exists()
        assert not temp_file.exists()
        assert output_file.read_bytes() == b"test video content"

    def test_atomic_replace_overwrites_existing(self, tmp_path: Path) -> None:
        """Atomic replace overwrites existing output file."""
        temp_file = tmp_path / "temp.mkv"
        output_file = tmp_path / "output.mkv"

        # Create existing output file
        output_file.write_bytes(b"old content")
        # Create temp file with new content
        temp_file.write_bytes(b"new content")

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        executor._atomic_replace(temp_file, output_file)

        assert output_file.read_bytes() == b"new content"


class TestCleanupOnFailure:
    """T082: Unit tests for cleanup on failure."""

    def test_cleanup_removes_temp_file(self, tmp_path: Path) -> None:
        """Cleanup removes temp file on failure."""
        temp_file = tmp_path / "temp.mkv"
        temp_file.write_bytes(b"partial content")

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        executor._cleanup_partial(temp_file)

        assert not temp_file.exists()

    def test_cleanup_ignores_missing_file(self, tmp_path: Path) -> None:
        """Cleanup doesn't fail for missing temp file."""
        temp_file = tmp_path / "nonexistent.mkv"

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        # Should not raise
        executor._cleanup_partial(temp_file)

    def test_cleanup_preserves_original(self, tmp_path: Path) -> None:
        """Cleanup preserves the original file."""
        original_file = tmp_path / "original.mkv"
        temp_file = tmp_path / "temp.mkv"

        original_file.write_bytes(b"original content")
        temp_file.write_bytes(b"temp content")

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        executor._cleanup_partial(temp_file)

        assert original_file.exists()
        assert original_file.read_bytes() == b"original content"


class TestIntegrityVerification:
    """T083: Unit tests for integrity verification."""

    def test_verify_empty_file_fails(self, tmp_path: Path) -> None:
        """Verification fails for empty file."""
        output_file = tmp_path / "empty.mkv"
        output_file.write_bytes(b"")

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        # Empty file should fail verification
        is_valid = executor._verify_output_integrity(output_file)
        assert is_valid is False

    def test_verify_nonexistent_file_fails(self, tmp_path: Path) -> None:
        """Verification fails for nonexistent file."""
        output_file = tmp_path / "missing.mkv"

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        is_valid = executor._verify_output_integrity(output_file)
        assert is_valid is False

    def test_verify_valid_file_passes(self, tmp_path: Path) -> None:
        """Verification passes for valid file with content."""
        output_file = tmp_path / "valid.mkv"
        # Write some non-empty content
        output_file.write_bytes(b"x" * 1000)

        policy = TranscodePolicyConfig(target_video_codec="hevc")
        executor = TranscodeExecutor(policy)

        # File with content should pass basic size verification
        is_valid = executor._verify_output_integrity(output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0
        assert is_valid is True
