"""Tests for language analysis batch query functions."""

import sqlite3
from datetime import datetime, timezone

from vpo.db.queries import (
    get_language_analysis_for_tracks,
    get_language_segments_for_analyses,
    upsert_language_analysis_result,
    upsert_language_segments,
)
from vpo.db.types import LanguageAnalysisResultRecord, LanguageSegmentRecord


def create_language_analysis(
    conn: sqlite3.Connection,
    track_id: int,
    primary_language: str = "eng",
    primary_percentage: float = 0.85,
    classification: str = "MULTI_LANGUAGE",
) -> int:
    """Create a language analysis record and return its ID."""
    now = datetime.now(timezone.utc).isoformat()
    record = LanguageAnalysisResultRecord(
        id=None,
        track_id=track_id,
        file_hash="hash123",
        primary_language=primary_language,
        primary_percentage=primary_percentage,
        classification=classification,
        analysis_metadata='{"plugin_name": "whisper", "model_name": "base"}',
        created_at=now,
        updated_at=now,
    )
    return upsert_language_analysis_result(conn, record)


def create_segments_for_analysis(
    conn: sqlite3.Connection, analysis_id: int, num_segments: int = 2
) -> list[int]:
    """Create language segments for an analysis and return their IDs."""
    segments = []
    for i in range(num_segments):
        segments.append(
            LanguageSegmentRecord(
                id=None,
                analysis_id=analysis_id,
                language_code="eng" if i % 2 == 0 else "spa",
                start_time=float(i * 30),
                end_time=float((i + 1) * 30),
                confidence=0.95 - (i * 0.05),
            )
        )
    return upsert_language_segments(conn, analysis_id, segments)


class TestGetLanguageAnalysisForTracks:
    """Tests for get_language_analysis_for_tracks batch lookup function."""

    def test_empty_list_returns_empty_dict(self, db_conn):
        """Empty track_ids list returns empty dict without query."""
        result = get_language_analysis_for_tracks(db_conn, [])
        assert result == {}

    def test_single_track_found(self, db_conn, insert_test_file, insert_test_track):
        """Single track_id lookup returns matching record."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        create_language_analysis(db_conn, track_id, "eng", 0.85)

        result = get_language_analysis_for_tracks(db_conn, [track_id])

        assert len(result) == 1
        assert track_id in result
        assert result[track_id].track_id == track_id
        assert result[track_id].primary_language == "eng"
        assert result[track_id].primary_percentage == 0.85

    def test_multiple_tracks_found(self, db_conn, insert_test_file, insert_test_track):
        """Multiple track_ids return all matching records."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_ids = []
        for i in range(3):
            track_id = insert_test_track(
                file_id=file_id,
                track_index=i + 1,
                track_type="audio",
                codec="aac",
                language="eng",
            )
            db_conn.commit()
            create_language_analysis(db_conn, track_id, "eng", 0.90 - i * 0.05)
            track_ids.append(track_id)

        result = get_language_analysis_for_tracks(db_conn, track_ids)

        assert len(result) == 3
        for track_id in track_ids:
            assert track_id in result
            assert result[track_id].track_id == track_id

    def test_partial_results(self, db_conn, insert_test_file, insert_test_track):
        """Returns only tracks with analysis results."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track1 = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        track2 = insert_test_track(
            file_id=file_id,
            track_index=2,
            track_type="audio",
            codec="aac",
            language="spa",
        )
        track3 = insert_test_track(
            file_id=file_id,
            track_index=3,
            track_type="audio",
            codec="aac",
            language="fre",
        )
        db_conn.commit()

        # Only create analysis for track1 and track3
        create_language_analysis(db_conn, track1, "eng", 0.95)
        create_language_analysis(db_conn, track3, "fre", 0.88)

        result = get_language_analysis_for_tracks(db_conn, [track1, track2, track3])

        assert len(result) == 2
        assert track1 in result
        assert track2 not in result
        assert track3 in result

    def test_no_matching_tracks_returns_empty(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returns empty dict when no tracks have analysis results."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        # No analysis created

        result = get_language_analysis_for_tracks(db_conn, [track_id])

        assert result == {}

    def test_nonexistent_track_ids_ignored(self, db_conn):
        """Nonexistent track IDs are silently ignored."""
        result = get_language_analysis_for_tracks(db_conn, [9999, 8888, 7777])
        assert result == {}

    def test_returns_correct_record_fields(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returned record has all expected fields."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        create_language_analysis(db_conn, track_id, "eng", 0.85, "MULTI_LANGUAGE")

        result = get_language_analysis_for_tracks(db_conn, [track_id])
        record = result[track_id]

        assert record.id is not None
        assert record.track_id == track_id
        assert record.file_hash == "hash123"
        assert record.primary_language == "eng"
        assert record.primary_percentage == 0.85
        assert record.classification == "MULTI_LANGUAGE"
        assert record.analysis_metadata is not None
        assert record.created_at is not None
        assert record.updated_at is not None

    def test_chunking_with_custom_chunk_size(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Verify chunking works with custom chunk size."""
        # Create 6 tracks with analysis
        file_id = insert_test_file(path="/media/test.mkv", container_format="matroska")
        db_conn.commit()
        track_ids = []
        for i in range(6):
            track_id = insert_test_track(
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="eng",
            )
            db_conn.commit()
            create_language_analysis(db_conn, track_id, "eng", 0.9)
            track_ids.append(track_id)

        # Use chunk_size=2 to force 3 separate queries
        result = get_language_analysis_for_tracks(db_conn, track_ids, chunk_size=2)

        assert len(result) == 6
        for tid in track_ids:
            assert tid in result

    def test_chunking_with_large_chunk_returns_all(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Verify chunking with chunk larger than list still works."""
        file_id = insert_test_file(path="/media/test.mkv", container_format="matroska")
        db_conn.commit()
        track_ids = []
        for i in range(3):
            track_id = insert_test_track(
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="eng",
            )
            db_conn.commit()
            create_language_analysis(db_conn, track_id, "eng", 0.9)
            track_ids.append(track_id)

        # Chunk size larger than list
        result = get_language_analysis_for_tracks(db_conn, track_ids, chunk_size=100)

        assert len(result) == 3


class TestGetLanguageSegmentsForAnalyses:
    """Tests for get_language_segments_for_analyses batch lookup function."""

    def test_empty_ids_returns_empty_dict(self, db_conn):
        """Empty analysis_ids list returns empty dict without query."""
        result = get_language_segments_for_analyses(db_conn, [])
        assert result == {}

    def test_single_analysis_with_segments(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Single analysis_id returns dict with segments."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        analysis_id = create_language_analysis(db_conn, track_id, "eng", 0.85)
        create_segments_for_analysis(db_conn, analysis_id, num_segments=3)

        result = get_language_segments_for_analyses(db_conn, [analysis_id])

        assert len(result) == 1
        assert analysis_id in result
        assert len(result[analysis_id]) == 3
        # Verify ordering by start_time
        segments = result[analysis_id]
        assert segments[0].start_time < segments[1].start_time < segments[2].start_time

    def test_multiple_analyses_batched(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Multiple analysis IDs return all segments grouped correctly."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        analysis_ids = []
        for i in range(3):
            track_id = insert_test_track(
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="eng",
            )
            db_conn.commit()
            analysis_id = create_language_analysis(db_conn, track_id, "eng", 0.85)
            create_segments_for_analysis(db_conn, analysis_id, num_segments=i + 1)
            analysis_ids.append(analysis_id)

        result = get_language_segments_for_analyses(db_conn, analysis_ids)

        assert len(result) == 3
        # Each analysis has different segment counts
        assert len(result[analysis_ids[0]]) == 1
        assert len(result[analysis_ids[1]]) == 2
        assert len(result[analysis_ids[2]]) == 3

    def test_analysis_without_segments_returns_empty_list(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Analysis without segments returns empty list, not missing key."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        analysis_id = create_language_analysis(db_conn, track_id, "eng", 0.85)
        # No segments created

        result = get_language_segments_for_analyses(db_conn, [analysis_id])

        assert analysis_id in result
        assert result[analysis_id] == []

    def test_nonexistent_analysis_ids_return_empty_lists(self, db_conn):
        """Nonexistent analysis IDs return empty lists."""
        result = get_language_segments_for_analyses(db_conn, [9999, 8888])

        assert 9999 in result
        assert 8888 in result
        assert result[9999] == []
        assert result[8888] == []

    def test_chunking_with_many_analyses(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Verify chunking works with custom chunk size."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        analysis_ids = []
        for i in range(6):
            track_id = insert_test_track(
                file_id=file_id,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="eng",
            )
            db_conn.commit()
            analysis_id = create_language_analysis(db_conn, track_id, "eng", 0.85)
            create_segments_for_analysis(db_conn, analysis_id, num_segments=2)
            analysis_ids.append(analysis_id)

        # Use chunk_size=2 to force 3 separate queries
        result = get_language_segments_for_analyses(db_conn, analysis_ids, chunk_size=2)

        assert len(result) == 6
        for aid in analysis_ids:
            assert aid in result
            assert len(result[aid]) == 2

    def test_returns_correct_segment_fields(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Returned segments have all expected fields."""
        file_id = insert_test_file(
            path="/media/movies/test.mkv", container_format="matroska"
        )
        db_conn.commit()
        track_id = insert_test_track(
            file_id=file_id,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        )
        db_conn.commit()
        analysis_id = create_language_analysis(db_conn, track_id, "eng", 0.85)
        create_segments_for_analysis(db_conn, analysis_id, num_segments=1)

        result = get_language_segments_for_analyses(db_conn, [analysis_id])
        segment = result[analysis_id][0]

        assert segment.id is not None
        assert segment.analysis_id == analysis_id
        assert segment.language_code == "eng"
        assert segment.start_time == 0.0
        assert segment.end_time == 30.0
        assert segment.confidence == 0.95
