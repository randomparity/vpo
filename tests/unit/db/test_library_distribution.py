"""Tests for library distribution query functions."""

import sqlite3

import pytest

from vpo.db.schema import create_schema
from vpo.db.views.library import get_library_distribution


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


def _insert_file(conn, *, path, container_format="mkv", scan_status="ok"):
    """Insert a minimal file record and return its id."""
    conn.execute(
        """
        INSERT INTO files (path, filename, directory, extension,
                           size_bytes, modified_at, container_format,
                           scanned_at, scan_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            path,
            path.split("/")[-1],
            "/".join(path.split("/")[:-1]) or "/",
            path.rsplit(".", 1)[-1] if "." in path else "",
            1000,
            "2025-01-15T10:00:00Z",
            container_format,
            "2025-01-15T10:00:00Z",
            scan_status,
        ),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_track(conn, file_id, *, track_index, track_type, codec):
    """Insert a minimal track record."""
    conn.execute(
        """
        INSERT INTO tracks (file_id, track_index, track_type, codec)
        VALUES (?, ?, ?, ?)
        """,
        (file_id, track_index, track_type, codec),
    )


class TestGetLibraryDistribution:
    """Tests for get_library_distribution."""

    def test_empty_library(self, db_conn):
        result = get_library_distribution(db_conn)
        assert result.containers == []
        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_single_file(self, db_conn):
        fid = _insert_file(db_conn, path="/video/a.mkv", container_format="mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="video", codec="hevc")
        _insert_track(db_conn, fid, track_index=1, track_type="audio", codec="aac")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 1

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 1

        assert len(result.audio_codecs) == 1
        assert result.audio_codecs[0].label == "aac"
        assert result.audio_codecs[0].count == 1

    def test_multiple_containers_ordered_by_count_desc(self, db_conn):
        for i in range(3):
            _insert_file(db_conn, path=f"/v/a{i}.mkv", container_format="mkv")
        _insert_file(db_conn, path="/v/b.mp4", container_format="mp4")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 2
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 3
        assert result.containers[1].label == "mp4"
        assert result.containers[1].count == 1

    def test_excludes_non_ok_status_files(self, db_conn):
        fid_ok = _insert_file(
            db_conn, path="/v/ok.mkv", container_format="mkv", scan_status="ok"
        )
        _insert_track(db_conn, fid_ok, track_index=0, track_type="video", codec="hevc")
        _insert_track(db_conn, fid_ok, track_index=1, track_type="audio", codec="aac")

        fid_err = _insert_file(
            db_conn, path="/v/err.mkv", container_format="mkv", scan_status="error"
        )
        _insert_track(db_conn, fid_err, track_index=0, track_type="video", codec="h264")

        fid_miss = _insert_file(
            db_conn, path="/v/miss.avi", container_format="avi", scan_status="missing"
        )
        _insert_track(db_conn, fid_miss, track_index=0, track_type="audio", codec="mp3")

        fid_pend = _insert_file(
            db_conn, path="/v/pend.mkv", container_format="mkv", scan_status="pending"
        )
        _insert_track(
            db_conn, fid_pend, track_index=0, track_type="video", codec="hevc"
        )

        result = get_library_distribution(db_conn)

        # Only the ok file counts
        assert len(result.containers) == 1
        assert result.containers[0].count == 1

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 1

        assert len(result.audio_codecs) == 1
        assert result.audio_codecs[0].label == "aac"
        assert result.audio_codecs[0].count == 1

    def test_video_codec_counts_distinct_files(self, db_conn):
        """A file with 2 hevc video tracks should count as 1 for hevc."""
        fid = _insert_file(db_conn, path="/v/multi.mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="video", codec="hevc")
        _insert_track(db_conn, fid, track_index=1, track_type="video", codec="hevc")

        result = get_library_distribution(db_conn)

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 1

    def test_audio_codec_counts_tracks_not_files(self, db_conn):
        """A file with aac + dts should produce 2 total audio codec entries."""
        fid = _insert_file(db_conn, path="/v/multi.mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="audio", codec="aac")
        _insert_track(db_conn, fid, track_index=1, track_type="audio", codec="dts")

        result = get_library_distribution(db_conn)

        assert len(result.audio_codecs) == 2
        labels = {item.label for item in result.audio_codecs}
        assert labels == {"aac", "dts"}
        # Each has count 1
        for item in result.audio_codecs:
            assert item.count == 1

    def test_case_insensitive_grouping(self, db_conn):
        """MKV and mkv should merge into one group."""
        _insert_file(db_conn, path="/v/upper.mkv", container_format="MKV")
        _insert_file(db_conn, path="/v/lower.mkv", container_format="mkv")
        _insert_file(db_conn, path="/v/mixed.mkv", container_format="Mkv")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 3

    def test_case_insensitive_codec_grouping(self, db_conn):
        """HEVC and hevc video codecs should merge."""
        fid1 = _insert_file(db_conn, path="/v/a.mkv")
        _insert_track(db_conn, fid1, track_index=0, track_type="video", codec="HEVC")

        fid2 = _insert_file(db_conn, path="/v/b.mkv")
        _insert_track(db_conn, fid2, track_index=0, track_type="video", codec="hevc")

        result = get_library_distribution(db_conn)

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 2

    def test_null_container_format_excluded(self, db_conn):
        """Files with NULL container_format should not appear in containers."""
        conn = db_conn
        conn.execute(
            """
            INSERT INTO files (path, filename, directory, extension,
                               size_bytes, modified_at, container_format,
                               scanned_at, scan_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "/v/null.mkv",
                "null.mkv",
                "/v",
                "mkv",
                1000,
                "2025-01-15T10:00:00Z",
                None,
                "2025-01-15T10:00:00Z",
                "ok",
            ),
        )
        _insert_file(conn, path="/v/good.mkv", container_format="mkv")

        result = get_library_distribution(conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 1

    def test_empty_string_container_format_excluded(self, db_conn):
        """Files with empty string container_format should not appear."""
        _insert_file(db_conn, path="/v/empty.mkv", container_format="")
        _insert_file(db_conn, path="/v/good.mkv", container_format="mkv")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 1

    def test_null_codec_excluded(self, db_conn):
        """Tracks with NULL codec should not appear in codec lists."""
        fid = _insert_file(db_conn, path="/v/null.mkv")
        db_conn.execute(
            """
            INSERT INTO tracks (file_id, track_index, track_type, codec)
            VALUES (?, ?, ?, ?)
            """,
            (fid, 0, "video", None),
        )
        db_conn.execute(
            """
            INSERT INTO tracks (file_id, track_index, track_type, codec)
            VALUES (?, ?, ?, ?)
            """,
            (fid, 1, "audio", None),
        )

        result = get_library_distribution(db_conn)

        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_empty_string_codec_excluded(self, db_conn):
        """Tracks with empty string codec should not appear."""
        fid = _insert_file(db_conn, path="/v/empty.mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="video", codec="")
        _insert_track(db_conn, fid, track_index=1, track_type="audio", codec="")

        result = get_library_distribution(db_conn)

        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_subtitle_only_file(self, db_conn):
        """A file with only subtitle tracks produces no video/audio codecs."""
        fid = _insert_file(db_conn, path="/v/subs.mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="subtitle", codec="srt")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_same_audio_codec_multiple_tracks(self, db_conn):
        """Multiple aac tracks on one file should count each track."""
        fid = _insert_file(db_conn, path="/v/multi_aac.mkv")
        _insert_track(db_conn, fid, track_index=0, track_type="audio", codec="aac")
        _insert_track(db_conn, fid, track_index=1, track_type="audio", codec="aac")

        result = get_library_distribution(db_conn)

        assert len(result.audio_codecs) == 1
        assert result.audio_codecs[0].label == "aac"
        assert result.audio_codecs[0].count == 2

    def test_results_ordered_by_count_descending(self, db_conn):
        """All three distributions should be ordered by count DESC."""
        # 2 mkv, 1 mp4, 3 avi
        for i in range(2):
            _insert_file(db_conn, path=f"/v/mkv{i}.mkv", container_format="mkv")
        _insert_file(db_conn, path="/v/mp4.mp4", container_format="mp4")
        for i in range(3):
            _insert_file(db_conn, path=f"/v/avi{i}.avi", container_format="avi")

        result = get_library_distribution(db_conn)

        counts = [item.count for item in result.containers]
        assert counts == sorted(counts, reverse=True)
        assert result.containers[0].label == "avi"
        assert result.containers[1].label == "mkv"
        assert result.containers[2].label == "mp4"
