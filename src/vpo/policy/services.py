"""Policy service functions.

This module provides high-level service functions for policy operations,
extracted from HTTP handlers to enable testability and code reuse.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vpo.policy.discovery import (
    DEFAULT_POLICIES_DIR,
    discover_policies,
)
from vpo.policy.view_models import (
    PolicyListItem,
    PolicyListResponse,
    format_language_preferences,
)

logger = logging.getLogger(__name__)


def get_default_policy_path() -> Path | None:
    """Get the default policy path from the active profile.

    Returns:
        Path to default policy file, or None if not configured or error.
    """
    try:
        from vpo.config.profiles import get_active_profile

        profile = get_active_profile()
        if profile and profile.default_policy:
            return profile.default_policy
    except (ImportError, AttributeError) as e:
        logger.debug("Could not load default policy from profile: %s", e)
    return None


def list_policies(policies_dir: Path | None = None) -> PolicyListResponse:
    """Discover and format all policies for display.

    Discovers policy files from the specified directory (or default),
    parses their metadata, and returns a response suitable for both
    HTML templates and JSON API responses.

    Args:
        policies_dir: Directory to scan for policy files.
            Defaults to ~/.vpo/policies/ if not specified.

    Returns:
        PolicyListResponse with all discovered policies and metadata.
    """
    if policies_dir is None:
        policies_dir = DEFAULT_POLICIES_DIR

    default_policy_path = get_default_policy_path()

    summaries, default_missing = discover_policies(
        policies_dir,
        default_policy_path,
    )

    # Convert PolicySummary objects to PolicyListItem
    policies = [
        PolicyListItem(
            name=s.name,
            filename=s.filename,
            file_path=s.file_path,
            last_modified=s.last_modified,
            schema_version=s.schema_version,
            description=s.description,
            category=s.category,
            audio_languages=format_language_preferences(s.audio_languages),
            subtitle_languages=format_language_preferences(s.subtitle_languages),
            has_transcode=s.has_transcode,
            has_transcription=s.has_transcription,
            is_default=s.is_default,
            parse_error=s.parse_error,
        )
        for s in summaries
    ]

    return PolicyListResponse(
        policies=policies,
        total=len(policies),
        policies_directory=str(policies_dir),
        default_policy_path=str(default_policy_path) if default_policy_path else None,
        default_policy_missing=default_missing,
        directory_exists=policies_dir.exists(),
    )
