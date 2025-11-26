"""Audio transcription and language detection module for VPO."""

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
    get_existing_transcription,
    prepare_transcription_context,
    should_skip_track,
)

__all__ = [
    "TrackClassification",
    "TranscriptionConfig",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionResult",
    # Service layer
    "TranscriptionContext",
    "TranscriptionSetupError",
    "prepare_transcription_context",
    "get_existing_transcription",
    "should_skip_track",
]
