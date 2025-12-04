"""Audio transcription and language detection module for VPO."""

from video_policy_orchestrator.transcription.coordinator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    NoTranscriptionPluginError,
    PluginTranscriberAdapter,
    TranscriptionCoordinator,
    TranscriptionCoordinatorResult,
    TranscriptionOptions,
)
from video_policy_orchestrator.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)
from video_policy_orchestrator.transcription.models import (
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
