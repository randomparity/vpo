"""Custom exceptions for audio synthesis operations.

This module defines exceptions specific to audio synthesis that provide
clear, actionable error messages to users.
"""


class SynthesisError(Exception):
    """Base exception for audio synthesis errors.

    Raised when a synthesis operation fails due to invalid configuration,
    missing requirements, or execution errors.
    """

    def __init__(self, message: str, definition_name: str | None = None) -> None:
        """Initialize synthesis error.

        Args:
            message: Human-readable error description.
            definition_name: Name of the synthesis definition that failed.
        """
        self.message = message
        self.definition_name = definition_name
        super().__init__(message)


class EncoderUnavailableError(SynthesisError):
    """Raised when a required FFmpeg encoder is not available.

    This typically occurs when FFmpeg is not compiled with support for
    the requested codec (e.g., libfdk_aac requires a custom FFmpeg build).
    """

    def __init__(self, encoder: str, codec: str) -> None:
        """Initialize encoder unavailable error.

        Args:
            encoder: The FFmpeg encoder name that is missing.
            codec: The target codec that requires this encoder.
        """
        self.encoder = encoder
        self.codec = codec
        message = (
            f"FFmpeg encoder '{encoder}' is not available for codec '{codec}'. "
            f"Ensure FFmpeg is installed with support for this encoder."
        )
        super().__init__(message)


class SourceTrackNotFoundError(SynthesisError):
    """Raised when no suitable source track can be found for synthesis.

    This occurs when the file has no audio tracks, or none meet the
    minimum requirements for synthesis (e.g., sufficient channel count).
    """

    def __init__(
        self,
        definition_name: str,
        reason: str,
    ) -> None:
        """Initialize source track not found error.

        Args:
            definition_name: Name of the synthesis definition.
            reason: Why no source track could be found.
        """
        self.reason = reason
        message = f"No suitable source track found for '{definition_name}': {reason}"
        super().__init__(message, definition_name=definition_name)


class DownmixNotSupportedError(SynthesisError):
    """Raised when attempting to upmix (increase channel count).

    Synthesis only supports downmixing (reducing channels) or maintaining
    the same channel count. Upmixing would require artificial channel
    synthesis which is not supported.
    """

    def __init__(
        self,
        source_channels: int,
        target_channels: int,
        definition_name: str | None = None,
    ) -> None:
        """Initialize downmix not supported error.

        Args:
            source_channels: Number of channels in source track.
            target_channels: Requested number of output channels.
            definition_name: Name of the synthesis definition.
        """
        self.source_channels = source_channels
        self.target_channels = target_channels
        message = (
            f"Cannot upmix from {source_channels} to {target_channels} channels. "
            "Synthesis only supports downmixing or maintaining channel count."
        )
        super().__init__(message, definition_name=definition_name)


class SynthesisCancelledError(SynthesisError):
    """Raised when synthesis is cancelled via SIGINT (Ctrl+C).

    The executor handles this exception by:
    1. Stopping any in-progress operations
    2. Restoring the original file from backup if modifications had started
    3. Cleaning up temporary files
    """

    def __init__(self, message: str = "Synthesis cancelled by user") -> None:
        """Initialize cancellation error.

        Args:
            message: Human-readable cancellation message.
        """
        super().__init__(message)
