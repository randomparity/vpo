"""Data models for Web UI Shell.

This package defines the navigation and template context structures
used for server-side rendering. All types are re-exported here for
backward compatibility with existing imports.
"""

from __future__ import annotations

# Re-export formatting utilities from core for backward compatibility
from vpo.core.formatting import (
    format_audio_languages,
    format_file_size,
    get_resolution_label,
)

# Re-export generate_summary_text from jobs module for backward compatibility
from vpo.jobs.summary import (
    generate_summary_text as generate_summary_text,
)

# Re-export policy view models for backward compatibility
from vpo.policy.view_models import (
    PolicyListItem as PolicyListItem,
)
from vpo.policy.view_models import (
    PolicyListResponse as PolicyListResponse,
)
from vpo.policy.view_models import (
    format_language_preferences as format_language_preferences,
)

# Base models (navigation, templates)
from vpo.server.ui.models.base import (
    DEFAULT_SECTION,
    NAVIGATION_ITEMS,
    AboutInfo,
    NavigationItem,
    NavigationState,
    TemplateContext,
)

# File detail models
from vpo.server.ui.models.file_detail import (
    FileDetailContext,
    FileDetailItem,
    FileDetailResponse,
    TrackDetailItem,
    build_file_detail_item,
)

# Job models
from vpo.server.ui.models.jobs import (
    JobDetailContext,
    JobDetailItem,
    JobFilterParams,
    JobListContext,
    JobListItem,
    JobListResponse,
    JobLogsResponse,
    ScanErrorItem,
    ScanErrorsResponse,
    build_job_detail_item,
)

# Library models
from vpo.server.ui.models.library import (
    VALID_RESOLUTIONS,
    FileListItem,
    FileListResponse,
    LibraryContext,
    LibraryFilterParams,
    TrackTranscriptionInfo,
    group_tracks_by_type,
)

# Plan models
from vpo.server.ui.models.plans import (
    PLAN_STATUS_BADGES,
    PlanActionResponse,
    PlanDetailContext,
    PlanDetailItem,
    PlanFilterParams,
    PlanListItem,
    PlanListResponse,
    PlannedActionItem,
    PlansContext,
)

# Plugin models
from vpo.server.ui.models.plugins import (
    FilePluginDataResponse,
    PluginDataContext,
    PluginFileItem,
    PluginFilesResponse,
    PluginInfo,
    PluginListResponse,
)

# Policy models
from vpo.server.ui.models.policies import (
    ChangedFieldItem,
    PoliciesContext,
    PolicyEditorContext,
    PolicyEditorRequest,
    PolicySaveSuccessResponse,
    PolicyValidateResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)

# Transcription models
from vpo.server.ui.models.transcriptions import (
    TRANSCRIPT_DISPLAY_LIMIT,
    TRANSCRIPT_HIGHLIGHT_LIMIT,
    TranscriptionDetailContext,
    TranscriptionDetailItem,
    TranscriptionDetailResponse,
    TranscriptionFilterParams,
    TranscriptionListItem,
    TranscriptionListResponse,
    build_transcription_detail_item,
    format_detected_languages,
    get_classification_reasoning,
    get_confidence_level,
    highlight_keywords_in_transcript,
)

__all__ = [
    # Re-exported from core.formatting for backward compatibility
    "format_file_size",
    "get_resolution_label",
    "format_audio_languages",
    # Re-exported from jobs.summary for backward compatibility
    "generate_summary_text",
    # Re-exported from policy.view_models for backward compatibility
    "PolicyListItem",
    "PolicyListResponse",
    "format_language_preferences",
    # Base models
    "AboutInfo",
    "NavigationItem",
    "NavigationState",
    "TemplateContext",
    "NAVIGATION_ITEMS",
    "DEFAULT_SECTION",
    # Job models
    "JobFilterParams",
    "JobListItem",
    "JobListResponse",
    "JobListContext",
    "JobDetailItem",
    "JobLogsResponse",
    "ScanErrorItem",
    "ScanErrorsResponse",
    "JobDetailContext",
    "build_job_detail_item",
    # Library models
    "VALID_RESOLUTIONS",
    "LibraryFilterParams",
    "FileListItem",
    "FileListResponse",
    "LibraryContext",
    "TrackTranscriptionInfo",
    "group_tracks_by_type",
    # File detail models
    "TrackDetailItem",
    "FileDetailItem",
    "FileDetailResponse",
    "FileDetailContext",
    "build_file_detail_item",
    # Transcription models
    "TRANSCRIPT_DISPLAY_LIMIT",
    "TRANSCRIPT_HIGHLIGHT_LIMIT",
    "get_confidence_level",
    "format_detected_languages",
    "get_classification_reasoning",
    "highlight_keywords_in_transcript",
    "build_transcription_detail_item",
    "TranscriptionFilterParams",
    "TranscriptionListItem",
    "TranscriptionListResponse",
    "TranscriptionDetailItem",
    "TranscriptionDetailResponse",
    "TranscriptionDetailContext",
    # Policy models
    "PoliciesContext",
    "PolicyEditorContext",
    "PolicyEditorRequest",
    "ValidationErrorItem",
    "ValidationErrorResponse",
    "ChangedFieldItem",
    "PolicySaveSuccessResponse",
    "PolicyValidateResponse",
    # Plan models
    "PLAN_STATUS_BADGES",
    "PlanFilterParams",
    "PlanListItem",
    "PlanListResponse",
    "PlansContext",
    "PlanActionResponse",
    "PlanDetailItem",
    "PlanDetailContext",
    "PlannedActionItem",
    # Plugin models
    "PluginInfo",
    "PluginListResponse",
    "PluginFileItem",
    "PluginFilesResponse",
    "FilePluginDataResponse",
    "PluginDataContext",
]
