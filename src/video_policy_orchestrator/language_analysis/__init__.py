"""Language analysis module for multi-language audio detection.

This module provides functionality for detecting multiple languages in audio tracks,
classifying tracks as single or multi-language, and caching analysis results.
"""

from video_policy_orchestrator.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguagePercentage,
    LanguageSegment,
)

__all__ = [
    "AnalysisMetadata",
    "LanguageAnalysisResult",
    "LanguageClassification",
    "LanguagePercentage",
    "LanguageSegment",
]
