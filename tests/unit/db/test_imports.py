"""Tests for database module import compatibility.

Verifies that all imports work from:
1. The db package (__init__.py)
2. The models.py backward-compat shim
3. The individual submodules (types.py, queries.py, views.py)
"""


class TestPackageImports:
    """Test imports from video_policy_orchestrator.db package."""

    def test_enum_imports(self):
        """Test enum imports from package."""
        from video_policy_orchestrator.db import (
            JobStatus,
            JobType,
            OperationStatus,
            PlanStatus,
            TrackClassification,
        )

        assert JobStatus.QUEUED.value == "queued"
        assert JobType.SCAN.value == "scan"
        assert OperationStatus.PENDING.value == "PENDING"
        assert PlanStatus.PENDING.value == "pending"
        assert TrackClassification.MAIN.value == "main"

    def test_domain_model_imports(self):
        """Test domain model imports from package."""
        from video_policy_orchestrator.db import (
            FileInfo,
            IntrospectionResult,
            TrackInfo,
        )

        # Verify types are accessible
        assert TrackInfo.__dataclass_fields__
        assert FileInfo.__dataclass_fields__
        assert IntrospectionResult.__dataclass_fields__

    def test_record_imports(self):
        """Test database record imports from package."""
        from video_policy_orchestrator.db import (
            FileRecord,
            Job,
            LanguageAnalysisResultRecord,
            LanguageSegmentRecord,
            OperationRecord,
            PlanRecord,
            PluginAcknowledgment,
            TrackRecord,
            TranscriptionResultRecord,
        )

        # Verify types are accessible
        assert FileRecord.__dataclass_fields__
        assert TrackRecord.__dataclass_fields__
        assert Job.__dataclass_fields__
        assert OperationRecord.__dataclass_fields__
        assert PlanRecord.__dataclass_fields__
        assert PluginAcknowledgment.__dataclass_fields__
        assert TranscriptionResultRecord.__dataclass_fields__
        assert LanguageAnalysisResultRecord.__dataclass_fields__
        assert LanguageSegmentRecord.__dataclass_fields__

    def test_view_model_imports(self):
        """Test view model imports from package."""
        from video_policy_orchestrator.db import (
            FileListViewItem,
            LanguageOption,
            TranscriptionDetailView,
            TranscriptionListViewItem,
        )

        # Verify types are accessible
        assert FileListViewItem.__dataclass_fields__
        assert LanguageOption.__dataclass_fields__
        assert TranscriptionListViewItem.__dataclass_fields__
        assert TranscriptionDetailView.__dataclass_fields__

    def test_file_operation_imports(self):
        """Test file operation imports from package."""
        from video_policy_orchestrator.db import (
            delete_file,
            get_file_by_id,
            get_file_by_path,
            insert_file,
            upsert_file,
        )

        # Verify functions are callable
        assert callable(insert_file)
        assert callable(upsert_file)
        assert callable(get_file_by_path)
        assert callable(get_file_by_id)
        assert callable(delete_file)

    def test_track_operation_imports(self):
        """Test track operation imports from package."""
        from video_policy_orchestrator.db import (
            delete_tracks_for_file,
            get_tracks_for_file,
            insert_track,
            upsert_tracks_for_file,
        )

        # Verify functions are callable
        assert callable(insert_track)
        assert callable(get_tracks_for_file)
        assert callable(delete_tracks_for_file)
        assert callable(upsert_tracks_for_file)

    def test_job_operation_imports(self):
        """Test job operation imports from package."""
        from video_policy_orchestrator.db import (
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

        # Verify functions are callable
        assert callable(insert_job)
        assert callable(get_job)
        assert callable(update_job_status)
        assert callable(update_job_progress)
        assert callable(update_job_worker)
        assert callable(update_job_output)
        assert callable(get_queued_jobs)
        assert callable(get_jobs_by_status)
        assert callable(get_all_jobs)
        assert callable(get_jobs_by_id_prefix)
        assert callable(get_jobs_filtered)
        assert callable(delete_job)
        assert callable(delete_old_jobs)

    def test_view_query_imports(self):
        """Test view query function imports from package."""
        from video_policy_orchestrator.db import (
            get_distinct_audio_languages,
            get_distinct_audio_languages_typed,
            get_files_filtered,
            get_files_filtered_typed,
            get_files_with_transcriptions,
            get_files_with_transcriptions_typed,
            get_transcription_detail,
            get_transcription_detail_typed,
        )

        # Verify functions are callable
        assert callable(get_files_filtered)
        assert callable(get_files_filtered_typed)
        assert callable(get_distinct_audio_languages)
        assert callable(get_distinct_audio_languages_typed)
        assert callable(get_files_with_transcriptions)
        assert callable(get_files_with_transcriptions_typed)
        assert callable(get_transcription_detail)
        assert callable(get_transcription_detail_typed)


class TestModelsShimImports:
    """Test imports from backward-compat models.py shim."""

    def test_enum_imports_from_models(self):
        """Test enum imports from models module."""
        from video_policy_orchestrator.db.models import (
            JobStatus,
            JobType,
            OperationStatus,
            PlanStatus,
            TrackClassification,
        )

        assert JobStatus.QUEUED.value == "queued"
        assert JobType.SCAN.value == "scan"
        assert OperationStatus.PENDING.value == "PENDING"
        assert PlanStatus.PENDING.value == "pending"
        assert TrackClassification.MAIN.value == "main"

    def test_record_imports_from_models(self):
        """Test database record imports from models module."""
        from video_policy_orchestrator.db.models import (
            FileRecord,
            Job,
            TrackRecord,
        )

        assert FileRecord.__dataclass_fields__
        assert TrackRecord.__dataclass_fields__
        assert Job.__dataclass_fields__

    def test_function_imports_from_models(self):
        """Test function imports from models module."""
        from video_policy_orchestrator.db.models import (
            get_file_by_path,
            get_files_filtered,
            get_tracks_for_file,
            insert_file,
            upsert_file,
        )

        assert callable(insert_file)
        assert callable(upsert_file)
        assert callable(get_file_by_path)
        assert callable(get_tracks_for_file)
        assert callable(get_files_filtered)


class TestSubmoduleImports:
    """Test imports from individual submodules."""

    def test_types_module_imports(self):
        """Test imports from types.py submodule."""
        from video_policy_orchestrator.db.types import (
            FileListViewItem,
            FileRecord,
            JobStatus,
            TrackInfo,
            TrackRecord,
            tracks_to_track_info,
        )

        assert JobStatus.QUEUED.value == "queued"
        assert FileRecord.__dataclass_fields__
        assert TrackRecord.__dataclass_fields__
        assert TrackInfo.__dataclass_fields__
        assert FileListViewItem.__dataclass_fields__
        assert callable(tracks_to_track_info)

    def test_queries_module_imports(self):
        """Test imports from queries.py submodule."""
        from video_policy_orchestrator.db.queries import (
            get_file_by_id,
            get_file_by_path,
            get_job,
            get_tracks_for_file,
            insert_file,
            insert_job,
            upsert_file,
        )

        assert callable(insert_file)
        assert callable(upsert_file)
        assert callable(get_file_by_path)
        assert callable(get_file_by_id)
        assert callable(get_tracks_for_file)
        assert callable(insert_job)
        assert callable(get_job)

    def test_views_module_imports(self):
        """Test imports from views.py submodule."""
        from video_policy_orchestrator.db.views import (
            get_distinct_audio_languages,
            get_distinct_audio_languages_typed,
            get_files_filtered,
            get_files_filtered_typed,
            get_files_with_transcriptions,
            get_files_with_transcriptions_typed,
            get_transcription_detail,
            get_transcription_detail_typed,
        )

        assert callable(get_files_filtered)
        assert callable(get_files_filtered_typed)
        assert callable(get_distinct_audio_languages)
        assert callable(get_distinct_audio_languages_typed)
        assert callable(get_files_with_transcriptions)
        assert callable(get_files_with_transcriptions_typed)
        assert callable(get_transcription_detail)
        assert callable(get_transcription_detail_typed)


class TestImportEquivalence:
    """Test that imports from different modules return the same objects."""

    def test_filerecord_is_same_class(self):
        """FileRecord should be the same class from all import paths."""
        from video_policy_orchestrator.db import FileRecord as FR1
        from video_policy_orchestrator.db.models import FileRecord as FR2
        from video_policy_orchestrator.db.types import FileRecord as FR3

        assert FR1 is FR2
        assert FR2 is FR3

    def test_get_file_by_path_is_same_function(self):
        """get_file_by_path should be the same function from all import paths."""
        from video_policy_orchestrator.db import get_file_by_path as gfbp1
        from video_policy_orchestrator.db.models import get_file_by_path as gfbp2
        from video_policy_orchestrator.db.queries import get_file_by_path as gfbp3

        assert gfbp1 is gfbp2
        assert gfbp2 is gfbp3

    def test_get_files_filtered_typed_is_same_function(self):
        """get_files_filtered_typed should be the same from all import paths."""
        from video_policy_orchestrator.db import get_files_filtered_typed as gfft1
        from video_policy_orchestrator.db.models import (
            get_files_filtered_typed as gfft2,
        )
        from video_policy_orchestrator.db.views import get_files_filtered_typed as gfft3

        assert gfft1 is gfft2
        assert gfft2 is gfft3
