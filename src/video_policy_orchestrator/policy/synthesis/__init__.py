"""Audio synthesis module for Video Policy Orchestrator.

This module provides functionality for synthesizing new audio tracks from
existing sources via transcoding. It supports:

- Multiple codecs: EAC3, AAC, AC3, Opus, FLAC
- Channel downmixing with proper LFE handling
- Intelligent source track selection based on language, codec, channels
- Configurable track positioning
- Dry-run preview of synthesis operations

Key Components:
    models: Data models for synthesis configuration and plans
    exceptions: Custom exceptions for synthesis errors
    encoders: FFmpeg encoder detection and configuration
    downmix: Channel downmix filter generation
    source_selector: Source track selection algorithm
    planner: Synthesis plan generation
"""

from video_policy_orchestrator.policy.synthesis.exceptions import (
    EncoderUnavailableError,
    SynthesisError,
)
from video_policy_orchestrator.policy.synthesis.models import (
    AudioCodec,
    ChannelConfig,
    Position,
    PreferenceCriterion,
    SkippedSynthesis,
    SkipReason,
    SourcePreferences,
    SourceTrackSelection,
    SynthesisOperation,
    SynthesisPlan,
    SynthesisTrackDefinition,
)

__all__ = [
    # Exceptions
    "SynthesisError",
    "EncoderUnavailableError",
    # Models
    "AudioCodec",
    "ChannelConfig",
    "Position",
    "SynthesisTrackDefinition",
    "SourcePreferences",
    "PreferenceCriterion",
    "SourceTrackSelection",
    "SynthesisOperation",
    "SynthesisPlan",
    "SkippedSynthesis",
    "SkipReason",
]
