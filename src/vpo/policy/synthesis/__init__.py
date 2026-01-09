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
    from vpo.policy.synthesis import plan_synthesis
    from vpo.policy.synthesis import execute_synthesis_plan

    plan = plan_synthesis(file_id, file_path, tracks, synthesis_config)
    result = execute_synthesis_plan(plan)
"""

from vpo.policy.synthesis.exceptions import (
    DownmixNotSupportedError,
    EncoderUnavailableError,
    SourceTrackNotFoundError,
    SynthesisCancelledError,
    SynthesisError,
)
from vpo.policy.synthesis.executor import (
    FFmpegSynthesisExecutor,
    SynthesisExecutionResult,
    execute_synthesis_plan,
)
from vpo.policy.synthesis.models import (
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
from vpo.policy.synthesis.planner import (
    format_final_track_order,
    format_synthesis_plan,
    plan_synthesis,
)
from vpo.policy.synthesis.source_selector import (
    select_source_track,
)

__all__ = [
    # Exceptions
    "SynthesisError",
    "SynthesisCancelledError",
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
    "format_synthesis_plan",
    "format_final_track_order",
    # Executor
    "FFmpegSynthesisExecutor",
    "SynthesisExecutionResult",
]
