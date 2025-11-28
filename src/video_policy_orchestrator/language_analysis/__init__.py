"""Language analysis module for multi-language audio detection.

This module provides functionality for detecting multiple languages in audio tracks,
classifying tracks as single or multi-language, and caching analysis results.
"""

from video_policy_orchestrator.language_analysis.formatters import (
    format_human,
    format_json,
)
from video_policy_orchestrator.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguagePercentage,
    LanguageSegment,
)
from video_policy_orchestrator.language_analysis.service import (
    LanguageAnalysisError,
    analyze_track_languages,
    get_cached_analysis,
    invalidate_analysis_cache,
    persist_analysis_result,
)

__all__ = [
    "AnalysisMetadata",
    "LanguageAnalysisError",
    "LanguageAnalysisResult",
    "LanguageClassification",
    "LanguagePercentage",
    "LanguageSegment",
    "analyze_track_languages",
    "format_human",
    "format_json",
    "get_cached_analysis",
    "invalidate_analysis_cache",
    "persist_analysis_result",
]
