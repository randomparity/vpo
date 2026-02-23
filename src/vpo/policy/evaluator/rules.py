"""Conditional rule evaluation.

This module provides functions for evaluating conditional rules
in policy definitions and executing matched actions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from vpo.language_analysis.models import LanguageAnalysisResult
    from vpo.track_classification.models import TrackClassificationResult

from vpo.domain import TrackInfo
from vpo.policy.conditions import PluginMetadataDict
from vpo.policy.types import (
    ConditionalResult,
    ConditionalRule,
    ContainerMetadataChange,
    MatchMode,
    RuleEvaluation,
    RulesConfig,
    SkipFlags,
    TrackFlagChange,
    TrackLanguageChange,
)

logger = logging.getLogger(__name__)


def evaluate_conditional_rules(
    rules: RulesConfig,
    tracks: list[TrackInfo],
    file_path: Path,
    language_results: dict[int, LanguageAnalysisResult] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
    classification_results: dict[int, TrackClassificationResult] | None = None,
    container_tags: dict[str, str] | None = None,
) -> ConditionalResult:
    """Evaluate conditional rules and execute matching actions.

    Evaluation behavior depends on the match mode:

    - **FIRST** (first-match-wins): Rules are evaluated in order. The first
      rule whose 'when' condition matches wins, and its 'then' actions are
      executed. If no rules match and the last rule has an 'else' clause,
      that else clause is executed.

    - **ALL** (evaluate all): All rules are evaluated. Every rule whose
      'when' condition matches has its 'then' actions executed, accumulating
      skip flags, warnings, and track changes. If no rules match, the last
      rule's 'else' clause fires (if present).

    Args:
        rules: RulesConfig with match mode and rule items.
        tracks: List of TrackInfo from the file.
        file_path: Path to the file being processed.
        language_results: Optional dict mapping track_id to LanguageAnalysisResult.
        plugin_metadata: Optional dict of plugin metadata keyed by plugin name.
        classification_results: Optional dict mapping track_id to
            TrackClassificationResult.
        container_tags: Optional dict of container-level metadata tags.

    Returns:
        ConditionalResult with matched rule, skip flags, warnings, and trace.

    Raises:
        ConditionalFailError: If a matched rule has a fail action.
    """
    from vpo.policy.actions import ActionContext, execute_actions
    from vpo.policy.conditions import evaluate_condition

    items = rules.items

    # Empty rules - return empty result
    if not items:
        return ConditionalResult(
            matched_rule=None,
            matched_branch=None,
            warnings=(),
            evaluation_trace=(),
        )

    if rules.match == MatchMode.FIRST:
        return _evaluate_first_match(
            items,
            tracks,
            file_path,
            language_results,
            plugin_metadata,
            classification_results,
            container_tags,
            evaluate_condition,
            ActionContext,
            execute_actions,
        )
    else:
        return _evaluate_all_match(
            items,
            tracks,
            file_path,
            language_results,
            plugin_metadata,
            classification_results,
            container_tags,
            evaluate_condition,
            ActionContext,
            execute_actions,
        )


def _evaluate_first_match(
    rules: tuple[ConditionalRule, ...],
    tracks: list[TrackInfo],
    file_path: Path,
    language_results: dict[int, LanguageAnalysisResult] | None,
    plugin_metadata: PluginMetadataDict | None,
    classification_results: dict[int, TrackClassificationResult] | None,
    container_tags: dict[str, str] | None,
    evaluate_condition: Callable[..., tuple[bool, str]],
    action_context_cls: type,
    execute_actions: Callable[..., Any],
) -> ConditionalResult:
    """First-match-wins evaluation: stop on first matching rule."""
    evaluation_trace: list[RuleEvaluation] = []
    matched_rule: str | None = None
    matched_branch: Literal["then", "else"] | None = None
    skip_flags = SkipFlags()
    warnings: list[str] = []
    track_flag_changes: list[TrackFlagChange] = []
    track_language_changes: list[TrackLanguageChange] = []
    container_metadata_changes: list[ContainerMetadataChange] = []

    for i, rule in enumerate(rules):
        result, reason = evaluate_condition(
            rule.when,
            tracks,
            language_results,
            None,
            plugin_metadata,
            classification_results,
            container_tags,
        )

        if result:
            evaluation_trace.append(
                RuleEvaluation(rule_name=rule.name, matched=True, reason=reason)
            )
            matched_rule = rule.name
            matched_branch = "then"

            context = action_context_cls(
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
            container_metadata_changes = context.container_metadata_changes
            break
        else:
            evaluation_trace.append(
                RuleEvaluation(rule_name=rule.name, matched=False, reason=reason)
            )
            is_last_rule = i == len(rules) - 1
            if is_last_rule and rule.else_actions is not None:
                matched_rule = rule.name
                matched_branch = "else"
                context = action_context_cls(
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
                container_metadata_changes = context.container_metadata_changes

    return ConditionalResult(
        matched_rule=matched_rule,
        matched_branch=matched_branch,
        warnings=tuple(warnings),
        evaluation_trace=tuple(evaluation_trace),
        skip_flags=skip_flags,
        track_flag_changes=tuple(track_flag_changes),
        track_language_changes=tuple(track_language_changes),
        container_metadata_changes=tuple(container_metadata_changes),
    )


def _evaluate_all_match(
    rules: tuple[ConditionalRule, ...],
    tracks: list[TrackInfo],
    file_path: Path,
    language_results: dict[int, LanguageAnalysisResult] | None,
    plugin_metadata: PluginMetadataDict | None,
    classification_results: dict[int, TrackClassificationResult] | None,
    container_tags: dict[str, str] | None,
    evaluate_condition: Callable[..., tuple[bool, str]],
    action_context_cls: type,
    execute_actions: Callable[..., Any],
) -> ConditionalResult:
    """All-match evaluation: evaluate every rule, accumulate results."""
    # Warn about else_actions on non-last rules (ignored in ALL mode)
    for i, rule in enumerate(rules[:-1]):
        if rule.else_actions is not None:
            logger.warning(
                "Rule '%s' has else_actions but is not the last rule in ALL "
                "mode — else_actions will be ignored (only the last rule's "
                "else clause fires when no rules match)",
                rule.name,
            )
    evaluation_trace: list[RuleEvaluation] = []
    last_matched_rule: str | None = None
    matched_branch: Literal["then", "else"] | None = None
    skip_flags = SkipFlags()
    warnings: list[str] = []
    track_flag_changes: list[TrackFlagChange] = []
    track_language_changes: list[TrackLanguageChange] = []
    container_metadata_changes: list[ContainerMetadataChange] = []
    any_matched = False

    for i, rule in enumerate(rules):
        result, reason = evaluate_condition(
            rule.when,
            tracks,
            language_results,
            None,
            plugin_metadata,
            classification_results,
            container_tags,
        )

        if result:
            any_matched = True
            evaluation_trace.append(
                RuleEvaluation(rule_name=rule.name, matched=True, reason=reason)
            )
            last_matched_rule = rule.name
            matched_branch = "then"

            context = action_context_cls(
                file_path=file_path,
                rule_name=rule.name,
                tracks=tracks,
                plugin_metadata=plugin_metadata,
            )
            context = execute_actions(rule.then_actions, context)
            # Accumulate: merge skip flags (OR semantics)
            skip_flags = SkipFlags(
                skip_video_transcode=skip_flags.skip_video_transcode
                or context.skip_flags.skip_video_transcode,
                skip_audio_transcode=skip_flags.skip_audio_transcode
                or context.skip_flags.skip_audio_transcode,
                skip_track_filter=skip_flags.skip_track_filter
                or context.skip_flags.skip_track_filter,
            )
            warnings.extend(context.warnings)
            track_flag_changes.extend(context.track_flag_changes)
            track_language_changes.extend(context.track_language_changes)
            container_metadata_changes.extend(context.container_metadata_changes)
        else:
            evaluation_trace.append(
                RuleEvaluation(rule_name=rule.name, matched=False, reason=reason)
            )

    # If no rules matched, fire the last rule's else clause (if present)
    if not any_matched and rules:
        last_rule = rules[-1]
        if last_rule.else_actions is not None:
            last_matched_rule = last_rule.name
            matched_branch = "else"
            context = action_context_cls(
                file_path=file_path,
                rule_name=last_rule.name,
                tracks=tracks,
                plugin_metadata=plugin_metadata,
            )
            context = execute_actions(last_rule.else_actions, context)
            skip_flags = context.skip_flags
            warnings.extend(context.warnings)
            track_flag_changes.extend(context.track_flag_changes)
            track_language_changes.extend(context.track_language_changes)
            container_metadata_changes.extend(context.container_metadata_changes)

    return ConditionalResult(
        matched_rule=last_matched_rule,
        matched_branch=matched_branch,
        warnings=tuple(warnings),
        evaluation_trace=tuple(evaluation_trace),
        skip_flags=skip_flags,
        track_flag_changes=tuple(track_flag_changes),
        track_language_changes=tuple(track_language_changes),
        container_metadata_changes=tuple(container_metadata_changes),
    )
