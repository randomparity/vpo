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
    from vpo.policy.actions import execute_actions
    from vpo.policy.types import SkipAction, SkipType

    action = SkipAction(skip_type=SkipType.VIDEO_TRANSCODE)
    result = execute_actions([action], context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from vpo.language import languages_match
from vpo.policy.exceptions import ConditionalFailError
from vpo.policy.types import (
    ConditionalAction,
    ContainerMetadataChange,
    FailAction,
    SetContainerMetadataAction,
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

if TYPE_CHECKING:
    from vpo.domain import TrackInfo

logger = logging.getLogger(__name__)


@dataclass
class ActionContext:
    """Context for action execution.

    Provides file information for placeholder substitution
    and tracks accumulated skip flags, warnings, and track flag changes.
    """

    file_path: Path
    rule_name: str

    # Tracks for set_forced/set_default/set_language actions (optional)
    tracks: list[TrackInfo] = field(default_factory=list)

    # Plugin metadata for dynamic value resolution (optional)
    # Keys are plugin names, values are dicts of field -> value
    plugin_metadata: dict[str, dict[str, str]] | None = None

    # Accumulated state
    skip_flags: SkipFlags = field(default_factory=SkipFlags)
    warnings: list[str] = field(default_factory=list)
    track_flag_changes: list[TrackFlagChange] = field(default_factory=list)
    track_language_changes: list[TrackLanguageChange] = field(default_factory=list)
    container_metadata_changes: list[ContainerMetadataChange] = field(
        default_factory=list
    )

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
    from dataclasses import replace

    skip_type_to_flag = {
        SkipType.VIDEO_TRANSCODE: "skip_video_transcode",
        SkipType.AUDIO_TRANSCODE: "skip_audio_transcode",
        SkipType.TRACK_FILTER: "skip_track_filter",
    }

    flag_name = skip_type_to_flag.get(action.skip_type)
    if flag_name:
        context.skip_flags = replace(context.skip_flags, **{flag_name: True})

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


def _find_matching_tracks(
    context: ActionContext,
    track_type: str,
    language: str | None,
    action_name: str,
) -> list[TrackInfo]:
    """Find tracks matching the specified type and optional language filter.

    Args:
        context: Current action context with tracks.
        track_type: Track type to match (e.g., "audio", "subtitle").
        language: Optional language filter.
        action_name: Name of the calling action for log messages.

    Returns:
        List of matching tracks (may be empty).
    """
    if not context.tracks:
        logger.warning(
            "%s action skipped: no tracks available in context for %s",
            action_name,
            context.file_path,
        )
        return []

    matching_tracks = [
        t for t in context.tracks if t.track_type.casefold() == track_type.casefold()
    ]

    if language is not None:
        matching_tracks = [
            t
            for t in matching_tracks
            if t.language and languages_match(t.language, language)
        ]

    if not matching_tracks:
        logger.warning(
            "%s action: no matching %s tracks%s found in %s",
            action_name,
            track_type,
            f" (language={language})" if language else "",
            context.file_path,
        )

    return matching_tracks


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
    matching_tracks = _find_matching_tracks(
        context, action.track_type, action.language, "set_forced"
    )

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
    matching_tracks = _find_matching_tracks(
        context, action.track_type, action.language, "set_default"
    )

    if not matching_tracks:
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


def _resolve_language_from_action(
    action: SetLanguageAction, context: ActionContext
) -> str | None:
    """Resolve the target language from the action.

    If new_language is specified, returns it directly.
    If from_plugin_metadata is specified, looks up the value from context.

    Args:
        action: The set_language action.
        context: Action context with optional plugin_metadata.

    Returns:
        The resolved language code, or None if not available.
    """
    if action.new_language is not None:
        return action.new_language

    if action.from_plugin_metadata is not None:
        ref = action.from_plugin_metadata
        plugin_name = ref.plugin.casefold()
        field_name = ref.field.casefold()

        if context.plugin_metadata is None:
            logger.warning(
                "set_language: no plugin_metadata in context, skipping action"
            )
            return None

        # Case-insensitive plugin lookup
        plugin_data = None
        for key, value in context.plugin_metadata.items():
            if key.casefold() == plugin_name:
                plugin_data = value
                break
        if plugin_data is None:
            logger.warning(
                "set_language: plugin '%s' not found in metadata, skipping action",
                plugin_name,
            )
            return None

        # Case-insensitive field lookup
        field_value = None
        for key, value in plugin_data.items():
            if key.casefold() == field_name:
                field_value = value
                break
        if field_value is None:
            logger.warning(
                "set_language: field '%s' not found in plugin '%s' metadata, "
                "skipping action",
                field_name,
                plugin_name,
            )
            return None

        return str(field_value)

    return None


def execute_set_language_action(
    action: SetLanguageAction, context: ActionContext
) -> ActionContext:
    """Execute a set_language action, setting language tag on matching tracks.

    Args:
        action: The set_language action to execute.
        context: Current action context (must have tracks populated).

    Returns:
        Updated context with track language changes recorded.
    """
    if not context.tracks:
        logger.warning(
            "set_language action skipped: no tracks available in context for %s",
            context.file_path,
        )
        return context

    # Resolve the target language (static or from plugin metadata)
    new_language = _resolve_language_from_action(action, context)
    if new_language is None:
        logger.debug(
            "set_language action skipped: could not resolve language for %s",
            context.file_path,
        )
        return context

    # Find matching tracks by type
    matching_tracks = [
        t
        for t in context.tracks
        if t.track_type.casefold() == action.track_type.casefold()
    ]

    # Apply match_language filter if specified
    if action.match_language is not None:
        matching_tracks = [
            t
            for t in matching_tracks
            if t.language and languages_match(t.language, action.match_language)
        ]

    if not matching_tracks:
        lang_filter = ""
        if action.match_language:
            lang_filter = f" (match_language={action.match_language})"
        logger.warning(
            "set_language action: no matching %s tracks%s found in %s",
            action.track_type,
            lang_filter,
            context.file_path,
        )
        return context

    # Add language changes for matching tracks
    for track in matching_tracks:
        context.track_language_changes.append(
            TrackLanguageChange(
                track_index=track.index,
                new_language=new_language,
            )
        )
        logger.debug(
            "set_language: track[%d] language=%s for %s",
            track.index,
            new_language,
            context.file_path,
        )

    return context


def _resolve_container_metadata_value(
    action: SetContainerMetadataAction, context: ActionContext
) -> str | None:
    """Resolve the target value for a set_container_metadata action.

    If value is specified, returns it directly.
    If from_plugin_metadata is specified, looks up the value from context.

    Args:
        action: The set_container_metadata action.
        context: Action context with optional plugin_metadata.

    Returns:
        The resolved value string, or None if not available.
    """
    if action.value is not None:
        if not isinstance(action.value, str):
            logger.warning(
                "set_container_metadata: value for field '%s' is %s, "
                "converting to string",
                action.field,
                type(action.value).__name__,
            )
            return str(action.value)
        return action.value

    if action.from_plugin_metadata is not None:
        ref = action.from_plugin_metadata
        plugin_name = ref.plugin.casefold()
        field_name = ref.field.casefold()

        if context.plugin_metadata is None:
            logger.warning(
                "set_container_metadata: no plugin_metadata in context, "
                "skipping action for field '%s'",
                action.field,
            )
            return None

        # Case-insensitive plugin lookup
        plugin_data = None
        for key, value in context.plugin_metadata.items():
            if key.casefold() == plugin_name:
                plugin_data = value
                break
        if plugin_data is None:
            logger.warning(
                "set_container_metadata: plugin '%s' not found in metadata, "
                "skipping action for field '%s'",
                plugin_name,
                action.field,
            )
            return None

        # Case-insensitive field lookup
        field_value = None
        for key, value in plugin_data.items():
            if key.casefold() == field_name:
                field_value = value
                break
        if field_value is None:
            logger.warning(
                "set_container_metadata: field '%s' not found in plugin '%s' "
                "metadata, skipping action for container field '%s'",
                field_name,
                plugin_name,
                action.field,
            )
            return None

        return str(field_value)

    return None


def execute_set_container_metadata_action(
    action: SetContainerMetadataAction, context: ActionContext
) -> ActionContext:
    """Execute a set_container_metadata action.

    Args:
        action: The set_container_metadata action to execute.
        context: Current action context.

    Returns:
        Updated context with container metadata change recorded.
    """
    new_value = _resolve_container_metadata_value(action, context)
    if new_value is None:
        logger.debug(
            "set_container_metadata action skipped: could not resolve value "
            "for field '%s' in %s",
            action.field,
            context.file_path,
        )
        return context

    context.container_metadata_changes.append(
        ContainerMetadataChange(
            field=action.field,
            new_value=new_value,
        )
    )
    source = (
        "from_plugin_metadata" if action.from_plugin_metadata is not None else "static"
    )
    logger.debug(
        "set_container_metadata: field '%s' = '%s' (source=%s) for %s",
        action.field,
        new_value if new_value else "(clear)",
        source,
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
        elif isinstance(action, SetLanguageAction):
            context = execute_set_language_action(action, context)
        elif isinstance(action, SetContainerMetadataAction):
            context = execute_set_container_metadata_action(action, context)
        elif isinstance(action, FailAction):
            execute_fail_action(action, context)

    return context
