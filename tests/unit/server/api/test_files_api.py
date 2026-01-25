"""Unit tests for server/api/files.py.

Tests the library/files API handlers and models:
- LibraryFilterParams query parameter parsing
- FileListItem/FileListResponse serialization
- LibraryContext filter options
- TrackTranscriptionInfo model
"""

from __future__ import annotations

from vpo.server.ui.models import (
    VALID_RESOLUTIONS,
    FileListItem,
    FileListResponse,
    LibraryContext,
    LibraryFilterParams,
    TrackTranscriptionInfo,
)

# =============================================================================
# Tests for LibraryFilterParams
# =============================================================================


class TestLibraryFilterParams:
    """Tests for LibraryFilterParams.from_query() method."""

    def test_parses_default_values(self):
        """Returns default values for empty query."""
        params = LibraryFilterParams.from_query({})

        assert params.status is None
        assert params.limit == 50
        assert params.offset == 0
        assert params.search is None
        assert params.resolution is None
        assert params.audio_lang is None
        assert params.subtitles is None

    def test_parses_status_ok(self):
        """Parses 'ok' status filter."""
        params = LibraryFilterParams.from_query({"status": "ok"})

        assert params.status == "ok"

    def test_parses_status_error(self):
        """Parses 'error' status filter."""
        params = LibraryFilterParams.from_query({"status": "error"})

        assert params.status == "error"

    def test_ignores_invalid_status(self):
        """Ignores invalid status values."""
        params = LibraryFilterParams.from_query({"status": "invalid"})

        assert params.status is None

    def test_ignores_empty_status(self):
        """Treats empty status as None."""
        params = LibraryFilterParams.from_query({"status": ""})

        assert params.status is None

    def test_parses_limit_within_bounds(self):
        """Parses limit value within bounds (1-100)."""
        params = LibraryFilterParams.from_query({"limit": "25"})

        assert params.limit == 25

    def test_clamps_limit_minimum(self):
        """Clamps limit to minimum of 1."""
        params = LibraryFilterParams.from_query({"limit": "0"})

        assert params.limit == 1

    def test_clamps_limit_maximum(self):
        """Clamps limit to maximum of 100."""
        params = LibraryFilterParams.from_query({"limit": "500"})

        assert params.limit == 100

    def test_handles_invalid_limit(self):
        """Returns default limit for invalid values."""
        params = LibraryFilterParams.from_query({"limit": "invalid"})

        assert params.limit == 50

    def test_parses_offset(self):
        """Parses offset value."""
        params = LibraryFilterParams.from_query({"offset": "100"})

        assert params.offset == 100

    def test_clamps_negative_offset(self):
        """Clamps negative offset to 0."""
        params = LibraryFilterParams.from_query({"offset": "-10"})

        assert params.offset == 0

    def test_handles_invalid_offset(self):
        """Returns default offset for invalid values."""
        params = LibraryFilterParams.from_query({"offset": "abc"})

        assert params.offset == 0

    def test_parses_search_query(self):
        """Parses search text."""
        params = LibraryFilterParams.from_query({"search": "movie"})

        assert params.search == "movie"

    def test_trims_search_whitespace(self):
        """Trims whitespace from search text."""
        params = LibraryFilterParams.from_query({"search": "  movie  "})

        assert params.search == "movie"

    def test_search_empty_after_trim_is_none(self):
        """Empty search after trim becomes None."""
        params = LibraryFilterParams.from_query({"search": "   "})

        assert params.search is None

    def test_search_truncated_to_200_chars(self):
        """Search text is truncated to 200 characters."""
        long_search = "a" * 300
        params = LibraryFilterParams.from_query({"search": long_search})

        assert len(params.search) == 200

    def test_parses_valid_resolution(self):
        """Parses valid resolution filter values."""
        for resolution in VALID_RESOLUTIONS:
            params = LibraryFilterParams.from_query({"resolution": resolution})
            assert params.resolution == resolution

    def test_ignores_invalid_resolution(self):
        """Ignores invalid resolution values."""
        params = LibraryFilterParams.from_query({"resolution": "2160p"})

        assert params.resolution is None

    def test_ignores_empty_resolution(self):
        """Treats empty resolution as None."""
        params = LibraryFilterParams.from_query({"resolution": ""})

        assert params.resolution is None

    def test_parses_single_audio_lang(self):
        """Parses single audio language code."""
        params = LibraryFilterParams.from_query({"audio_lang": "eng"})

        assert params.audio_lang == ["eng"]

    def test_parses_audio_lang_list(self):
        """Parses list of audio language codes."""
        params = LibraryFilterParams.from_query({"audio_lang": ["eng", "jpn"]})

        assert params.audio_lang == ["eng", "jpn"]

    def test_audio_lang_normalized_to_lowercase(self):
        """Audio language codes are normalized to lowercase."""
        params = LibraryFilterParams.from_query({"audio_lang": "ENG"})

        assert params.audio_lang == ["eng"]

    def test_audio_lang_filters_invalid_lengths(self):
        """Only accepts 2-3 character language codes."""
        params = LibraryFilterParams.from_query({"audio_lang": ["en", "english"]})

        # "en" (2 chars) accepted, "english" (7 chars) rejected
        assert params.audio_lang == ["en"]

    def test_audio_lang_empty_list_becomes_none(self):
        """Empty audio_lang list becomes None."""
        params = LibraryFilterParams.from_query({"audio_lang": []})

        assert params.audio_lang is None

    def test_parses_subtitles_yes(self):
        """Parses 'yes' subtitles filter."""
        params = LibraryFilterParams.from_query({"subtitles": "yes"})

        assert params.subtitles == "yes"

    def test_parses_subtitles_no(self):
        """Parses 'no' subtitles filter."""
        params = LibraryFilterParams.from_query({"subtitles": "no"})

        assert params.subtitles == "no"

    def test_ignores_invalid_subtitles(self):
        """Ignores invalid subtitles values."""
        params = LibraryFilterParams.from_query({"subtitles": "maybe"})

        assert params.subtitles is None

    def test_ignores_empty_subtitles(self):
        """Treats empty subtitles as None."""
        params = LibraryFilterParams.from_query({"subtitles": ""})

        assert params.subtitles is None

    def test_parses_all_parameters(self):
        """Parses all parameters together."""
        params = LibraryFilterParams.from_query(
            {
                "status": "ok",
                "limit": "20",
                "offset": "40",
                "search": "movie",
                "resolution": "1080p",
                "audio_lang": ["eng", "jpn"],
                "subtitles": "yes",
            }
        )

        assert params.status == "ok"
        assert params.limit == 20
        assert params.offset == 40
        assert params.search == "movie"
        assert params.resolution == "1080p"
        assert params.audio_lang == ["eng", "jpn"]
        assert params.subtitles == "yes"


# =============================================================================
# Tests for FileListItem
# =============================================================================


class TestFileListItem:
    """Tests for FileListItem.to_dict() method."""

    def test_to_dict_basic(self):
        """Serializes basic file list item."""
        item = FileListItem(
            id=123,
            filename="movie.mkv",
            path="/videos/movie.mkv",
            title="My Movie",
            resolution="1080p",
            audio_languages="eng, jpn",
            scanned_at="2024-01-15T10:00:00Z",
            scan_status="ok",
        )

        result = item.to_dict()

        assert result["id"] == 123
        assert result["filename"] == "movie.mkv"
        assert result["path"] == "/videos/movie.mkv"
        assert result["title"] == "My Movie"
        assert result["resolution"] == "1080p"
        assert result["audio_languages"] == "eng, jpn"
        assert result["scanned_at"] == "2024-01-15T10:00:00Z"
        assert result["scan_status"] == "ok"
        assert result["scan_error"] is None

    def test_to_dict_with_error(self):
        """Serializes file item with scan error."""
        item = FileListItem(
            id=456,
            filename="corrupt.mkv",
            path="/videos/corrupt.mkv",
            title=None,
            resolution="Unknown",
            audio_languages="",
            scanned_at="2024-01-15T10:00:00Z",
            scan_status="error",
            scan_error="ffprobe failed: Invalid data",
        )

        result = item.to_dict()

        assert result["scan_status"] == "error"
        assert result["scan_error"] == "ffprobe failed: Invalid data"
        assert result["title"] is None


# =============================================================================
# Tests for FileListResponse
# =============================================================================


class TestFileListResponse:
    """Tests for FileListResponse.to_dict() method."""

    def test_to_dict_empty_list(self):
        """Serializes response with no files."""
        response = FileListResponse(
            files=[],
            total=0,
            limit=50,
            offset=0,
            has_filters=False,
        )

        result = response.to_dict()

        assert result["files"] == []
        assert result["total"] == 0
        assert result["limit"] == 50
        assert result["offset"] == 0
        assert result["has_filters"] is False

    def test_to_dict_with_files(self):
        """Serializes response with file list."""
        file1 = FileListItem(
            id=1,
            filename="movie1.mkv",
            path="/videos/movie1.mkv",
            title="Movie 1",
            resolution="1080p",
            audio_languages="eng",
            scanned_at="2024-01-15T10:00:00Z",
            scan_status="ok",
        )
        file2 = FileListItem(
            id=2,
            filename="movie2.mkv",
            path="/videos/movie2.mkv",
            title="Movie 2",
            resolution="4K",
            audio_languages="eng, jpn",
            scanned_at="2024-01-15T11:00:00Z",
            scan_status="ok",
        )
        response = FileListResponse(
            files=[file1, file2],
            total=100,
            limit=50,
            offset=0,
            has_filters=True,
        )

        result = response.to_dict()

        assert len(result["files"]) == 2
        assert result["files"][0]["filename"] == "movie1.mkv"
        assert result["files"][1]["filename"] == "movie2.mkv"
        assert result["total"] == 100
        assert result["has_filters"] is True


# =============================================================================
# Tests for LibraryContext
# =============================================================================


class TestLibraryContext:
    """Tests for LibraryContext.default() method."""

    def test_default_has_status_options(self):
        """Default context includes status filter options."""
        context = LibraryContext.default()

        assert len(context.status_options) > 0
        status_values = [opt["value"] for opt in context.status_options]
        assert "" in status_values  # All files
        assert "ok" in status_values
        assert "error" in status_values

    def test_default_has_resolution_options(self):
        """Default context includes resolution filter options."""
        context = LibraryContext.default()

        assert len(context.resolution_options) > 0
        res_values = [opt["value"] for opt in context.resolution_options]
        assert "" in res_values  # All resolutions
        assert "4k" in res_values
        assert "1080p" in res_values
        assert "720p" in res_values
        assert "480p" in res_values
        assert "other" in res_values

    def test_default_has_subtitles_options(self):
        """Default context includes subtitles filter options."""
        context = LibraryContext.default()

        assert len(context.subtitles_options) > 0
        sub_values = [opt["value"] for opt in context.subtitles_options]
        assert "" in sub_values  # All files
        assert "yes" in sub_values
        assert "no" in sub_values


# =============================================================================
# Tests for TrackTranscriptionInfo
# =============================================================================


class TestTrackTranscriptionInfo:
    """Tests for TrackTranscriptionInfo model."""

    def test_confidence_percent_high(self):
        """Converts high confidence score to percentage."""
        info = TrackTranscriptionInfo(
            id=1,
            detected_language="eng",
            confidence_score=0.95,
            track_type="main",
            plugin_name="whisper",
        )

        assert info.confidence_percent == 95

    def test_confidence_percent_low(self):
        """Converts low confidence score to percentage."""
        info = TrackTranscriptionInfo(
            id=2,
            detected_language="jpn",
            confidence_score=0.45,
            track_type="commentary",
            plugin_name="whisper",
        )

        assert info.confidence_percent == 45

    def test_confidence_percent_rounds_down(self):
        """Confidence percentage rounds down (int truncation)."""
        info = TrackTranscriptionInfo(
            id=3,
            detected_language="eng",
            confidence_score=0.859,
            track_type="main",
            plugin_name="whisper",
        )

        assert info.confidence_percent == 85

    def test_to_dict(self):
        """Serializes transcription info to dict."""
        info = TrackTranscriptionInfo(
            id=10,
            detected_language="fra",
            confidence_score=0.88,
            track_type="alternate",
            plugin_name="custom_detector",
        )

        result = info.to_dict()

        assert result["id"] == 10
        assert result["detected_language"] == "fra"
        assert result["confidence_score"] == 0.88
        assert result["track_type"] == "alternate"
        assert result["plugin_name"] == "custom_detector"

    def test_to_dict_with_none_language(self):
        """Serializes transcription info with unknown language."""
        info = TrackTranscriptionInfo(
            id=11,
            detected_language=None,
            confidence_score=0.0,
            track_type="unknown",
            plugin_name="whisper",
        )

        result = info.to_dict()

        assert result["detected_language"] is None


# =============================================================================
# Tests for VALID_RESOLUTIONS constant
# =============================================================================


class TestValidResolutions:
    """Tests for VALID_RESOLUTIONS constant."""

    def test_contains_expected_values(self):
        """VALID_RESOLUTIONS includes expected resolution values."""
        expected = ("4k", "1080p", "720p", "480p", "other")

        assert VALID_RESOLUTIONS == expected
