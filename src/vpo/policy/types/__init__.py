"""Policy type definitions package.

All types are re-exported for backward compatibility.
Import from vpo.policy.types to access any type.
"""

# Core enums and constants (extracted)
# Action types (extracted)
from vpo.policy.types.actions import (
    ConditionalAction,
    ConditionalResult,
    ConditionalRule,
    FailAction,
    PluginMetadataReference,
    RuleEvaluation,
    SetDefaultAction,
    SetForcedAction,
    SetLanguageAction,
    SkipAction,
    SkipFlags,
    SkipType,
    TrackFlagChange,
    TrackLanguageChange,
    WarnAction,
)

# Condition types (extracted)
from vpo.policy.types.conditions import (
    AndCondition,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    Condition,
    CountCondition,
    ExistsCondition,
    IsDubbedCondition,
    IsOriginalCondition,
    NotCondition,
    OrCondition,
    PluginMetadataCondition,
    PluginMetadataOperator,
    TitleMatch,
    TrackFilters,
)
from vpo.policy.types.enums import (
    CANONICAL_OPERATION_ORDER,
    DEFAULT_TRACK_ORDER,
    MP4_INCOMPATIBLE_CODECS,
    RESOLUTION_MAP,
    VALID_AUDIO_CODECS,
    VALID_RESOLUTIONS,
    VALID_VIDEO_CODECS,
    ActionType,
    OnErrorMode,
    OperationType,
    PhaseOutcome,
    SkipReasonType,
    TrackType,
)

# Filter configuration types (extracted)
from vpo.policy.types.filters import (
    AttachmentFilterConfig,
    AudioActionsConfig,
    AudioFilterConfig,
    ContainerConfig,
    DefaultFlagsConfig,
    FileTimestampConfig,
    LanguageFallbackConfig,
    SubtitleActionsConfig,
    SubtitleFilterConfig,
    TranscriptionPolicyOptions,
)

# Plan and execution types (extracted)
from vpo.policy.types.plan import (
    ContainerChange,
    ContainerTranscodePlan,
    FileProcessingResult,
    IncompatibleTrackPlan,
    PhaseExecutionContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseSkipCondition,
    Plan,
    PlannedAction,
    RunIfCondition,
    SkipReason,
    TrackDisposition,
)

# Schema types (extracted)
from vpo.policy.types.schema import (
    AudioSynthesisConfig,
    EvaluationPolicy,
    GlobalConfig,
    PhaseDefinition,
    PolicySchema,
    SkipIfExistsCriteria,
    SynthesisTrackDefinitionRef,
)

# Transcode configuration types (extracted)
from vpo.policy.types.transcode import (
    DEFAULT_CRF_VALUES,
    VALID_PRESETS,
    X264_X265_TUNES,
    AudioPreservationRule,
    AudioTrackAction,
    AudioTranscodeConfig,
    HardwareAccelConfig,
    HardwareAccelMode,
    QualityMode,
    QualitySettings,
    ScaleAlgorithm,
    ScalingSettings,
    SkipCondition,
    TranscodePolicyConfig,
    VideoTranscodeAction,
    VideoTranscodeConfig,
    VideoTranscodeResult,
    get_default_crf,
    parse_bitrate,
)

__all__ = [
    # Core enums
    "TrackType",
    "ActionType",
    "OperationType",
    "OnErrorMode",
    "PhaseOutcome",
    "SkipReasonType",
    # Constants
    "DEFAULT_TRACK_ORDER",
    "CANONICAL_OPERATION_ORDER",
    "VALID_VIDEO_CODECS",
    "VALID_AUDIO_CODECS",
    "VALID_RESOLUTIONS",
    "RESOLUTION_MAP",
    "MP4_INCOMPATIBLE_CODECS",
    # Transcode enums
    "QualityMode",
    "ScaleAlgorithm",
    "HardwareAccelMode",
    # Transcode constants
    "VALID_PRESETS",
    "X264_X265_TUNES",
    "DEFAULT_CRF_VALUES",
    # Transcode functions
    "parse_bitrate",
    "get_default_crf",
    # Transcode types
    "SkipCondition",
    "QualitySettings",
    "ScalingSettings",
    "HardwareAccelConfig",
    "AudioTranscodeConfig",
    "VideoTranscodeConfig",
    "VideoTranscodeAction",
    "VideoTranscodeResult",
    "AudioTrackAction",
    "TranscodePolicyConfig",
    "AudioPreservationRule",
    # Filter types
    "LanguageFallbackConfig",
    "AudioFilterConfig",
    "SubtitleFilterConfig",
    "AttachmentFilterConfig",
    "AudioActionsConfig",
    "SubtitleActionsConfig",
    "ContainerConfig",
    "DefaultFlagsConfig",
    "FileTimestampConfig",
    "TranscriptionPolicyOptions",
    # Condition enums
    "ComparisonOperator",
    "PluginMetadataOperator",
    # Condition types
    "Comparison",
    "TitleMatch",
    "TrackFilters",
    "ExistsCondition",
    "CountCondition",
    "AndCondition",
    "OrCondition",
    "NotCondition",
    "AudioIsMultiLanguageCondition",
    "PluginMetadataCondition",
    "IsOriginalCondition",
    "IsDubbedCondition",
    "Condition",
    # Action enums
    "SkipType",
    # Action types
    "SkipAction",
    "WarnAction",
    "FailAction",
    "SetForcedAction",
    "SetDefaultAction",
    "PluginMetadataReference",
    "SetLanguageAction",
    "ConditionalAction",
    # Rule types
    "ConditionalRule",
    "RuleEvaluation",
    "TrackFlagChange",
    "TrackLanguageChange",
    "SkipFlags",
    "ConditionalResult",
    # Plan types
    "TrackDisposition",
    "IncompatibleTrackPlan",
    "ContainerTranscodePlan",
    "ContainerChange",
    "PlannedAction",
    "Plan",
    "SkipReason",
    "PhaseSkipCondition",
    "RunIfCondition",
    "PhaseResult",
    "FileProcessingResult",
    "PhaseExecutionContext",
    "PhaseExecutionError",
    # Schema types
    "GlobalConfig",
    "AudioSynthesisConfig",
    "SkipIfExistsCriteria",
    "SynthesisTrackDefinitionRef",
    "PhaseDefinition",
    "EvaluationPolicy",
    "PolicySchema",
]
