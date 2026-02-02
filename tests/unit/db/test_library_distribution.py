"""Tests for library distribution query functions."""

from vpo.db.views.library import get_library_distribution


class TestGetLibraryDistribution:
    """Tests for get_library_distribution."""

    def test_empty_library(self, db_conn):
        result = get_library_distribution(db_conn)
        assert result.containers == []
        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_single_file(self, db_conn, insert_test_file, insert_test_track):
        fid = insert_test_file(path="/video/a.mkv", container_format="mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="video", codec="hevc")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="aac")

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

    def test_multiple_containers_ordered_by_count_desc(self, db_conn, insert_test_file):
        for i in range(3):
            insert_test_file(path=f"/v/a{i}.mkv", container_format="mkv")
        insert_test_file(path="/v/b.mp4", container_format="mp4")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 2
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 3
        assert result.containers[1].label == "mp4"
        assert result.containers[1].count == 1

    def test_excludes_non_ok_status_files(
        self, db_conn, insert_test_file, insert_test_track
    ):
        fid_ok = insert_test_file(
            path="/v/ok.mkv", container_format="mkv", scan_status="ok"
        )
        insert_test_track(
            file_id=fid_ok, track_index=0, track_type="video", codec="hevc"
        )
        insert_test_track(
            file_id=fid_ok, track_index=1, track_type="audio", codec="aac"
        )

        fid_err = insert_test_file(
            path="/v/err.mkv", container_format="mkv", scan_status="error"
        )
        insert_test_track(
            file_id=fid_err, track_index=0, track_type="video", codec="h264"
        )

        fid_miss = insert_test_file(
            path="/v/miss.avi", container_format="avi", scan_status="missing"
        )
        insert_test_track(
            file_id=fid_miss, track_index=0, track_type="audio", codec="mp3"
        )

        fid_pend = insert_test_file(
            path="/v/pend.mkv", container_format="mkv", scan_status="pending"
        )
        insert_test_track(
            file_id=fid_pend, track_index=0, track_type="video", codec="hevc"
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

    def test_video_codec_counts_distinct_files(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """A file with 2 hevc video tracks should count as 1 for hevc."""
        fid = insert_test_file(path="/v/multi.mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="video", codec="hevc")
        insert_test_track(file_id=fid, track_index=1, track_type="video", codec="hevc")

        result = get_library_distribution(db_conn)

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 1

    def test_audio_codec_counts_tracks_not_files(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """A file with aac + dts should produce 2 total audio codec entries."""
        fid = insert_test_file(path="/v/multi.mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="audio", codec="aac")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="dts")

        result = get_library_distribution(db_conn)

        assert len(result.audio_codecs) == 2
        labels = {item.label for item in result.audio_codecs}
        assert labels == {"aac", "dts"}
        # Each has count 1
        for item in result.audio_codecs:
            assert item.count == 1

    def test_case_insensitive_grouping(self, db_conn, insert_test_file):
        """MKV and mkv should merge into one group."""
        insert_test_file(path="/v/upper.mkv", container_format="MKV")
        insert_test_file(path="/v/lower.mkv", container_format="mkv")
        insert_test_file(path="/v/mixed.mkv", container_format="Mkv")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 3

    def test_case_insensitive_codec_grouping(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """HEVC and hevc video codecs should merge."""
        fid1 = insert_test_file(path="/v/a.mkv")
        insert_test_track(file_id=fid1, track_index=0, track_type="video", codec="HEVC")

        fid2 = insert_test_file(path="/v/b.mkv")
        insert_test_track(file_id=fid2, track_index=0, track_type="video", codec="hevc")

        result = get_library_distribution(db_conn)

        assert len(result.video_codecs) == 1
        assert result.video_codecs[0].label == "hevc"
        assert result.video_codecs[0].count == 2

    def test_null_container_format_excluded(self, db_conn, insert_test_file):
        """Files with NULL container_format should not appear in containers."""
        # Raw SQL needed: insert_test_file defaults container_format to "mkv"
        db_conn.execute(
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
        insert_test_file(path="/v/good.mkv", container_format="mkv")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 1

    def test_empty_string_container_format_excluded(self, db_conn, insert_test_file):
        """Files with empty string container_format should not appear."""
        insert_test_file(path="/v/empty.mkv", container_format="")
        insert_test_file(path="/v/good.mkv", container_format="mkv")

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.containers[0].label == "mkv"
        assert result.containers[0].count == 1

    def test_null_codec_excluded(self, db_conn, insert_test_file):
        """Tracks with NULL codec should not appear in codec lists."""
        fid = insert_test_file(path="/v/null.mkv")
        # Raw SQL needed: insert_test_track defaults codec to "h264"
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

    def test_empty_string_codec_excluded(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Tracks with empty string codec should not appear."""
        fid = insert_test_file(path="/v/empty.mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="video", codec="")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="")

        result = get_library_distribution(db_conn)

        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_subtitle_only_file(self, db_conn, insert_test_file, insert_test_track):
        """A file with only subtitle tracks produces no video/audio codecs."""
        fid = insert_test_file(path="/v/subs.mkv")
        insert_test_track(
            file_id=fid, track_index=0, track_type="subtitle", codec="srt"
        )

        result = get_library_distribution(db_conn)

        assert len(result.containers) == 1
        assert result.video_codecs == []
        assert result.audio_codecs == []

    def test_same_audio_codec_multiple_tracks(
        self, db_conn, insert_test_file, insert_test_track
    ):
        """Multiple aac tracks on one file should count each track."""
        fid = insert_test_file(path="/v/multi_aac.mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="audio", codec="aac")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="aac")

        result = get_library_distribution(db_conn)

        assert len(result.audio_codecs) == 1
        assert result.audio_codecs[0].label == "aac"
        assert result.audio_codecs[0].count == 2

    def test_results_ordered_by_count_descending(self, db_conn, insert_test_file):
        """All three distributions should be ordered by count DESC."""
        # 2 mkv, 1 mp4, 3 avi
        for i in range(2):
            insert_test_file(path=f"/v/mkv{i}.mkv", container_format="mkv")
        insert_test_file(path="/v/mp4.mp4", container_format="mp4")
        for i in range(3):
            insert_test_file(path=f"/v/avi{i}.avi", container_format="avi")

        result = get_library_distribution(db_conn)

        counts = [item.count for item in result.containers]
        assert counts == sorted(counts, reverse=True)
        assert result.containers[0].label == "avi"
        assert result.containers[1].label == "mkv"
        assert result.containers[2].label == "mp4"
