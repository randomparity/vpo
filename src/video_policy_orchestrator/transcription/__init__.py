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
from video_policy_orchestrator.transcription.service import (
    TranscriptionContext,
    TranscriptionSetupError,
    prepare_transcription_context,
    should_skip_track,
)

__all__ = [
    "TrackClassification",
    "TranscriptionConfig",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionResult",
    # Coordinator (primary API for plugin-based transcription)
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "NoTranscriptionPluginError",
    "PluginTranscriberAdapter",
    "TranscriptionCoordinator",
    "TranscriptionCoordinatorResult",
    "TranscriptionOptions",
    # Service layer (legacy - use Coordinator for new code)
    "TranscriptionContext",
    "TranscriptionSetupError",
    "prepare_transcription_context",
    "should_skip_track",
]
