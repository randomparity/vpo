"""Policy engine module for Video Policy Orchestrator.

This module provides policy loading, validation, and evaluation functionality:
- loader: Load and validate YAML policy files
- models: Policy, Plan, and PlannedAction dataclasses
- evaluator: Pure-function policy evaluation
- matchers: Commentary pattern matching utilities
"""

from video_policy_orchestrator.policy.evaluator import (
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
    "classify_track",
    "compute_default_flags",
    "compute_desired_order",
    "evaluate_policy",
    # Matchers
    "CommentaryMatcher",
]
