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

__all__ = [
    "TrackClassification",
    "TranscriptionConfig",
    "TranscriptionError",
    "TranscriptionPlugin",
    "TranscriptionResult",
]
