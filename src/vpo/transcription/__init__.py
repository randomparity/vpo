"""Audio transcription and language detection module for VPO."""

from vpo.transcription.coordinator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    NoTranscriptionPluginError,
    PluginTranscriberAdapter,
    TranscriptionCoordinator,
    TranscriptionCoordinatorResult,
    TranscriptionOptions,
)
from vpo.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)
from vpo.transcription.models import (
    TrackClassification,
    TranscriptionConfig,
    TranscriptionResult,
)

__all__ = [
    "TrackClassification",
    "TranscriptionConfig",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionResult",
    # Coordinator API (the only supported transcription interface)
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "NoTranscriptionPluginError",
    "PluginTranscriberAdapter",
    "TranscriptionCoordinator",
    "TranscriptionCoordinatorResult",
    "TranscriptionOptions",
]
