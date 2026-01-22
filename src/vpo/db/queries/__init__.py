"""Database query operations package.

This package provides CRUD operations for all database tables.
Functions are organized by domain but re-exported here for convenience.

Module organization:
- helpers.py: SQL utilities and row mapping functions
- files.py: File and track CRUD operations
- jobs.py: Job queue operations
- plugins.py: Plugin acknowledgment operations
- transcriptions.py: Transcription result operations
- analysis.py: Language analysis operations
- stats.py: Processing statistics operations
- classifications.py: Track classification operations

Usage:
    from vpo.db.queries import get_file_by_path, insert_job
"""

# Language analysis operations
from .analysis import (
    delete_all_analysis,
    delete_analysis_by_path_prefix,
    delete_analysis_for_file,
    delete_language_analysis_for_file,
    delete_language_analysis_result,
    get_file_ids_by_path_prefix,
    get_language_analysis_by_file_hash,
    get_language_analysis_for_tracks,
    get_language_analysis_result,
    get_language_segments,
    upsert_language_analysis_result,
    upsert_language_segments,
)

# Track classification operations
from .classifications import (
    delete_classifications_for_file,
    delete_track_classification,
    get_classifications_for_file,
    get_classifications_for_tracks,
    get_track_classification,
    upsert_track_classification,
)

# File and track operations
from .files import (
    delete_file,
    delete_tracks_for_file,
    get_file_by_id,
    get_file_by_path,
    get_files_by_paths,
    get_tracks_for_file,
    insert_file,
    insert_track,
    upsert_file,
    upsert_tracks_for_file,
)

# Job operations
from .jobs import (
    delete_job,
    delete_old_jobs,
    get_all_jobs,
    get_job,
    get_jobs_by_id_prefix,
    get_jobs_by_status,
    get_jobs_filtered,
    get_queued_jobs,
    insert_job,
    update_job_output,
    update_job_progress,
    update_job_status,
    update_job_worker,
)

# Plugin acknowledgment operations
from .plugins import (
    delete_plugin_acknowledgment,
    get_acknowledgments_for_plugin,
    get_plugin_acknowledgment,
    insert_plugin_acknowledgment,
    is_plugin_acknowledged,
)

# Processing statistics operations
from .stats import (
    delete_all_processing_stats,
    delete_processing_stats_before,
    delete_processing_stats_by_policy,
    get_action_results_for_stats,
    get_performance_metrics_for_stats,
    get_processing_stats_by_id,
    get_processing_stats_for_file,
    insert_action_result,
    insert_performance_metric,
    insert_processing_stats,
)

# Transcription result operations
from .transcriptions import (
    delete_transcription_results_for_file,
    get_transcription_result,
    get_transcriptions_for_tracks,
    upsert_transcription_result,
)

__all__ = [
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
    "get_language_analysis_for_tracks",
    "get_language_analysis_result",
    "get_language_segments",
    "upsert_language_analysis_result",
    "upsert_language_segments",
    # Processing statistics operations
    "delete_all_processing_stats",
    "delete_processing_stats_before",
    "delete_processing_stats_by_policy",
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
]
