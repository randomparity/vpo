"""Data models for Video Policy Orchestrator database.

DEPRECATED: This module is a backward-compatibility shim. All exports have been
moved to the following modules:
- types.py: Enums, dataclasses, and type definitions
- queries.py: CRUD operations for database tables
- views.py: Aggregated view query functions for UI

For new code, import from the db package directly:
    from video_policy_orchestrator.db import FileRecord, get_file_by_path

Or import from the specific submodule:
    from video_policy_orchestrator.db.types import FileRecord
    from video_policy_orchestrator.db.queries import get_file_by_path
"""

# Re-export everything for backward compatibility
# Types: Enums
# Queries: File operations
# Queries: Track operations
# Queries: Plugin acknowledgment operations
# Queries: Job operations
# Queries: Transcription result operations
# Queries: Language analysis operations
from .queries import (
    delete_file,
    delete_job,
    delete_language_analysis_for_file,
    delete_language_analysis_result,
    delete_old_jobs,
    delete_plugin_acknowledgment,
    delete_tracks_for_file,
    delete_transcription_results_for_file,
    get_acknowledgments_for_plugin,
    get_all_jobs,
    get_file_by_id,
    get_file_by_path,
    get_job,
    get_jobs_by_id_prefix,
    get_jobs_by_status,
    get_jobs_filtered,
    get_language_analysis_by_file_hash,
    get_language_analysis_result,
    get_language_segments,
    get_plugin_acknowledgment,
    get_queued_jobs,
    get_tracks_for_file,
    get_transcription_result,
    get_transcriptions_for_tracks,
    insert_file,
    insert_job,
    insert_plugin_acknowledgment,
    insert_track,
    is_plugin_acknowledged,
    update_job_output,
    update_job_progress,
    update_job_status,
    update_job_worker,
    upsert_file,
    upsert_language_analysis_result,
    upsert_language_segments,
    upsert_tracks_for_file,
    upsert_transcription_result,
)

# Types: Domain models
# Types: Database records
# Types: View models
# Types: Helper functions
from .types import (
    FileInfo,
    FileListViewItem,
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
    PlanRecord,
    PlanStatus,
    PluginAcknowledgment,
    TrackClassification,
    TrackInfo,
    TrackRecord,
    TranscriptionDetailView,
    TranscriptionListViewItem,
    TranscriptionResultRecord,
    tracks_to_track_info,
)

# Views: Library list view queries
# Views: Transcription view queries
from .views import (
    get_distinct_audio_languages,
    get_distinct_audio_languages_typed,
    get_files_filtered,
    get_files_filtered_typed,
    get_files_with_transcriptions,
    get_files_with_transcriptions_typed,
    get_transcription_detail,
    get_transcription_detail_typed,
)

__all__ = [
    # Enums
    "JobStatus",
    "JobType",
    "OperationStatus",
    "PlanStatus",
    "TrackClassification",
    # Domain models
    "FileInfo",
    "IntrospectionResult",
    "TrackInfo",
    # Database records
    "FileRecord",
    "Job",
    "JobProgress",
    "LanguageAnalysisResultRecord",
    "LanguageSegmentRecord",
    "OperationRecord",
    "PlanRecord",
    "PluginAcknowledgment",
    "TrackRecord",
    "TranscriptionResultRecord",
    # View models
    "FileListViewItem",
    "LanguageOption",
    "TranscriptionDetailView",
    "TranscriptionListViewItem",
    # Helper functions
    "tracks_to_track_info",
    # File operations
    "delete_file",
    "get_file_by_id",
    "get_file_by_path",
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
    "delete_language_analysis_for_file",
    "delete_language_analysis_result",
    "get_language_analysis_by_file_hash",
    "get_language_analysis_result",
    "get_language_segments",
    "upsert_language_analysis_result",
    "upsert_language_segments",
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
]
