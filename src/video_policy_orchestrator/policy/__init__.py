"""Policy engine module for Video Policy Orchestrator.

This module provides policy loading, validation, and evaluation functionality:
- loader: Load and validate YAML policy files
- models: Policy, Plan, and PlannedAction dataclasses
- evaluator: Pure-function policy evaluation
- matchers: Commentary pattern matching utilities
- discovery: Policy file discovery and metadata extraction
"""

from video_policy_orchestrator.policy.discovery import (
    DEFAULT_POLICIES_DIR,
    PolicySummary,
    discover_policies,
)
from video_policy_orchestrator.policy.evaluator import (
    EvaluationError,
    NoTracksError,
    UnsupportedContainerError,
    classify_track,
    compute_default_flags,
    compute_desired_order,
    evaluate_policy,
)
from video_policy_orchestrator.policy.loader import (
    PolicyValidationError,
    load_policy,
    load_policy_from_dict,
)
from video_policy_orchestrator.policy.matchers import CommentaryMatcher
from video_policy_orchestrator.policy.models import (
    ActionType,
    DefaultFlagsConfig,
    Plan,
    PlannedAction,
    PolicySchema,
    TrackType,
)
from video_policy_orchestrator.policy.validation import (
    DiffSummary,
    FieldChange,
    ValidationError,
    ValidationResult,
    format_pydantic_errors,
    validate_policy_data,
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
]
