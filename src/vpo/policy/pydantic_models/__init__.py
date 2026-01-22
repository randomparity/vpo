"""Pydantic models for policy YAML parsing and validation.

This package contains all Pydantic BaseModel subclasses used to parse and
validate YAML policy files. All models are frozen (immutable) and can be
used directly at runtime.

Package structure:
- base: Exception, constants, shared validators
- config: Configuration models (DefaultFlagsModel, TranscriptionPolicyModel, etc.)
- transcode: V6 transcode models
- filters: Track filtering models
- conditions: Condition models for conditional rules
- actions: Action models for conditional rules
- synthesis: Audio synthesis models
- phases: Phase and policy models
"""

# =============================================================================
# Base Components
# =============================================================================
# =============================================================================
# Action Models
# =============================================================================
from vpo.policy.pydantic_models.actions import (
    ActionModel,
    ConditionalRuleModel,
    PluginMetadataReferenceModel,
    SetDefaultActionModel,
    SetForcedActionModel,
    SetLanguageActionModel,
)
from vpo.policy.pydantic_models.base import (
    PHASE_NAME_PATTERN,
    RESERVED_PHASE_NAMES,
    VALID_CHANNEL_CONFIGS,
    VALID_SYNTHESIS_CODECS,
    PolicyValidationError,
    _validate_language_codes,
)

# =============================================================================
# Condition Models
# =============================================================================
from vpo.policy.pydantic_models.conditions import (
    AudioIsMultiLanguageModel,
    ComparisonModel,
    ConditionModel,
    CountConditionModel,
    ExistsConditionModel,
    IsDubbedConditionModel,
    IsOriginalConditionModel,
    PluginMetadataConditionModel,
    TitleMatchModel,
    TrackFiltersModel,
)

# =============================================================================
# Configuration Models
# =============================================================================
from vpo.policy.pydantic_models.config import (
    DefaultFlagsModel,
    TranscodePolicyModel,
    TranscriptionPolicyModel,
)

# =============================================================================
# Track Filtering Models
# =============================================================================
from vpo.policy.pydantic_models.filters import (
    AttachmentFilterModel,
    AudioActionsModel,
    AudioFilterModel,
    ContainerModel,
    FileTimestampModel,
    LanguageFallbackModel,
    SubtitleActionsModel,
    SubtitleFilterModel,
)

# =============================================================================
# Phase and Policy Models
# =============================================================================
from vpo.policy.pydantic_models.phases import (
    GlobalConfigModel,
    PhaseModel,
    PhaseSkipConditionModel,
    PolicyModel,
    RunIfConditionModel,
)

# =============================================================================
# Audio Synthesis Models
# =============================================================================
from vpo.policy.pydantic_models.synthesis import (
    AudioSynthesisModel,
    ChannelPreferenceModel,
    PreferenceCriterionModel,
    SkipIfExistsModel,
    SourcePreferencesModel,
    SynthesisTrackDefinitionModel,
)

# =============================================================================
# V6 Transcode Models
# =============================================================================
from vpo.policy.pydantic_models.transcode import (
    AudioTranscodeConfigModel,
    HardwareAccelConfigModel,
    QualitySettingsModel,
    ScalingSettingsModel,
    SkipConditionModel,
    TranscodeV6Model,
    VideoTranscodeConfigModel,
)

__all__ = [
    # Base
    "PolicyValidationError",
    "RESERVED_PHASE_NAMES",
    "PHASE_NAME_PATTERN",
    "VALID_SYNTHESIS_CODECS",
    "VALID_CHANNEL_CONFIGS",
    "_validate_language_codes",
    # Config
    "DefaultFlagsModel",
    "TranscriptionPolicyModel",
    "TranscodePolicyModel",
    # Transcode
    "SkipConditionModel",
    "QualitySettingsModel",
    "ScalingSettingsModel",
    "HardwareAccelConfigModel",
    "VideoTranscodeConfigModel",
    "AudioTranscodeConfigModel",
    "TranscodeV6Model",
    # Filters
    "LanguageFallbackModel",
    "AudioFilterModel",
    "SubtitleFilterModel",
    "AttachmentFilterModel",
    "AudioActionsModel",
    "SubtitleActionsModel",
    "ContainerModel",
    "FileTimestampModel",
    # Conditions
    "ComparisonModel",
    "TitleMatchModel",
    "TrackFiltersModel",
    "ExistsConditionModel",
    "CountConditionModel",
    "AudioIsMultiLanguageModel",
    "PluginMetadataConditionModel",
    "IsOriginalConditionModel",
    "IsDubbedConditionModel",
    "ConditionModel",
    # Actions
    "SetForcedActionModel",
    "SetDefaultActionModel",
    "PluginMetadataReferenceModel",
    "SetLanguageActionModel",
    "ActionModel",
    "ConditionalRuleModel",
    # Synthesis
    "ChannelPreferenceModel",
    "PreferenceCriterionModel",
    "SourcePreferencesModel",
    "SkipIfExistsModel",
    "SynthesisTrackDefinitionModel",
    "AudioSynthesisModel",
    # Phases
    "GlobalConfigModel",
    "PhaseSkipConditionModel",
    "RunIfConditionModel",
    "PhaseModel",
    "PolicyModel",
]
