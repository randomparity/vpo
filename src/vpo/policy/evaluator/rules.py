"""Conditional rule evaluation.

This module provides functions for evaluating conditional rules
in policy definitions and executing matched actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from vpo.language_analysis.models import LanguageAnalysisResult
    from vpo.track_classification.models import TrackClassificationResult

from vpo.db import TrackInfo
from vpo.policy.conditions import PluginMetadataDict
from vpo.policy.types import (
    ConditionalResult,
    ConditionalRule,
    RuleEvaluation,
    SkipFlags,
    TrackFlagChange,
    TrackLanguageChange,
)


def evaluate_conditional_rules(
    rules: tuple[ConditionalRule, ...],
    tracks: list[TrackInfo],
    file_path: Path,
    language_results: dict[int, LanguageAnalysisResult] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
    classification_results: dict[int, TrackClassificationResult] | None = None,
) -> ConditionalResult:
    """Evaluate conditional rules and execute matching actions.

    Rules are evaluated in document order. The first rule whose 'when'
    condition matches wins, and its 'then' actions are executed.
    If no rules match and the last rule has an 'else' clause, that
    else clause is executed.

    Args:
        rules: Tuple of ConditionalRule from EvaluationPolicy.
        tracks: List of TrackInfo from the file.
        file_path: Path to the file being processed.
        language_results: Optional dict mapping track_id to LanguageAnalysisResult
            (required for audio_is_multi_language conditions).
        plugin_metadata: Optional dict of plugin metadata keyed by plugin name
            (required for plugin_metadata conditions).
        classification_results: Optional dict mapping track_id to
            TrackClassificationResult (required for is_original/is_dubbed conditions).

    Returns:
        ConditionalResult with matched rule, skip flags, warnings, and trace.

    Raises:
        ConditionalFailError: If a matched rule has a fail action.
    """
    from vpo.policy.actions import ActionContext, execute_actions
    from vpo.policy.conditions import evaluate_condition

    # Empty rules - return empty result
    if not rules:
        return ConditionalResult(
            matched_rule=None,
            matched_branch=None,
            warnings=(),
            evaluation_trace=(),
        )

    evaluation_trace: list[RuleEvaluation] = []
    matched_rule: str | None = None
    matched_branch: Literal["then", "else"] | None = None
    skip_flags = SkipFlags()
    warnings: list[str] = []
    track_flag_changes: list[TrackFlagChange] = []
    track_language_changes: list[TrackLanguageChange] = []

    for i, rule in enumerate(rules):
        # Evaluate the condition, passing all context for condition types
        result, reason = evaluate_condition(
            rule.when,
            tracks,
            language_results,
            None,
            plugin_metadata,
            classification_results,
        )

        if result:
            # Condition matched - execute then_actions
            evaluation_trace.append(
                RuleEvaluation(
                    rule_name=rule.name,
                    matched=True,
                    reason=reason,
                )
            )

            matched_rule = rule.name
            matched_branch = "then"

            # Execute actions
            context = ActionContext(
                file_path=file_path,
                rule_name=rule.name,
                tracks=tracks,
                plugin_metadata=plugin_metadata,
            )
            context = execute_actions(rule.then_actions, context)
            skip_flags = context.skip_flags
            warnings = context.warnings
            track_flag_changes = context.track_flag_changes
            track_language_changes = context.track_language_changes

            # First match wins - stop evaluation
            break

        else:
            # Condition didn't match
            evaluation_trace.append(
                RuleEvaluation(
                    rule_name=rule.name,
                    matched=False,
                    reason=reason,
                )
            )

            # Check if this is the last rule and has else_actions
            is_last_rule = i == len(rules) - 1
            if is_last_rule and rule.else_actions is not None:
                # Execute else_actions for the last rule
                matched_rule = rule.name
                matched_branch = "else"

                context = ActionContext(
                    file_path=file_path,
                    rule_name=rule.name,
                    tracks=tracks,
                    plugin_metadata=plugin_metadata,
                )
                context = execute_actions(rule.else_actions, context)
                skip_flags = context.skip_flags
                warnings = context.warnings
                track_flag_changes = context.track_flag_changes
                track_language_changes = context.track_language_changes

    return ConditionalResult(
        matched_rule=matched_rule,
        matched_branch=matched_branch,
        warnings=tuple(warnings),
        evaluation_trace=tuple(evaluation_trace),
        skip_flags=skip_flags,
        track_flag_changes=tuple(track_flag_changes),
        track_language_changes=tuple(track_language_changes),
    )
