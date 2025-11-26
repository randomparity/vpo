"""Custom exceptions for policy operations.

This module defines exceptions for track filtering and container conversion
operations that may fail due to policy constraints.
"""


class PolicyError(Exception):
    """Base class for policy-related errors."""

    pass


class InsufficientTracksError(PolicyError):
    """Raised when track filtering would leave insufficient tracks.

    This error is raised when applying a track filter would result in fewer
    tracks than the minimum required. For audio tracks, at least one track
    must always remain to avoid creating audio-less files.
    """

    def __init__(
        self,
        track_type: str,
        required: int,
        available: int,
        policy_languages: tuple[str, ...],
        file_languages: tuple[str, ...],
    ) -> None:
        """Initialize the error.

        Args:
            track_type: The type of track being filtered (e.g., "audio", "subtitle").
            required: The minimum number of tracks required.
            available: The number of tracks that would remain after filtering.
            policy_languages: The language codes specified in the policy filter.
            file_languages: The language codes present in the file's tracks.
        """
        self.track_type = track_type
        self.required = required
        self.available = available
        self.policy_languages = policy_languages
        self.file_languages = file_languages
        super().__init__(
            f"Filtering {track_type} tracks would leave {available} tracks, "
            f"but minimum {required} required. "
            f"Policy languages: {policy_languages}, "
            f"File has: {file_languages}"
        )


class IncompatibleCodecError(PolicyError):
    """Raised when source codecs are incompatible with target container.

    This error is raised when attempting to convert to a container format
    that does not support one or more codecs present in the source file.
    For example, TrueHD audio cannot be stored in MP4 containers.
    """

    def __init__(
        self,
        target_container: str,
        incompatible_tracks: list[tuple[int, str, str]],  # (index, type, codec)
    ) -> None:
        """Initialize the error.

        Args:
            target_container: The target container format (e.g., "mp4").
            incompatible_tracks: List of (track_index, track_type, codec) tuples
                for each incompatible track.
        """
        self.target_container = target_container
        self.incompatible_tracks = incompatible_tracks
        track_list = ", ".join(
            f"#{idx} ({ttype}: {codec})" for idx, ttype, codec in incompatible_tracks
        )
        super().__init__(
            f"Cannot convert to {target_container}: incompatible tracks: {track_list}"
        )


class ConditionalFailError(PolicyError):
    """Raised when a conditional rule's fail action is triggered.

    This error is raised during policy evaluation when a conditional rule
    matches and its action specifies fail with a message. This allows policies
    to halt processing based on file characteristics.
    """

    def __init__(
        self,
        rule_name: str,
        message: str,
        file_path: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            rule_name: Name of the conditional rule that triggered the failure.
            message: The fail message from the rule (with placeholders substituted).
            file_path: Path to the file being processed, if available.
        """
        self.rule_name = rule_name
        self.message = message
        self.file_path = file_path
        error_msg = f"Rule '{rule_name}' triggered fail action: {message}"
        if file_path:
            error_msg += f" (file: {file_path})"
        super().__init__(error_msg)
