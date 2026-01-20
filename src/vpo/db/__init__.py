"""Database module for Video Policy Orchestrator.

This module provides the public API for database operations. All types and
functions are re-exported here for convenient access.

Module organization:
- types.py: Enums, dataclasses, and type definitions
- queries.py: CRUD operations for database tables
- views.py: Aggregated view query functions for UI
- operations.py: Plan CRUD and operation audit logging
- schema.py: Schema creation and migrations

Usage:
    from vpo.db import FileRecord, get_file_by_path
    from vpo.db import FileListViewItem, get_files_filtered_typed
"""

# Types: Enums
# Queries: File operations
# Queries: Track operations
# Queries: Plugin acknowledgment operations
# Queries: Job operations
# Queries: Transcription result operations
# Queries: Language analysis operations
# Queries: Processing statistics operations
# Operations: Operation audit logging and plan CRUD
from .operations import (
    PLAN_STATUS_TRANSITIONS,
    InvalidPlanTransitionError,
    create_operation,
    create_plan,
    get_operation,
    get_operations_for_file,
    get_pending_operations,
    get_plan_by_id,
    get_plans_filtered,
    update_operation_status,
    update_plan_status,
)
from .queries import (
    delete_all_analysis,
    delete_analysis_by_path_prefix,
    delete_analysis_for_file,
    delete_classifications_for_file,
    delete_file,
    delete_job,
    delete_language_analysis_for_file,
    delete_language_analysis_result,
    delete_old_jobs,
    delete_plugin_acknowledgment,
    delete_track_classification,
    delete_tracks_for_file,
    delete_transcription_results_for_file,
    get_acknowledgments_for_plugin,
    get_action_results_for_stats,
    get_all_jobs,
    get_classifications_for_file,
    get_classifications_for_tracks,
    get_file_by_id,
    get_file_by_path,
    get_file_ids_by_path_prefix,
    get_files_by_paths,
    get_job,
    get_jobs_by_id_prefix,
    get_jobs_by_status,
    get_jobs_filtered,
    get_language_analysis_by_file_hash,
    get_language_analysis_result,
    get_language_segments,
    get_performance_metrics_for_stats,
    get_plugin_acknowledgment,
    get_processing_stats_by_id,
    get_processing_stats_for_file,
    get_queued_jobs,
    get_track_classification,
    get_tracks_for_file,
    get_transcription_result,
    get_transcriptions_for_tracks,
    insert_action_result,
    insert_file,
    insert_job,
    insert_performance_metric,
    insert_plugin_acknowledgment,
    insert_processing_stats,
    insert_track,
    is_plugin_acknowledged,
    update_job_output,
    update_job_progress,
    update_job_status,
    update_job_worker,
    upsert_file,
    upsert_language_analysis_result,
    upsert_language_segments,
    upsert_track_classification,
    upsert_tracks_for_file,
    upsert_transcription_result,
)

# Types: Domain models
# Types: Database records
# Types: View models
# Types: Helper functions
# Types: Type aliases
from .types import (
    ActionResultRecord,
    ActionSummary,
    AnalysisStatusSummary,
    CommentaryStatus,
    DetectionMethod,
    FileAnalysisStatus,
    FileInfo,
    FileListViewItem,
    FileProcessingHistory,
    FileRecord,
    IntrospectionResult,
    Job,
    JobProgress,
    JobStatus,
    JobType,
    LanguageAnalysisResultRecord,
    LanguageOption,
    LanguageSegmentRecord,
    OperationRecord,
    OperationStatus,
    OriginalDubbedStatus,
    PerformanceMetricsRecord,
    PlanRecord,
    PlanStatus,
    PluginAcknowledgment,
    PluginMetadataDict,
    PolicyStats,
    ProcessingStatsRecord,
    ScanErrorView,
    StatsDetailView,
    StatsSummary,
    TrackAnalysisDetail,
    TrackClassification,
    TrackClassificationRecord,
    TrackInfo,
    TrackRecord,
    TranscriptionDetailView,
    TranscriptionListViewItem,
    TranscriptionResultRecord,
    tracks_to_track_info,
)

# Views: Library list view queries
# Views: Transcription view queries
# Views: Scan errors view queries
# Views: Processing statistics view queries
# Views: Plugin data view queries
# Views: Language analysis view queries
# Views: Pagination constants
from .views import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    get_analysis_status_summary,
    get_distinct_audio_languages,
    get_distinct_audio_languages_typed,
    get_file_analysis_detail,
    get_files_analysis_status,
    get_files_filtered,
    get_files_filtered_typed,
    get_files_with_plugin_data,
    get_files_with_transcriptions,
    get_files_with_transcriptions_typed,
    get_plugin_data_for_file,
    get_policy_stats,
    get_policy_stats_by_name,
    get_recent_stats,
    get_scan_errors_for_job,
    get_stats_detail,
    get_stats_for_file,
    get_stats_summary,
    get_transcription_detail,
    get_transcription_detail_typed,
)

__all__ = [
    # Enums
    "CommentaryStatus",
    "DetectionMethod",
    "JobStatus",
    "JobType",
    "OperationStatus",
    "OriginalDubbedStatus",
    "PlanStatus",
    "TrackClassification",
    # Domain models
    "FileInfo",
    "IntrospectionResult",
    "TrackInfo",
    # Database records
    "ActionResultRecord",
    "FileRecord",
    "Job",
    "JobProgress",
    "LanguageAnalysisResultRecord",
    "LanguageSegmentRecord",
    "OperationRecord",
    "PerformanceMetricsRecord",
    "PlanRecord",
    "PluginAcknowledgment",
    "ProcessingStatsRecord",
    "TrackClassificationRecord",
    "TrackRecord",
    "TranscriptionResultRecord",
    # View models
    "ActionSummary",
    "AnalysisStatusSummary",
    "FileAnalysisStatus",
    "FileListViewItem",
    "FileProcessingHistory",
    "LanguageOption",
    "PolicyStats",
    "ScanErrorView",
    "StatsDetailView",
    "StatsSummary",
    "TrackAnalysisDetail",
    "TranscriptionDetailView",
    "TranscriptionListViewItem",
    # Type aliases
    "PluginMetadataDict",
    # Helper functions
    "tracks_to_track_info",
    # File operations
    "delete_file",
    "get_file_by_id",
    "get_file_by_path",
    "get_files_by_paths",
    "insert_file",
    "upsert_file",
    # Track operations
    "delete_tracks_for_file",
    "get_tracks_for_file",
    "insert_track",
    "upsert_tracks_for_file",
    # Plugin acknowledgment operations
    "delete_plugin_acknowledgment",
    "get_acknowledgments_for_plugin",
    "get_plugin_acknowledgment",
    "insert_plugin_acknowledgment",
    "is_plugin_acknowledged",
    # Job operations
    "delete_job",
    "delete_old_jobs",
    "get_all_jobs",
    "get_job",
    "get_jobs_by_id_prefix",
    "get_jobs_by_status",
    "get_jobs_filtered",
    "get_queued_jobs",
    "insert_job",
    "update_job_output",
    "update_job_progress",
    "update_job_status",
    "update_job_worker",
    # Transcription result operations
    "delete_transcription_results_for_file",
    "get_transcription_result",
    "get_transcriptions_for_tracks",
    "upsert_transcription_result",
    # Language analysis operations
    "delete_all_analysis",
    "delete_analysis_by_path_prefix",
    "delete_analysis_for_file",
    "delete_language_analysis_for_file",
    "delete_language_analysis_result",
    "get_file_ids_by_path_prefix",
    "get_language_analysis_by_file_hash",
    "get_language_analysis_result",
    "get_language_segments",
    "upsert_language_analysis_result",
    "upsert_language_segments",
    # Processing statistics operations
    "get_action_results_for_stats",
    "get_performance_metrics_for_stats",
    "get_processing_stats_by_id",
    "get_processing_stats_for_file",
    "insert_action_result",
    "insert_performance_metric",
    "insert_processing_stats",
    # Track classification operations
    "delete_classifications_for_file",
    "delete_track_classification",
    "get_classifications_for_file",
    "get_classifications_for_tracks",
    "get_track_classification",
    "upsert_track_classification",
    # Operation audit logging
    "create_operation",
    "get_operation",
    "get_operations_for_file",
    "get_pending_operations",
    "update_operation_status",
    # Plan CRUD operations
    "create_plan",
    "get_plan_by_id",
    "get_plans_filtered",
    "update_plan_status",
    "InvalidPlanTransitionError",
    "PLAN_STATUS_TRANSITIONS",
    # Library list view queries
    "get_distinct_audio_languages",
    "get_distinct_audio_languages_typed",
    "get_files_filtered",
    "get_files_filtered_typed",
    # Transcription view queries
    "get_files_with_transcriptions",
    "get_files_with_transcriptions_typed",
    "get_transcription_detail",
    "get_transcription_detail_typed",
    # Scan errors view queries
    "get_scan_errors_for_job",
    # Processing statistics view queries
    "get_policy_stats",
    "get_policy_stats_by_name",
    "get_recent_stats",
    "get_stats_detail",
    "get_stats_for_file",
    "get_stats_summary",
    # Plugin data view queries
    "get_files_with_plugin_data",
    "get_plugin_data_for_file",
    # Language analysis view queries
    "get_analysis_status_summary",
    "get_file_analysis_detail",
    "get_files_analysis_status",
    # Pagination constants
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
]
