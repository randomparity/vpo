"""Pure-function policy evaluation.

This module provides the core evaluation logic for applying policies
to media file track metadata. All functions are pure (no side effects).

Re-exports all public API for backward compatibility.
"""

from vpo.policy.evaluator.classification import (
    classify_track,
    compute_default_flags,
    compute_desired_order,
)
from vpo.policy.evaluator.container import (
    evaluate_container_change_with_policy,
    normalize_container_format,
)
from vpo.policy.evaluator.evaluate import evaluate_policy
from vpo.policy.evaluator.exceptions import (
    EvaluationError,
    NoTracksError,
    UnsupportedContainerError,
)
from vpo.policy.evaluator.filtering import compute_track_dispositions
from vpo.policy.evaluator.rules import evaluate_conditional_rules
from vpo.policy.evaluator.transcription import compute_language_updates

# Re-export Plan for backward compatibility (imported by evaluate.py from types)
from vpo.policy.types import Plan

__all__ = [
    # Exceptions
    "EvaluationError",
    "NoTracksError",
    "UnsupportedContainerError",
    # Classification
    "classify_track",
    "compute_default_flags",
    "compute_desired_order",
    # Transcription
    "compute_language_updates",
    # Filtering
    "compute_track_dispositions",
    # Container
    "normalize_container_format",
    "evaluate_container_change_with_policy",
    # Rules
    "evaluate_conditional_rules",
    # Main evaluation
    "evaluate_policy",
    # Types (backward compatibility)
    "Plan",
]
