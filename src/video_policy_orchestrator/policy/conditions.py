"""Condition evaluation for conditional policy rules.

This module implements the evaluation logic for conditional expressions
in VPO policies. It provides functions to evaluate existence conditions,
count conditions, and boolean operators (and/or/not) against track metadata.

Key Functions:
    evaluate_condition: Main entry point for condition evaluation
    evaluate_exists: Check if tracks match criteria
    evaluate_count: Count matching tracks and compare
    matches_track: Check if a single track matches filter criteria

Usage:
    from video_policy_orchestrator.policy.conditions import evaluate_condition
    from video_policy_orchestrator.policy.models import ExistsCondition, TrackFilters

    condition = ExistsCondition(track_type="video", filters=TrackFilters())
    result = evaluate_condition(condition, tracks)
"""
