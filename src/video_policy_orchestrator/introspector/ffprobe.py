"""FFprobe-based implementation of MediaIntrospector protocol."""

import json
import shutil
import subprocess
from pathlib import Path

from video_policy_orchestrator.db.models import IntrospectionResult, TrackInfo
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError


class FFprobeIntrospector:
    """ffprobe-based implementation of MediaIntrospector protocol.

    Extracts track-level metadata from video files using ffprobe.
    """

    def __init__(self) -> None:
        """Initialize the introspector.

        Raises:
            MediaIntrospectionError: If ffprobe is not available.
        """
        if not self.is_available():
            raise MediaIntrospectionError(
                "ffprobe is not installed or not in PATH. "
                "Install ffmpeg to use media introspection features."
            )

    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is available on the system.

        Returns:
            True if ffprobe is found in PATH, False otherwise.
        """
        return shutil.which("ffprobe") is not None

    def get_file_info(self, path: Path) -> IntrospectionResult:
        """Extract metadata from a video file.

        Args:
            path: Path to the video file.

        Returns:
            IntrospectionResult containing file metadata and track information.

        Raises:
            MediaIntrospectionError: If the file cannot be introspected.
        """
        if not path.exists():
            raise MediaIntrospectionError(f"File not found: {path}")

        try:
            ffprobe_output = self._run_ffprobe(path)
        except subprocess.CalledProcessError as e:
            raise MediaIntrospectionError(
                f"ffprobe failed for {path}: {e.stderr or e}"
            ) from e
        except json.JSONDecodeError as e:
            raise MediaIntrospectionError(
                f"Invalid ffprobe output for {path}: {e}"
            ) from e

        return self._parse_output(path, ffprobe_output)

    def _run_ffprobe(self, path: Path) -> dict:
        """Run ffprobe and return parsed JSON output.

        Args:
            path: Path to the video file.

        Returns:
            Parsed JSON output from ffprobe.

        Raises:
            subprocess.CalledProcessError: If ffprobe returns non-zero.
            json.JSONDecodeError: If output is not valid JSON.
        """
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def _parse_output(self, path: Path, data: dict) -> IntrospectionResult:
        """Parse ffprobe JSON output into IntrospectionResult.

        Args:
            path: Path to the video file.
            data: Parsed ffprobe JSON output.

        Returns:
            IntrospectionResult with tracks and warnings.
        """
        warnings: list[str] = []

        # Extract container format
        format_info = data.get("format", {})
        container_format = format_info.get("format_name")

        # Parse streams
        streams = data.get("streams", [])
        tracks = self._parse_streams(streams, warnings)

        if not tracks:
            warnings.append("No streams found in file")

        return IntrospectionResult(
            file_path=path,
            container_format=container_format,
            tracks=tracks,
            warnings=warnings,
        )

    def _parse_streams(
        self, streams: list[dict], warnings: list[str]
    ) -> list[TrackInfo]:
        """Parse stream data into TrackInfo objects.

        Args:
            streams: List of stream dictionaries from ffprobe.
            warnings: List to append warnings to.

        Returns:
            List of TrackInfo objects.
        """
        tracks: list[TrackInfo] = []
        seen_indices: set[int] = set()

        for stream in streams:
            index = stream.get("index", 0)

            # Check for duplicate indices
            if index in seen_indices:
                warnings.append(f"Duplicate stream index {index}, skipping")
                continue
            seen_indices.add(index)

            codec_type = stream.get("codec_type", "")
            track_type = self._map_track_type(codec_type)

            # Get disposition flags
            disposition = stream.get("disposition", {})
            is_default = disposition.get("default", 0) == 1
            is_forced = disposition.get("forced", 0) == 1

            # Get tags
            tags = stream.get("tags", {})
            language = tags.get("language") or "und"
            title = tags.get("title")

            # Build track info
            track = TrackInfo(
                index=index,
                track_type=track_type,
                codec=stream.get("codec_name"),
                language=language,
                title=title,
                is_default=is_default,
                is_forced=is_forced,
            )

            # Add audio-specific fields
            if track_type == "audio":
                channels = stream.get("channels")
                if channels is not None:
                    track.channels = channels
                    track.channel_layout = self._map_channel_layout(channels)

            # Add video-specific fields
            if track_type == "video":
                width = stream.get("width")
                height = stream.get("height")
                if width is not None:
                    track.width = width
                if height is not None:
                    track.height = height
                # Get frame rate (prefer r_frame_rate, fallback to avg_frame_rate)
                frame_rate = stream.get("r_frame_rate") or stream.get("avg_frame_rate")
                if frame_rate and frame_rate != "0/0":
                    track.frame_rate = frame_rate

            tracks.append(track)

        return tracks

    @staticmethod
    def _map_track_type(codec_type: str) -> str:
        """Map ffprobe codec_type to VPO track type.

        Args:
            codec_type: The codec_type from ffprobe.

        Returns:
            VPO track type string.
        """
        mapping = {
            "video": "video",
            "audio": "audio",
            "subtitle": "subtitle",
            "attachment": "attachment",
        }
        return mapping.get(codec_type, "other")

    @staticmethod
    def _map_channel_layout(channels: int) -> str:
        """Map channel count to human-readable label.

        Args:
            channels: Number of audio channels.

        Returns:
            Human-readable channel layout string.
        """
        mapping = {
            1: "mono",
            2: "stereo",
            6: "5.1",
            8: "7.1",
        }
        return mapping.get(channels, f"{channels}ch")
