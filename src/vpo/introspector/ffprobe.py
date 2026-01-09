"""FFprobe-based implementation of MediaIntrospector protocol."""

import json
import subprocess  # nosec B404 - subprocess is required for ffprobe invocation
from pathlib import Path

from vpo.db.types import IntrospectionResult
from vpo.introspector.interface import MediaIntrospectionError
from vpo.introspector.parsers import parse_ffprobe_output


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
        from vpo.executor.interface import get_tool_path

        return get_tool_path("ffprobe")

    @staticmethod
    def is_available() -> bool:
        """Check if ffprobe is available on the system.

        Uses configuration-aware detection.

        Returns:
            True if ffprobe is available, False otherwise.
        """
        from vpo.executor.interface import check_tool_availability

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
        except subprocess.TimeoutExpired as e:
            raise MediaIntrospectionError(
                f"ffprobe timed out for {path} after {e.timeout}s"
            ) from e
        except subprocess.CalledProcessError as e:
            raise MediaIntrospectionError(
                f"ffprobe failed for {path}: {e.stderr or e}"
            ) from e
        except json.JSONDecodeError as e:
            raise MediaIntrospectionError(
                f"Invalid ffprobe output for {path}: {e}"
            ) from e

        return parse_ffprobe_output(path, ffprobe_output)

    def _run_ffprobe(self, path: Path) -> dict:
        """Run ffprobe and return parsed JSON output.

        Args:
            path: Path to the video file.

        Returns:
            Parsed JSON output from ffprobe.

        Raises:
            subprocess.CalledProcessError: If ffprobe returns non-zero.
            json.JSONDecodeError: If output is not valid JSON.
            MediaIntrospectionError: If output is missing required keys.
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
            timeout=60,  # Prevent hangs on corrupted files
        )
        data = json.loads(result.stdout)

        # Validate required keys are present
        if "streams" not in data:
            raise MediaIntrospectionError(
                f"Missing 'streams' in ffprobe output for {path}. "
                "File may be corrupted or not a valid media file."
            )
        if "format" not in data:
            raise MediaIntrospectionError(
                f"Missing 'format' in ffprobe output for {path}. "
                "File may be corrupted or not a valid media file."
            )

        return data
