"""FFprobe-based implementation of MediaIntrospector protocol."""

import json
import subprocess  # nosec B404 - subprocess is required for ffprobe invocation
from pathlib import Path

from video_policy_orchestrator.db.models import IntrospectionResult
from video_policy_orchestrator.introspector.interface import MediaIntrospectionError
from video_policy_orchestrator.introspector.mappings import (
    map_channel_layout,
    map_track_type,
)
from video_policy_orchestrator.introspector.parsers import (
    parse_duration,
    parse_ffprobe_output,
    sanitize_string,
)


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

        Delegates to the pure function in parsers module.

        Args:
            value: String value to sanitize.

        Returns:
            Sanitized string or None if input was None.
        """
        return sanitize_string(value)

    def _parse_output(self, path: Path, data: dict) -> IntrospectionResult:
        """Parse ffprobe JSON output into IntrospectionResult.

        Delegates to the pure function in parsers module.

        Args:
            path: Path to the video file.
            data: Parsed ffprobe JSON output.

        Returns:
            IntrospectionResult with tracks and warnings.
        """
        return parse_ffprobe_output(path, data)

    @staticmethod
    def _map_track_type(codec_type: str) -> str:
        """Map ffprobe codec_type to VPO track type.

        Delegates to the pure function in mappings module.

        Args:
            codec_type: The codec_type from ffprobe.

        Returns:
            VPO track type string.
        """
        return map_track_type(codec_type)

    @staticmethod
    def _map_channel_layout(channels: int) -> str:
        """Map channel count to human-readable label.

        Delegates to the pure function in mappings module.

        Args:
            channels: Number of audio channels.

        Returns:
            Human-readable channel layout string.
        """
        return map_channel_layout(channels)

    @staticmethod
    def _parse_duration(value: str | None) -> float | None:
        """Parse duration string from ffprobe into seconds.

        Delegates to the pure function in parsers module.

        Args:
            value: Duration string from ffprobe (e.g., "3600.000") or None.

        Returns:
            Duration in seconds as float, or None if parsing fails.
        """
        return parse_duration(value)
