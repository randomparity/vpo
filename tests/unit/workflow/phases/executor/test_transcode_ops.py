"""Tests for temp directory fallback in audio-only transcode."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.db import TrackInfo
from vpo.policy.transcode import AudioAction, AudioPlan, AudioTrackPlan
from vpo.workflow.phases.executor.transcode_ops import execute_audio_only_transcode

MODULE = "vpo.workflow.phases.executor.transcode_ops"


def _make_audio_track(index: int = 1, codec: str = "ac3") -> TrackInfo:
    """Create a minimal audio TrackInfo for testing."""
    return TrackInfo(
        index=index,
        track_type="audio",
        codec=codec,
        language="eng",
        channels=6,
    )


def _make_audio_plan(codec: str = "aac") -> AudioPlan:
    """Create an AudioPlan with one track to transcode."""
    return AudioPlan(
        tracks=[
            AudioTrackPlan(
                track_index=1,
                stream_index=0,
                codec="ac3",
                language="eng",
                channels=6,
                channel_layout="5.1",
                action=AudioAction.TRANSCODE,
                target_codec=codec,
                target_bitrate="192k",
            ),
        ],
    )


class TestAudioTranscodeTempDirectory:
    """Tests for temp directory fallback in audio-only transcode."""

    def test_temp_file_in_source_parent_when_unconfigured(self, tmp_path: Path) -> None:
        """Temp file created in source parent when temp dir unconfigured."""
        file_path = tmp_path / "movie.mkv"
        file_path.write_bytes(b"x" * 1000)
        tracks = [_make_audio_track()]
        audio_plan = _make_audio_plan()

        mock_tmp_ctx = MagicMock()
        mock_tmp_ctx.name = str(tmp_path / "tmpfile.mkv")

        with (
            patch(
                f"{MODULE}.get_temp_directory_for_file",
                return_value=file_path.parent,
            ) as mock_get_temp,
            patch(f"{MODULE}.check_disk_space"),
            patch(f"{MODULE}.require_tool", return_value=Path("/usr/bin/ffmpeg")),
            patch(
                f"{MODULE}.executor_create_backup",
                return_value=tmp_path / "movie.bak.mkv",
            ),
            patch(f"{MODULE}.tempfile.NamedTemporaryFile") as mock_tmpfile,
        ):
            mock_tmpfile.return_value.__enter__ = MagicMock(return_value=mock_tmp_ctx)
            mock_tmpfile.return_value.__exit__ = MagicMock(return_value=False)

            # Will fail at subprocess.run (not patched), but we only need to
            # reach the NamedTemporaryFile call. Catch any downstream error.
            try:
                execute_audio_only_transcode(file_path, tracks, audio_plan, "aac")
            except Exception:
                pass

        mock_get_temp.assert_called_once_with(file_path)
        mock_tmpfile.assert_called_once_with(
            suffix=".mkv",
            delete=False,
            dir=file_path.parent,
        )

    def test_temp_file_in_configured_dir(self, tmp_path: Path) -> None:
        """Temp file created in configured dir when available."""
        file_path = tmp_path / "movie.mkv"
        file_path.write_bytes(b"x" * 1000)
        custom_temp = tmp_path / "custom_temp"
        custom_temp.mkdir()
        tracks = [_make_audio_track()]
        audio_plan = _make_audio_plan()

        mock_tmp_ctx = MagicMock()
        mock_tmp_ctx.name = str(custom_temp / "tmpfile.mkv")

        with (
            patch(
                f"{MODULE}.get_temp_directory_for_file",
                return_value=custom_temp,
            ) as mock_get_temp,
            patch(f"{MODULE}.check_disk_space"),
            patch(f"{MODULE}.require_tool", return_value=Path("/usr/bin/ffmpeg")),
            patch(
                f"{MODULE}.executor_create_backup",
                return_value=tmp_path / "movie.bak.mkv",
            ),
            patch(f"{MODULE}.tempfile.NamedTemporaryFile") as mock_tmpfile,
        ):
            mock_tmpfile.return_value.__enter__ = MagicMock(return_value=mock_tmp_ctx)
            mock_tmpfile.return_value.__exit__ = MagicMock(return_value=False)

            try:
                execute_audio_only_transcode(file_path, tracks, audio_plan, "aac")
            except Exception:
                pass

        mock_get_temp.assert_called_once_with(file_path)
        mock_tmpfile.assert_called_once_with(
            suffix=".mkv",
            delete=False,
            dir=custom_temp,
        )
