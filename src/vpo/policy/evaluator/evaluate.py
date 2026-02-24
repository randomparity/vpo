"""Main policy evaluation entry point.

This module provides the main evaluate_policy() function that orchestrates
all evaluation steps to produce an execution plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.language_analysis.models import LanguageAnalysisResult
    from vpo.track_classification.models import TrackClassificationResult

from vpo.db import TrackInfo
from vpo.plugin_sdk.helpers import is_mkv_container
from vpo.policy.conditions import PluginMetadataDict
from vpo.policy.evaluator.classification import (
    _audio_matches_language_preference,
    _find_preferred_track,
    compute_default_flags,
    compute_desired_order,
)
from vpo.policy.evaluator.container import evaluate_container_change_with_policy
from vpo.policy.evaluator.exceptions import NoTracksError
from vpo.policy.evaluator.filtering import compute_track_dispositions
from vpo.policy.evaluator.rules import evaluate_conditional_rules
from vpo.policy.evaluator.transcription import (
    compute_language_updates,
    compute_title_updates,
)
from vpo.policy.matchers import CommentaryMatcher
from vpo.policy.types import (
    ActionType,
    ConditionalResult,
    ContainerChange,
    EvaluationPolicy,
    Plan,
    PlannedAction,
    SkipFlags,
    TrackDisposition,
    TranscriptionInfo,
)


def evaluate_policy(
    file_id: str,
    file_path: Path,
    container: str,
    tracks: list[TrackInfo],
    policy: EvaluationPolicy,
    transcription_results: dict[int, TranscriptionInfo] | None = None,
    language_results: dict[int, LanguageAnalysisResult] | None = None,
    plugin_metadata: PluginMetadataDict | None = None,
    classification_results: dict[int, TrackClassificationResult] | None = None,
    container_tags: dict[str, str] | None = None,
) -> Plan:
    """Evaluate a policy against file tracks to produce an execution plan.

    This is a pure function with no side effects. Given the same inputs,
    it always produces the same output.

    Args:
        file_id: UUID of the file being evaluated.
        file_path: Path to the media file.
        container: Container format (mkv, mp4, etc.).
        tracks: List of track metadata from introspection.
        policy: Validated policy configuration.
        transcription_results: Optional map of track_id to transcription result.
            Required for transcription-based language updates.
        language_results: Optional dict mapping track_id to LanguageAnalysisResult.
            Required for audio_is_multi_language conditions.
        plugin_metadata: Optional dict of plugin metadata keyed by plugin name.
            Required for plugin_metadata conditions.
        classification_results: Optional dict mapping track_id to
            TrackClassificationResult. Required for is_original/is_dubbed conditions.
        container_tags: Optional dict of container-level metadata tags
            (key → value). Required for container_metadata conditions.

    Returns:
        Plan describing all changes needed to make tracks conform to policy.

    Raises:
        NoTracksError: If no tracks are provided.
        ConditionalFailError: If a conditional rule triggers a fail action.

    Edge cases handled:
        - No tracks: Raises NoTracksError
        - No audio tracks: Skips audio default flag processing
        - All commentary: Falls back to first track for defaults
        - Missing language: Uses "und" as fallback
        - Missing transcription results: Skips language updates for those tracks
        - Low confidence: Skips update if below threshold
    """
    # Edge case: no tracks
    if not tracks:
        raise NoTracksError("File has no tracks to evaluate")

    # V4: Evaluate conditional rules first (may raise ConditionalFailError)
    conditional_result: ConditionalResult | None = None
    skip_flags = SkipFlags()

    if policy.has_rules:
        conditional_result = evaluate_conditional_rules(
            rules=policy.rules,
            tracks=tracks,
            file_path=file_path,
            language_results=language_results,
            plugin_metadata=plugin_metadata,
            classification_results=classification_results,
            container_tags=container_tags,
        )
        skip_flags = conditional_result.skip_flags

    matcher = CommentaryMatcher(policy.commentary_patterns)
    actions: list[PlannedAction] = []
    requires_remux = False

    # Process track actions (pre-processing, applied before filters)
    # These generate CLEAR_FORCED/CLEAR_DEFAULT/SET_TITLE actions to normalize metadata
    if policy.audio_actions is not None:
        for track in tracks:
            if track.track_type.casefold() != "audio":
                continue
            if policy.audio_actions.clear_all_forced and track.is_forced:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_FORCED,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.audio_actions.clear_all_default and track.is_default:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_DEFAULT,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.audio_actions.clear_all_titles and track.title:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_TITLE,
                        track_index=track.index,
                        current_value=track.title,
                        desired_value="",
                    )
                )

    # Process video_actions (pre-processing for video tracks)
    if policy.video_actions is not None:
        for track in tracks:
            if track.track_type.casefold() != "video":
                continue
            if policy.video_actions.clear_all_forced and track.is_forced:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_FORCED,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.video_actions.clear_all_default and track.is_default:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_DEFAULT,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.video_actions.clear_all_titles and track.title:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_TITLE,
                        track_index=track.index,
                        current_value=track.title,
                        desired_value="",
                    )
                )

    # NOTE: Execution order contract - subtitle_actions are applied BEFORE filters.
    # This ensures clear_all_forced runs before preserve_forced filter evaluation.
    # The subtitle_forced_will_be_cleared flag is passed to compute_track_dispositions
    # so that preserve_forced correctly ignores tracks that will have forced cleared.
    if policy.subtitle_actions is not None:
        for track in tracks:
            if track.track_type.casefold() != "subtitle":
                continue
            if policy.subtitle_actions.clear_all_forced and track.is_forced:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_FORCED,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.subtitle_actions.clear_all_default and track.is_default:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.CLEAR_DEFAULT,
                        track_index=track.index,
                        current_value=True,
                        desired_value=False,
                    )
                )
            if policy.subtitle_actions.clear_all_titles and track.title:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_TITLE,
                        track_index=track.index,
                        current_value=track.title,
                        desired_value="",
                    )
                )

    # Convert track flag changes from conditional rules to PlannedActions
    if conditional_result is not None and conditional_result.track_flag_changes:
        for change in conditional_result.track_flag_changes:
            # Find current track state
            track = next((t for t in tracks if t.index == change.track_index), None)
            if track is None:
                continue

            if change.flag_type == "forced":
                current = track.is_forced
                if current != change.value:
                    if change.value:
                        action_type = ActionType.SET_FORCED
                    else:
                        action_type = ActionType.CLEAR_FORCED
                    actions.append(
                        PlannedAction(
                            action_type=action_type,
                            track_index=change.track_index,
                            current_value=current,
                            desired_value=change.value,
                        )
                    )
            elif change.flag_type == "default":
                current = track.is_default
                if current != change.value:
                    if change.value:
                        action_type = ActionType.SET_DEFAULT
                    else:
                        action_type = ActionType.CLEAR_DEFAULT
                    actions.append(
                        PlannedAction(
                            action_type=action_type,
                            track_index=change.track_index,
                            current_value=current,
                            desired_value=change.value,
                        )
                    )

    # Convert track language changes from conditional rules to PlannedActions
    if conditional_result is not None and conditional_result.track_language_changes:
        for change in conditional_result.track_language_changes:
            # Find current track state
            track = next((t for t in tracks if t.index == change.track_index), None)
            if track is None:
                continue

            current = track.language
            if current != change.new_language:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_LANGUAGE,
                        track_index=change.track_index,
                        current_value=current,
                        desired_value=change.new_language,
                    )
                )

    # Convert container metadata changes from conditional rules to PlannedActions
    if conditional_result is not None and conditional_result.container_metadata_changes:
        for change in conditional_result.container_metadata_changes:
            # Idempotency: compare current tag value with desired
            current_value = None
            if container_tags is not None:
                current_value = container_tags.get(change.field.casefold())
            # Skip if already set to desired value
            if current_value == change.new_value:
                continue
            # For clearing: skip if tag doesn't exist
            if change.new_value == "" and current_value is None:
                continue
            actions.append(
                PlannedAction(
                    action_type=ActionType.SET_CONTAINER_METADATA,
                    track_index=None,
                    current_value=current_value,
                    desired_value=change.new_value,
                    container_field=change.field,
                )
            )

    # Compute desired track order (handles empty tracks gracefully)
    # Pass transcription_results to enable transcription-based commentary detection
    current_order = [t.index for t in sorted(tracks, key=lambda t: t.index)]
    desired_order = compute_desired_order(
        tracks, policy, matcher, transcription_results
    )

    # Check if reordering is needed
    if current_order != desired_order:
        # Only MKV supports track reordering
        if is_mkv_container(container):
            actions.append(
                PlannedAction(
                    action_type=ActionType.REORDER,
                    track_index=None,
                    current_value=current_order,
                    desired_value=desired_order,
                )
            )
            requires_remux = True

    # Compute desired default flags (handles edge cases internally)
    # - All commentary tracks: uses first track as default
    # - Missing language: uses "und" as fallback
    # - No tracks of type: skips that type
    desired_defaults = compute_default_flags(tracks, policy, matcher)

    # Create actions for flag changes
    for track in tracks:
        desired = desired_defaults.get(track.index)
        if desired is not None and desired != track.is_default:
            if desired:
                action_type = ActionType.SET_DEFAULT
            else:
                action_type = ActionType.CLEAR_DEFAULT
            actions.append(
                PlannedAction(
                    action_type=action_type,
                    track_index=track.index,
                    current_value=track.is_default,
                    desired_value=desired,
                )
            )

    # Set subtitle forced flag when audio language differs from preference
    if policy.default_flags.set_subtitle_forced_when_audio_differs:
        audio_tracks = [t for t in tracks if t.track_type.casefold() == "audio"]
        subtitle_tracks = [t for t in tracks if t.track_type.casefold() == "subtitle"]

        if subtitle_tracks and not _audio_matches_language_preference(
            audio_tracks, policy.audio_languages, matcher
        ):
            # Find the preferred subtitle track
            forced_subtitle = _find_preferred_track(
                subtitle_tracks, policy.subtitle_languages, matcher
            )
            if forced_subtitle is not None and not forced_subtitle.is_forced:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_FORCED,
                        track_index=forced_subtitle.index,
                        current_value=False,
                        desired_value=True,
                    )
                )

    # Compute language updates from transcription results
    if transcription_results is not None:
        language_updates = compute_language_updates(
            tracks, transcription_results, policy
        )
        for track in tracks:
            new_lang = language_updates.get(track.index)
            if new_lang is not None:
                current_lang = track.language or "und"
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_LANGUAGE,
                        track_index=track.index,
                        current_value=current_lang,
                        desired_value=new_lang,
                    )
                )

    # Compute title updates from transcription classification.
    # Skip tracks that already have an explicit SET_TITLE action
    # (e.g. from clear_all_titles) to avoid conflicting actions.
    if transcription_results is not None:
        tracks_with_title_action = frozenset(
            a.track_index for a in actions if a.action_type == ActionType.SET_TITLE
        )
        title_updates = compute_title_updates(tracks, transcription_results, policy)
        for track in tracks:
            if track.index in tracks_with_title_action:
                continue
            new_title = title_updates.get(track.index)
            if new_title is not None:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.SET_TITLE,
                        track_index=track.index,
                        current_value=track.title,
                        desired_value=new_title,
                    )
                )

    # Compute track dispositions for V3 track filtering
    track_dispositions: tuple[TrackDisposition, ...] = ()
    tracks_removed = 0
    # Default: all tracks kept when no filtering is active
    tracks_kept = len(tracks)

    # V4: Check skip_track_filter flag before applying track filtering
    should_filter = policy.has_track_filtering and not skip_flags.skip_track_filter
    if should_filter:
        # Check if subtitle forced flags will be cleared by actions
        subtitle_forced_will_be_cleared = (
            policy.subtitle_actions is not None
            and policy.subtitle_actions.clear_all_forced
        )
        track_dispositions = compute_track_dispositions(
            tracks, policy, transcription_results, subtitle_forced_will_be_cleared
        )
        tracks_removed = sum(1 for d in track_dispositions if d.action == "REMOVE")
        tracks_kept = sum(1 for d in track_dispositions if d.action == "KEEP")
        if tracks_removed > 0:
            requires_remux = True

    # Compute container change for V3 container conversion
    container_change: ContainerChange | None = None
    if policy.has_container_config:
        container_change = evaluate_container_change_with_policy(
            tracks, container, policy
        )
        # Only requires remux if actually changing format
        if container_change is not None:
            if container_change.source_format != container_change.target_format:
                requires_remux = True

    return Plan(
        file_id=file_id,
        file_path=file_path,
        policy_version=policy.schema_version,
        actions=tuple(actions),
        requires_remux=requires_remux,
        created_at=datetime.now(timezone.utc),
        track_dispositions=track_dispositions,
        container_change=container_change,
        conditional_result=conditional_result,
        skip_flags=skip_flags,
        tracks_removed=tracks_removed,
        tracks_kept=tracks_kept,
    )
