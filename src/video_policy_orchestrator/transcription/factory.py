"""Factory for creating transcription plugin instances.

This module provides a factory pattern for obtaining transcriber instances,
replacing direct WhisperTranscriptionPlugin instantiation in CLI modules.
The factory uses a cached singleton pattern for efficiency.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_policy_orchestrator.transcription.interface import TranscriptionPlugin

logger = logging.getLogger(__name__)


class TranscriberUnavailableError(Exception):
    """Raised when transcriber is required but unavailable.

    Attributes:
        reason: Human-readable reason why transcriber is unavailable.
    """

    def __init__(self, reason: str) -> None:
        """Initialize with reason.

        Args:
            reason: Description of why the transcriber is unavailable.
        """
        self.reason = reason
        super().__init__(f"Transcriber unavailable: {reason}")


class TranscriberFactory:
    """Factory for creating transcriber instances with proper error handling.

    Uses a cached singleton pattern - the same transcriber instance is
    reused across all calls within a process. This is safe because
    transcription plugins are stateless for inference.

    Example:
        # Get transcriber if available (returns None if not)
        transcriber = TranscriberFactory.get_transcriber()
        if transcriber:
            result = transcriber.detect_language(file_path, track_index)

        # Get transcriber or raise (when transcriber is required)
        transcriber = TranscriberFactory.get_transcriber_or_raise(
            require_multi_language=True
        )
    """

    _instance: TranscriptionPlugin | None = None
    _initialization_error: str | None = None
    _initialized: bool = False

    @classmethod
    def get_transcriber(
        cls,
        require_multi_language: bool = False,
    ) -> TranscriptionPlugin | None:
        """Get a transcriber instance.

        Returns a cached transcriber instance, or None if no transcriber
        is available.

        Args:
            require_multi_language: If True, only return transcriber that
                supports the multi_language_detection feature.

        Returns:
            TranscriptionPlugin instance, or None if unavailable.
        """
        # Return cached instance if available and meets requirements
        if cls._instance is not None:
            if require_multi_language:
                if not cls._instance.supports_feature("multi_language_detection"):
                    return None
            return cls._instance

        # If already tried and failed, don't retry
        if cls._initialized and cls._initialization_error is not None:
            return None

        # Try to initialize
        cls._initialized = True
        try:
            from video_policy_orchestrator.transcription.registry import get_registry

            registry = get_registry()
            plugin = registry.get_default()

            if plugin is None:
                cls._initialization_error = (
                    "No transcription plugins available. "
                    "Install openai-whisper for local transcription."
                )
                return None

            if require_multi_language:
                if not plugin.supports_feature("multi_language_detection"):
                    cls._initialization_error = (
                        f"Plugin '{plugin.name}' does not support "
                        "multi_language_detection feature."
                    )
                    return None

            cls._instance = plugin
            logger.debug("Initialized transcriber: %s v%s", plugin.name, plugin.version)
            return plugin

        except Exception as e:
            cls._initialization_error = str(e)
            logger.warning("Failed to initialize transcriber: %s", e)
            return None

    @classmethod
    def get_transcriber_or_raise(
        cls,
        require_multi_language: bool = False,
    ) -> TranscriptionPlugin:
        """Get transcriber or raise if unavailable.

        Use this method when a transcriber is required for the operation
        to proceed. Raises a clear error if no transcriber is available.

        Args:
            require_multi_language: If True, require multi_language_detection
                feature support.

        Returns:
            TranscriptionPlugin instance.

        Raises:
            TranscriberUnavailableError: If no suitable transcriber available.
        """
        transcriber = cls.get_transcriber(require_multi_language)
        if transcriber is None:
            reason = cls._initialization_error or "Unknown error"
            raise TranscriberUnavailableError(reason)
        return transcriber

    @classmethod
    def is_available(cls, require_multi_language: bool = False) -> bool:
        """Check if a transcriber is available.

        Args:
            require_multi_language: If True, check for multi_language_detection
                feature support.

        Returns:
            True if a suitable transcriber is available.
        """
        return cls.get_transcriber(require_multi_language) is not None

    @classmethod
    def get_error(cls) -> str | None:
        """Get the initialization error message if any.

        Returns:
            Error message, or None if no error occurred.
        """
        return cls._initialization_error

    @classmethod
    def reset(cls) -> None:
        """Reset the cached instance.

        Primarily useful for testing to ensure clean state between tests.
        """
        cls._instance = None
        cls._initialization_error = None
        cls._initialized = False


# Convenience functions for common use cases


def get_transcriber(
    require_multi_language: bool = False,
) -> TranscriptionPlugin | None:
    """Get a transcriber instance (convenience function).

    Equivalent to TranscriberFactory.get_transcriber().

    Args:
        require_multi_language: If True, only return transcriber that
            supports multi_language_detection feature.

    Returns:
        TranscriptionPlugin instance, or None if unavailable.
    """
    return TranscriberFactory.get_transcriber(require_multi_language)


def get_transcriber_or_raise(
    require_multi_language: bool = False,
) -> TranscriptionPlugin:
    """Get transcriber or raise if unavailable (convenience function).

    Equivalent to TranscriberFactory.get_transcriber_or_raise().

    Args:
        require_multi_language: If True, require multi_language_detection.

    Returns:
        TranscriptionPlugin instance.

    Raises:
        TranscriberUnavailableError: If no suitable transcriber available.
    """
    return TranscriberFactory.get_transcriber_or_raise(require_multi_language)
