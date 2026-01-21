"""Policy engine module for Video Policy Orchestrator.

This module provides policy loading, validation, and evaluation functionality:
- loader: High-level policy loading from YAML files
- pydantic_models: Pydantic models for YAML parsing/validation
- conversion: Functions to convert Pydantic models to dataclasses
- types: Policy, Plan, and PlannedAction dataclasses
- evaluator: Pure-function policy evaluation
- matchers: Commentary pattern matching utilities
- discovery: Policy file discovery and metadata extraction
"""

# Codec matching utilities
from vpo.policy.codecs import (
    AUDIO_CODEC_ALIASES,
    VIDEO_CODEC_ALIASES,
    audio_codec_matches,
    audio_codec_matches_any,
    normalize_audio_codec,
    normalize_video_codec,
    video_codec_matches,
    video_codec_matches_any,
)
from vpo.policy.discovery import (
    DEFAULT_POLICIES_DIR,
    PolicySummary,
    discover_policies,
)
from vpo.policy.evaluator import (
    EvaluationError,
    NoTracksError,
    UnsupportedContainerError,
    classify_track,
    compute_default_flags,
    compute_desired_order,
    evaluate_policy,
)
from vpo.policy.loader import (
    PolicyValidationError,
    load_policy,
    load_policy_from_dict,
)
from vpo.policy.matchers import CommentaryMatcher

# Skip condition evaluation
from vpo.policy.transcode import (
    SkipEvaluationResult,
    evaluate_skip_condition,
)
from vpo.policy.types import (
    ActionType,
    DefaultFlagsConfig,
    Plan,
    PlannedAction,
    PolicySchema,
    TrackType,
)
from vpo.policy.validation import (
    DiffSummary,
    FieldChange,
    ValidationError,
    ValidationResult,
    format_pydantic_errors,
    validate_policy_data,
)

# Video analysis utilities
from vpo.policy.video_analysis import (
    HDRType,
    VideoAnalysisResult,
    analyze_video_tracks,
    build_hdr_preservation_args,
    detect_hdr_content,
    detect_hdr_type,
    detect_missing_bitrate,
    detect_vfr_content,
    parse_frame_rate,
    select_primary_video_stream,
)

__all__ = [
    # Models
    "ActionType",
    "DefaultFlagsConfig",
    "Plan",
    "PlannedAction",
    "PolicySchema",
    "TrackType",
    # Loader
    "PolicyValidationError",
    "load_policy",
    "load_policy_from_dict",
    # Evaluator
    "EvaluationError",
    "NoTracksError",
    "UnsupportedContainerError",
    "classify_track",
    "compute_default_flags",
    "compute_desired_order",
    "evaluate_policy",
    # Matchers
    "CommentaryMatcher",
    # Discovery
    "DEFAULT_POLICIES_DIR",
    "PolicySummary",
    "discover_policies",
    # Validation (025-policy-validation)
    "DiffSummary",
    "FieldChange",
    "ValidationError",
    "ValidationResult",
    "format_pydantic_errors",
    "validate_policy_data",
    # Codec matching
    "AUDIO_CODEC_ALIASES",
    "VIDEO_CODEC_ALIASES",
    "audio_codec_matches",
    "audio_codec_matches_any",
    "normalize_audio_codec",
    "normalize_video_codec",
    "video_codec_matches",
    "video_codec_matches_any",
    # Video analysis
    "HDRType",
    "VideoAnalysisResult",
    "analyze_video_tracks",
    "build_hdr_preservation_args",
    "detect_hdr_content",
    "detect_hdr_type",
    "detect_missing_bitrate",
    "detect_vfr_content",
    "parse_frame_rate",
    "select_primary_video_stream",
    # Skip condition evaluation
    "SkipEvaluationResult",
    "evaluate_skip_condition",
]
