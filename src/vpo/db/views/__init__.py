"""View query functions for Video Policy Orchestrator database.

This package contains query functions that return aggregated/joined data
for UI views. These functions typically:
- JOIN multiple tables
- Use GROUP BY for aggregation
- Return view model dataclasses for typed results

The dict-returning versions are kept for backward compatibility.
New code should use the _typed variants that return dataclasses.
"""

# Re-export types for backward compatibility (originally imported in views.py)
from ..types import (
    ActionSummary,
    AnalysisStatusSummary,
    DistributionItem,
    FileAnalysisStatus,
    FileListViewItem,
    FileProcessingHistory,
    LanguageOption,
    LibraryDistribution,
    PolicyStats,
    ScanErrorView,
    StatsDetailView,
    StatsSummary,
    TrackAnalysisDetail,
    TranscriptionDetailView,
    TranscriptionListViewItem,
    TrendDataPoint,
)

# Language analysis views
from .analysis import (
    get_analysis_status_summary,
    get_file_analysis_detail,
    get_files_analysis_status,
)

# Pagination constants and helpers
from .helpers import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, _clamp_limit

# Library list views
from .library import (
    get_distinct_audio_languages,
    get_distinct_audio_languages_typed,
    get_files_filtered,
    get_files_filtered_typed,
    get_library_distribution,
    get_missing_files,
)

# Plugin data views
from .plugins import get_files_with_plugin_data, get_plugin_data_for_file

# Scan error views
from .scan_errors import get_scan_errors_for_job

# Library snapshots
from .snapshots import (
    LibrarySnapshotPoint,
    get_library_snapshots,
    insert_library_snapshot,
)

# Processing statistics views
from .stats import (
    get_policy_stats,
    get_policy_stats_by_name,
    get_recent_stats,
    get_stats_detail,
    get_stats_for_file,
    get_stats_summary,
    get_stats_trends,
)

# Transcription views
from .transcriptions import (
    get_files_with_transcriptions,
    get_files_with_transcriptions_typed,
    get_transcription_detail,
    get_transcription_detail_typed,
)

__all__ = [
    # Types (re-exported for backward compatibility)
    "ActionSummary",
    "AnalysisStatusSummary",
    "DistributionItem",
    "FileAnalysisStatus",
    "FileListViewItem",
    "FileProcessingHistory",
    "LanguageOption",
    "LibraryDistribution",
    "PolicyStats",
    "ScanErrorView",
    "StatsDetailView",
    "StatsSummary",
    "TrackAnalysisDetail",
    "TranscriptionDetailView",
    "TranscriptionListViewItem",
    "TrendDataPoint",
    # Pagination
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "_clamp_limit",
    # Analysis
    "get_analysis_status_summary",
    "get_file_analysis_detail",
    "get_files_analysis_status",
    # Library
    "get_distinct_audio_languages",
    "get_distinct_audio_languages_typed",
    "get_files_filtered",
    "get_files_filtered_typed",
    "get_library_distribution",
    "get_missing_files",
    # Plugins
    "get_files_with_plugin_data",
    "get_plugin_data_for_file",
    # Scan errors
    "get_scan_errors_for_job",
    # Snapshots
    "LibrarySnapshotPoint",
    "get_library_snapshots",
    "insert_library_snapshot",
    # Stats
    "get_policy_stats",
    "get_policy_stats_by_name",
    "get_recent_stats",
    "get_stats_detail",
    "get_stats_for_file",
    "get_stats_summary",
    "get_stats_trends",
    # Transcriptions
    "get_files_with_transcriptions",
    "get_files_with_transcriptions_typed",
    "get_transcription_detail",
    "get_transcription_detail_typed",
]
