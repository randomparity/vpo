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
