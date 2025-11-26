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
    executor: FFmpeg/mkvmerge execution

Usage:
    from video_policy_orchestrator.policy.synthesis import plan_synthesis
    from video_policy_orchestrator.policy.synthesis import execute_synthesis_plan

    plan = plan_synthesis(file_id, file_path, tracks, synthesis_config)
    result = execute_synthesis_plan(plan)
"""

from video_policy_orchestrator.policy.synthesis.exceptions import (
    DownmixNotSupportedError,
    EncoderUnavailableError,
    SourceTrackNotFoundError,
    SynthesisError,
)
from video_policy_orchestrator.policy.synthesis.executor import (
    FFmpegSynthesisExecutor,
    SynthesisExecutionResult,
    execute_synthesis_plan,
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
from video_policy_orchestrator.policy.synthesis.planner import plan_synthesis
from video_policy_orchestrator.policy.synthesis.source_selector import (
    select_source_track,
)

__all__ = [
    # Exceptions
    "SynthesisError",
    "EncoderUnavailableError",
    "SourceTrackNotFoundError",
    "DownmixNotSupportedError",
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
    # Functions
    "plan_synthesis",
    "select_source_track",
    "execute_synthesis_plan",
    # Executor
    "FFmpegSynthesisExecutor",
    "SynthesisExecutionResult",
]
