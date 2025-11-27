"""FFprobe-based implementation of MediaIntrospector protocol."""

import json
import subprocess  # nosec B404 - subprocess is required for ffprobe invocation
from pathlib import Path

from video_policy_orchestrator.db.models import IntrospectionResult, TrackInfo
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError
from video_policy_orchestrator.language import normalize_language


class FFprobeIntrospector:
    """ffprobe-based implementation of MediaIntrospector protocol.

    Extracts track-level metadata from video files using ffprobe.
    Supports configured ffprobe paths via VPO configuration system.
    """

    def __init__(self, ffprobe_path: Path | None = None) -> None:
        """Initialize the introspector.

        Args:
            ffprobe_path: Optional explicit path to ffprobe. If not provided,
                uses the path from VPO configuration or system PATH.

        Raises:
            MediaIntrospectionError: If ffprobe is not available.
        """
        self._ffprobe_path = ffprobe_path or self._get_configured_path()

        if self._ffprobe_path is None:
            raise MediaIntrospectionError(
                "ffprobe is not installed or not in PATH. "
                "Install ffmpeg to use media introspection features. "
                "You can also configure a custom path via VPO_FFPROBE_PATH "
                "environment variable or ~/.vpo/config.toml"
            )

    @staticmethod
    def _get_configured_path() -> Path | None:
        """Get ffprobe path from configuration.

        Returns:
            Configured path or None if not available.
        """
        from video_policy_orchestrator.executor.interface import get_tool_path

        return get_tool_path("ffprobe")

    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is available on the system.

        Uses configuration-aware detection.

        Returns:
            True if ffprobe is available, False otherwise.
        """
        from video_policy_orchestrator.executor.interface import check_tool_availability

        return check_tool_availability().get("ffprobe", False)

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
        result = subprocess.run(  # nosec B603 - ffprobe path is validated
            [
                str(self._ffprobe_path),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            errors="replace",  # Handle non-UTF8 characters by replacing them
            check=True,
        )
        return json.loads(result.stdout)

    @staticmethod
    def _sanitize_string(value: str | None) -> str | None:
        """Sanitize a string by replacing invalid characters.

        Args:
            value: String value to sanitize.

        Returns:
            Sanitized string or None if input was None.
        """
        if value is None:
            return None
        # Replace any remaining problematic characters
        return value.encode("utf-8", errors="replace").decode("utf-8")

    def _parse_output(self, path: Path, data: dict) -> IntrospectionResult:
        """Parse ffprobe JSON output into IntrospectionResult.

        Args:
            path: Path to the video file.
            data: Parsed ffprobe JSON output.

        Returns:
            IntrospectionResult with tracks and warnings.
        """
        warnings: list[str] = []

        # Extract container format and duration
        format_info = data.get("format", {})
        container_format = format_info.get("format_name")
        # Container duration (used as fallback for streams without duration)
        container_duration = self._parse_duration(format_info.get("duration"))

        # Parse streams
        streams = data.get("streams", [])
        tracks = self._parse_streams(streams, warnings, container_duration)

        if not tracks:
            warnings.append("No streams found in file")

        return IntrospectionResult(
            file_path=path,
            container_format=container_format,
            tracks=tracks,
            warnings=warnings,
        )

    def _parse_streams(
        self,
        streams: list[dict],
        warnings: list[str],
        container_duration: float | None = None,
    ) -> list[TrackInfo]:
        """Parse stream data into TrackInfo objects.

        Args:
            streams: List of stream dictionaries from ffprobe.
            warnings: List to append warnings to.
            container_duration: Container-level duration as fallback.

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

            # Get tags (sanitize strings to handle non-UTF8 characters)
            tags = stream.get("tags", {})
            raw_language = tags.get("language") or "und"
            # Normalize language code to configured standard (default: ISO 639-2/B)
            language = normalize_language(raw_language)
            title = self._sanitize_string(tags.get("title"))

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

            # Extract stream duration (fall back to container duration)
            stream_duration = self._parse_duration(stream.get("duration"))
            if stream_duration is not None:
                track.duration_seconds = stream_duration
            elif container_duration is not None:
                track.duration_seconds = container_duration

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
                # Extract HDR color metadata
                color_transfer = stream.get("color_transfer")
                if color_transfer:
                    track.color_transfer = color_transfer
                color_primaries = stream.get("color_primaries")
                if color_primaries:
                    track.color_primaries = color_primaries
                color_space = stream.get("color_space")
                if color_space:
                    track.color_space = color_space
                color_range = stream.get("color_range")
                if color_range:
                    track.color_range = color_range

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

    @staticmethod
    def _parse_duration(value: str | None) -> float | None:
        """Parse duration string from ffprobe into seconds.

        Args:
            value: Duration string from ffprobe (e.g., "3600.000") or None.

        Returns:
            Duration in seconds as float, or None if parsing fails.
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
