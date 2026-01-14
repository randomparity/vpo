"""Unit tests for language analysis formatters."""

import pytest

from vpo.language_analysis.formatters import (
    format_human,
    format_json,
)
from vpo.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageSegment,
)


@pytest.fixture
def sample_metadata() -> AnalysisMetadata:
    """Create sample metadata for tests."""
    return AnalysisMetadata(
        plugin_name="whisper",
        plugin_version="1.0.0",
        model_name="base",
        sample_positions=(30.0, 60.0, 90.0),
        sample_duration=5.0,
        total_duration=120.0,
        speech_ratio=0.85,
    )


@pytest.fixture
def single_language_result(sample_metadata: AnalysisMetadata) -> LanguageAnalysisResult:
    """Create a single-language analysis result."""
    segments = [
        LanguageSegment("eng", 30.0, 35.0, 0.95),
        LanguageSegment("eng", 60.0, 65.0, 0.92),
        LanguageSegment("eng", 90.0, 95.0, 0.94),
    ]
    return LanguageAnalysisResult.from_segments(
        track_id=1,
        file_hash="abc123",
        segments=segments,
        metadata=sample_metadata,
    )


@pytest.fixture
def multi_language_result(sample_metadata: AnalysisMetadata) -> LanguageAnalysisResult:
    """Create a multi-language analysis result."""
    segments = [
        LanguageSegment("eng", 30.0, 35.0, 0.95),
        LanguageSegment("eng", 60.0, 65.0, 0.92),
        LanguageSegment("fre", 90.0, 95.0, 0.88),
    ]
    return LanguageAnalysisResult.from_segments(
        track_id=2,
        file_hash="def456",
        segments=segments,
        metadata=sample_metadata,
    )


class TestFormatHuman:
    """Tests for format_human function."""

    def test_single_language_output(
        self, single_language_result: LanguageAnalysisResult
    ) -> None:
        """Test human output for single-language result."""
        output = format_human(single_language_result)

        assert "SINGLE-LANGUAGE" in output
        assert "eng" in output
        assert "100.0%" in output
        assert "3 samples" in output
        assert "85% speech detected" in output

    def test_multi_language_output(
        self, multi_language_result: LanguageAnalysisResult
    ) -> None:
        """Test human output for multi-language result."""
        output = format_human(multi_language_result)

        assert "MULTI-LANGUAGE" in output
        assert "Primary: eng" in output
        assert "Secondary:" in output
        assert "fre" in output

    def test_show_segments(
        self, single_language_result: LanguageAnalysisResult
    ) -> None:
        """Test that show_segments includes segment details."""
        output = format_human(single_language_result, show_segments=True)

        assert "Segments:" in output
        assert "30.0s-35.0s" in output
        assert "confidence:" in output

    def test_no_segments_by_default(
        self, single_language_result: LanguageAnalysisResult
    ) -> None:
        """Test that segments are not shown by default."""
        output = format_human(single_language_result, show_segments=False)

        assert "Segments:" not in output


class TestFormatJson:
    """Tests for format_json function."""

    def test_single_language_json(
        self, single_language_result: LanguageAnalysisResult
    ) -> None:
        """Test JSON output for single-language result."""
        data = format_json(single_language_result)

        assert data["classification"] == "SINGLE_LANGUAGE"
        assert data["primary_language"] == "eng"
        assert data["primary_percentage"] == 1.0
        assert data["secondary_languages"] == []
        assert data["is_multi_language"] is False
        assert len(data["segments"]) == 3
        assert data["metadata"]["plugin"] == "whisper"
        assert data["metadata"]["speech_ratio"] == 0.85

    def test_multi_language_json(
        self, multi_language_result: LanguageAnalysisResult
    ) -> None:
        """Test JSON output for multi-language result."""
        data = format_json(multi_language_result)

        assert data["classification"] == "MULTI_LANGUAGE"
        assert data["is_multi_language"] is True
        assert len(data["secondary_languages"]) > 0
        assert data["secondary_languages"][0]["code"] == "fre"

    def test_segments_structure(
        self, single_language_result: LanguageAnalysisResult
    ) -> None:
        """Test that segments have correct structure."""
        data = format_json(single_language_result)

        segment = data["segments"][0]
        assert "language" in segment
        assert "start_time" in segment
        assert "end_time" in segment
        assert "confidence" in segment
        assert segment["language"] == "eng"
        assert segment["start_time"] == 30.0
        assert segment["end_time"] == 35.0

    def test_json_serializable(
        self, multi_language_result: LanguageAnalysisResult
    ) -> None:
        """Test that output is JSON serializable."""
        import json

        data = format_json(multi_language_result)
        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
