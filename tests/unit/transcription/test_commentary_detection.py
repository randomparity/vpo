"""Unit tests for commentary detection functionality."""

import pytest

from vpo.transcription.models import (
    COMMENTARY_KEYWORDS,
    COMMENTARY_TRANSCRIPT_PATTERNS,
    TrackClassification,
    detect_commentary_type,
    is_commentary_by_metadata,
)

# =============================================================================
# Metadata-based Commentary Detection Tests
# =============================================================================


class TestIsCommentaryByMetadata:
    """Tests for is_commentary_by_metadata function."""

    @pytest.mark.parametrize(
        "title",
        [
            "Director's Commentary",
            "Cast Commentary",
            "Commentary Track",
            "Behind the Scenes Audio",
            "Making of Feature",
            "Composer Notes",
        ],
    )
    def test_detects_commentary_keywords(self, title):
        """Should detect tracks with commentary keywords in title."""
        assert is_commentary_by_metadata(title) is True

    def test_isolated_score_is_not_commentary(self):
        """Isolated Score should be music, not commentary."""
        # "Isolated Score" contains "score" which is a music keyword, not commentary
        assert is_commentary_by_metadata("Isolated Score") is False

    def test_alternate_mix_is_not_commentary(self):
        """Alternate Mix is just an alternate track, not commentary."""
        # "Alternate Mix" doesn't contain any commentary keywords
        assert is_commentary_by_metadata("Alternate Mix") is False

    @pytest.mark.parametrize(
        "title",
        [
            "English",
            "5.1 Surround",
            "DTS-HD MA",
            "Original Audio",
            "Stereo",
        ],
    )
    def test_non_commentary_titles(self, title):
        """Should not flag regular track titles as commentary."""
        assert is_commentary_by_metadata(title) is False

    def test_none_title(self):
        """Should return False for None title."""
        assert is_commentary_by_metadata(None) is False

    def test_empty_title(self):
        """Should return False for empty title."""
        assert is_commentary_by_metadata("") is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert is_commentary_by_metadata("DIRECTOR'S COMMENTARY") is True
        assert is_commentary_by_metadata("director's commentary") is True
        assert is_commentary_by_metadata("DiReCtOr'S cOmMeNtArY") is True


# =============================================================================
# Transcript-based Commentary Detection Tests
# =============================================================================


class TestDetectCommentaryType:
    """Tests for detect_commentary_type function."""

    def test_metadata_based_detection(self):
        """Should detect commentary from metadata regardless of transcript."""
        result = detect_commentary_type(
            title="Director's Commentary",
            transcript_sample=None,
        )
        assert result == TrackClassification.COMMENTARY

    def test_transcript_based_detection(self):
        """Should detect commentary from transcript patterns."""
        transcript = (
            "This scene was really challenging. When we shot this, "
            "I remember the actor had to do multiple takes."
        )
        result = detect_commentary_type(
            title=None,
            transcript_sample=transcript,
        )
        assert result == TrackClassification.COMMENTARY

    def test_single_pattern_not_enough(self):
        """Single transcript pattern match shouldn't trigger commentary detection."""
        # Only one pattern: "I remember"
        transcript = "I remember this movie."
        result = detect_commentary_type(
            title=None,
            transcript_sample=transcript,
        )
        assert result == TrackClassification.MAIN

    def test_no_transcript_returns_main(self):
        """Should return MAIN for tracks without transcript sample."""
        result = detect_commentary_type(
            title=None,
            transcript_sample=None,
        )
        assert result == TrackClassification.MAIN

    def test_no_metadata_no_patterns_returns_main(self):
        """Should return MAIN when no commentary indicators present."""
        result = detect_commentary_type(
            title="English",
            transcript_sample="The quick brown fox jumps over the lazy dog.",
        )
        assert result == TrackClassification.MAIN

    def test_metadata_takes_precedence(self):
        """Metadata-based detection should occur before transcript analysis."""
        result = detect_commentary_type(
            title="Director Commentary",
            transcript_sample="Regular dialogue without commentary patterns.",
        )
        assert result == TrackClassification.COMMENTARY

    @pytest.mark.parametrize(
        "transcript",
        [
            # "When we filmed" + "I wanted" = 2 patterns
            "When we filmed this scene, I wanted to show the tension.",
            # "on set" + "This scene" = 2 patterns
            "The actor was amazing on set. This scene took three days.",
            # "I think" + "the script" = 2 patterns
            "I think the script originally had this in a different location.",
        ],
    )
    def test_various_commentary_transcripts(self, transcript):
        """Should detect various commentary transcript patterns."""
        result = detect_commentary_type(
            title=None,
            transcript_sample=transcript,
        )
        assert result == TrackClassification.COMMENTARY


# =============================================================================
# Pattern Constants Tests
# =============================================================================


class TestCommentaryPatterns:
    """Tests for commentary pattern constants."""

    def test_commentary_keywords_not_empty(self):
        """COMMENTARY_KEYWORDS should contain patterns."""
        assert len(COMMENTARY_KEYWORDS) > 0

    def test_transcript_patterns_not_empty(self):
        """COMMENTARY_TRANSCRIPT_PATTERNS should contain patterns."""
        assert len(COMMENTARY_TRANSCRIPT_PATTERNS) > 0

    def test_keywords_are_lowercase(self):
        """All commentary keywords should be lowercase for matching."""
        for keyword in COMMENTARY_KEYWORDS:
            assert keyword == keyword.lower(), f"Keyword '{keyword}' not lowercase"

    def test_transcript_patterns_are_valid_regex(self):
        """All transcript patterns should be valid regex."""
        import re

        for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")
