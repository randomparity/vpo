"""Conditional action handlers for policy rules.

This module implements the execution logic for conditional actions
in VPO policies. Actions are triggered when conditional rules match
and can skip processing, emit warnings, or halt execution.

Key Functions:
    execute_actions: Execute a list of conditional actions
    handle_skip_action: Set skip flags in the evaluation context
    handle_warn_action: Log a warning message with placeholder substitution
    handle_fail_action: Raise ConditionalFailError to halt processing

Placeholder Substitution:
    Actions with message templates support these placeholders:
    - {filename}: Base filename without path
    - {path}: Full file path
    - {rule_name}: Name of the matching rule

Usage:
    from video_policy_orchestrator.policy.actions import execute_actions
    from video_policy_orchestrator.policy.models import SkipAction, SkipType

    action = SkipAction(skip_type=SkipType.VIDEO_TRANSCODE)
    result = execute_actions([action], context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator.language import languages_match
from video_policy_orchestrator.policy.exceptions import ConditionalFailError
from video_policy_orchestrator.policy.models import (
    ConditionalAction,
    FailAction,
    SetDefaultAction,
    SetForcedAction,
    SkipAction,
    SkipFlags,
    SkipType,
    TrackFlagChange,
    WarnAction,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import TrackInfo

logger = logging.getLogger(__name__)


@dataclass
class ActionContext:
    """Context for action execution.

    Provides file information for placeholder substitution
    and tracks accumulated skip flags, warnings, and track flag changes.
    """

    file_path: Path
    rule_name: str

    # Tracks for set_forced/set_default actions (optional)
    tracks: list[TrackInfo] = field(default_factory=list)

    # Accumulated state
    skip_flags: SkipFlags = field(default_factory=SkipFlags)
    warnings: list[str] = field(default_factory=list)
    track_flag_changes: list[TrackFlagChange] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """Get the base filename without path."""
        return self.file_path.name

    def substitute_placeholders(self, message: str) -> str:
        """Substitute placeholders in a message template.

        Supported placeholders:
            {filename}: Base filename without path
            {path}: Full file path
            {rule_name}: Name of the matching rule

        Args:
            message: Message template with placeholders.

        Returns:
            Message with placeholders substituted.
        """
        try:
            return message.format(
                filename=self.filename,
                path=str(self.file_path),
                rule_name=self.rule_name,
            )
        except KeyError as e:
            return f"{message} [invalid placeholder: {e}]"


def execute_skip_action(action: SkipAction, context: ActionContext) -> ActionContext:
    """Execute a skip action, setting the appropriate flag.

    Args:
        action: The skip action to execute.
        context: Current action context.

    Returns:
        Updated context with skip flag set.
    """
    flags = context.skip_flags

    if action.skip_type == SkipType.VIDEO_TRANSCODE:
        context.skip_flags = SkipFlags(
            skip_video_transcode=True,
            skip_audio_transcode=flags.skip_audio_transcode,
            skip_track_filter=flags.skip_track_filter,
        )
    elif action.skip_type == SkipType.AUDIO_TRANSCODE:
        context.skip_flags = SkipFlags(
            skip_video_transcode=flags.skip_video_transcode,
            skip_audio_transcode=True,
            skip_track_filter=flags.skip_track_filter,
        )
    elif action.skip_type == SkipType.TRACK_FILTER:
        context.skip_flags = SkipFlags(
            skip_video_transcode=flags.skip_video_transcode,
            skip_audio_transcode=flags.skip_audio_transcode,
            skip_track_filter=True,
        )

    return context


def execute_warn_action(action: WarnAction, context: ActionContext) -> ActionContext:
    """Execute a warn action, recording the warning message.

    Args:
        action: The warn action to execute.
        context: Current action context.

    Returns:
        Updated context with warning recorded.
    """
    message = context.substitute_placeholders(action.message)
    context.warnings.append(message)
    return context


def execute_fail_action(action: FailAction, context: ActionContext) -> None:
    """Execute a fail action, raising ConditionalFailError.

    Args:
        action: The fail action to execute.
        context: Current action context.

    Raises:
        ConditionalFailError: Always raised to halt processing.
    """
    message = context.substitute_placeholders(action.message)
    raise ConditionalFailError(
        rule_name=context.rule_name,
        message=message,
        file_path=str(context.file_path),
    )


def execute_set_forced_action(
    action: SetForcedAction, context: ActionContext
) -> ActionContext:
    """Execute a set_forced action, setting forced flag on matching tracks.

    Args:
        action: The set_forced action to execute.
        context: Current action context (must have tracks populated).

    Returns:
        Updated context with track flag changes recorded.
    """
    if not context.tracks:
        logger.warning(
            "set_forced action skipped: no tracks available in context for %s",
            context.file_path,
        )
        return context

    # Find matching tracks
    matching_tracks = [
        t for t in context.tracks if t.track_type.lower() == action.track_type.lower()
    ]

    # Apply language filter if specified
    if action.language is not None:
        matching_tracks = [
            t
            for t in matching_tracks
            if t.language and languages_match(t.language, action.language)
        ]

    if not matching_tracks:
        logger.warning(
            "set_forced action: no matching %s tracks%s found in %s",
            action.track_type,
            f" (language={action.language})" if action.language else "",
            context.file_path,
        )
        return context

    # Add flag changes for matching tracks
    for track in matching_tracks:
        context.track_flag_changes.append(
            TrackFlagChange(
                track_index=track.index,
                flag_type="forced",
                value=action.value,
            )
        )
        logger.debug(
            "set_forced: track[%d] forced=%s for %s",
            track.index,
            action.value,
            context.file_path,
        )

    return context


def execute_set_default_action(
    action: SetDefaultAction, context: ActionContext
) -> ActionContext:
    """Execute a set_default action, setting default flag on matching tracks.

    Args:
        action: The set_default action to execute.
        context: Current action context (must have tracks populated).

    Returns:
        Updated context with track flag changes recorded.
    """
    if not context.tracks:
        logger.warning(
            "set_default action skipped: no tracks available in context for %s",
            context.file_path,
        )
        return context

    # Find matching tracks
    matching_tracks = [
        t for t in context.tracks if t.track_type.lower() == action.track_type.lower()
    ]

    # Apply language filter if specified
    if action.language is not None:
        matching_tracks = [
            t
            for t in matching_tracks
            if t.language and languages_match(t.language, action.language)
        ]

    if not matching_tracks:
        logger.warning(
            "set_default action: no matching %s tracks%s found in %s",
            action.track_type,
            f" (language={action.language})" if action.language else "",
            context.file_path,
        )
        return context

    # Add flag change for first matching track only (there can be only one default)
    track = matching_tracks[0]
    context.track_flag_changes.append(
        TrackFlagChange(
            track_index=track.index,
            flag_type="default",
            value=action.value,
        )
    )
    logger.debug(
        "set_default: track[%d] default=%s for %s",
        track.index,
        action.value,
        context.file_path,
    )

    return context


def execute_actions(
    actions: tuple[ConditionalAction, ...],
    context: ActionContext,
) -> ActionContext:
    """Execute a sequence of conditional actions.

    Actions are executed in order. If a FailAction is encountered,
    ConditionalFailError is raised and execution stops.

    Args:
        actions: Tuple of actions to execute.
        context: Current action context.

    Returns:
        Updated context with all skip flags, warnings, and flag changes.

    Raises:
        ConditionalFailError: If any action is a FailAction.
    """
    for action in actions:
        if isinstance(action, SkipAction):
            context = execute_skip_action(action, context)
        elif isinstance(action, WarnAction):
            context = execute_warn_action(action, context)
        elif isinstance(action, SetForcedAction):
            context = execute_set_forced_action(action, context)
        elif isinstance(action, SetDefaultAction):
            context = execute_set_default_action(action, context)
        elif isinstance(action, FailAction):
            execute_fail_action(action, context)

    return context
