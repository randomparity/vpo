"""Tests for workflow phase executor helper functions.

Tests the get_language_results_for_tracks helper that fetches language
analysis results from the database for policy evaluation.
"""

import logging
import sqlite3
from datetime import datetime, timezone

from vpo.db.types import (
    LanguageAnalysisResultRecord,
    LanguageSegmentRecord,
    TrackInfo,
)
from vpo.workflow.phases.executor.helpers import get_language_results_for_tracks


def create_language_analysis(
    conn: sqlite3.Connection,
    track_id: int,
    primary_language: str = "eng",
    primary_percentage: float = 0.85,
) -> int:
    """Create a language analysis record and return its ID."""
    from vpo.db.queries import upsert_language_analysis_result, upsert_language_segments

    now = datetime.now(timezone.utc).isoformat()
    record = LanguageAnalysisResultRecord(
        id=None,
        track_id=track_id,
        file_hash="hash123",
        primary_language=primary_language,
        primary_percentage=primary_percentage,
        classification="MULTI_LANGUAGE"
        if primary_percentage < 0.95
        else "SINGLE_LANGUAGE",
        analysis_metadata=(
            '{"plugin_name": "whisper", "plugin_version": "1.0.0", '
            '"model_name": "base", "sample_positions": [0.0, 60.0], '
            '"sample_duration": 30.0, "total_duration": 120.0, "speech_ratio": 0.8}'
        ),
        created_at=now,
        updated_at=now,
    )
    analysis_id = upsert_language_analysis_result(conn, record)

    # Add segments
    segments = [
        LanguageSegmentRecord(
            id=None,
            analysis_id=analysis_id,
            language_code=primary_language,
            start_time=0.0,
            end_time=30.0,
            confidence=0.95,
        ),
        LanguageSegmentRecord(
            id=None,
            analysis_id=analysis_id,
            language_code="spa",
            start_time=30.0,
            end_time=60.0,
            confidence=0.90,
        ),
    ]
    upsert_language_segments(conn, analysis_id, segments)

    return analysis_id


class TestGetLanguageResultsForTracks:
    """Tests for get_language_results_for_tracks helper function."""

    def test_no_audio_tracks_returns_none(self, db_conn):
        """Returns None when no audio tracks in list."""
        tracks = [
            TrackInfo(id=1, index=0, track_type="video", codec="h264", language="und"),
            TrackInfo(
                id=2, index=1, track_type="subtitle", codec="srt", language="eng"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is None

    def test_tracks_without_db_ids_returns_none(self, db_conn):
        """Returns None when audio tracks have no database IDs."""
        tracks = [
            TrackInfo(
                id=None, index=0, track_type="video", codec="h264", language="und"
            ),
            TrackInfo(
                id=None, index=1, track_type="audio", codec="aac", language="eng"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is None

    def test_no_analysis_results_returns_none(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returns None when no analysis results in database."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()

        tracks = [
            TrackInfo(
                id=track_id, index=1, track_type="audio", codec="aac", language="eng"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is None

    def test_returns_results_with_segments(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returns LanguageAnalysisResult with segments for matching tracks."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        create_language_analysis(db_conn, track_id, "eng", 0.85)

        tracks = [
            TrackInfo(
                id=track_id, index=1, track_type="audio", codec="aac", language="eng"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is not None
        assert track_id in result
        analysis = result[track_id]
        assert analysis.primary_language == "eng"
        assert analysis.primary_percentage == 0.85
        assert analysis.is_multi_language is True
        assert len(analysis.segments) == 2

    def test_filters_to_audio_tracks_only(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Only queries audio tracks, ignores video and subtitle tracks."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        video_id = insert_test_track(
            file_id=file_id, track_index=0, track_type="video", codec="h264"
        )
        audio_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        sub_id = insert_test_track(
            file_id=file_id,
            track_index=2,
            track_type="subtitle",
            codec="h264",
            language="eng",
        )
        db_conn.commit()
        create_language_analysis(db_conn, audio_id, "eng", 0.85)

        tracks = [
            TrackInfo(
                id=video_id, index=0, track_type="video", codec="h264", language="und"
            ),
            TrackInfo(
                id=audio_id, index=1, track_type="audio", codec="aac", language="eng"
            ),
            TrackInfo(
                id=sub_id, index=2, track_type="subtitle", codec="srt", language="eng"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is not None
        assert len(result) == 1
        assert audio_id in result
        assert video_id not in result
        assert sub_id not in result

    def test_partial_results_for_multiple_tracks(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returns results only for tracks with analysis."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        audio1_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        audio2_id = insert_test_track(
            file_id=file_id,
            track_index=2,
            track_type="audio",
            codec="aac",
            language="spa",
        )
        db_conn.commit()
        # Only create analysis for first track
        create_language_analysis(db_conn, audio1_id, "eng", 0.85)

        tracks = [
            TrackInfo(
                id=audio1_id, index=1, track_type="audio", codec="aac", language="eng"
            ),
            TrackInfo(
                id=audio2_id, index=2, track_type="audio", codec="aac", language="spa"
            ),
        ]

        result = get_language_results_for_tracks(db_conn, tracks)

        assert result is not None
        assert len(result) == 1
        assert audio1_id in result
        assert audio2_id not in result

    def test_logs_debug_when_no_audio_tracks(self, db_conn, caplog):
        """Verify debug logging when no audio tracks found."""
        tracks = [
            TrackInfo(id=1, index=0, track_type="video", codec="h264", language="und"),
        ]

        with caplog.at_level(logging.DEBUG):
            result = get_language_results_for_tracks(db_conn, tracks)

        assert result is None
        assert "No audio tracks with database IDs" in caplog.text

    def test_logs_debug_when_no_analysis_results(
        self, db_conn, insert_test_file, insert_test_track, caplog
    ):
        """Verify debug logging when no analysis results in database."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()

        tracks = [
            TrackInfo(
                id=track_id, index=1, track_type="audio", codec="aac", language="eng"
            ),
        ]

        with caplog.at_level(logging.DEBUG):
            result = get_language_results_for_tracks(db_conn, tracks)

        assert result is None
        assert "No language analysis results found for" in caplog.text
        assert "1 audio track(s)" in caplog.text
