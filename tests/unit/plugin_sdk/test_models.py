"""Unit tests for plugin_sdk models module."""

from __future__ import annotations

import pytest

from video_policy_orchestrator.plugin_sdk.models import (
    MatchResult,
    MatchStatus,
    MetadataEnrichment,
)


class TestMatchStatus:
    """Tests for MatchStatus enum."""

    def test_enum_values(self) -> None:
        """MatchStatus has MATCHED, UNMATCHED, UNCERTAIN, ERROR."""
        assert hasattr(MatchStatus, "MATCHED")
        assert hasattr(MatchStatus, "UNMATCHED")
        assert hasattr(MatchStatus, "UNCERTAIN")
        assert hasattr(MatchStatus, "ERROR")

    def test_value_strings(self) -> None:
        """Enum values are lowercase strings."""
        assert MatchStatus.MATCHED.value == "matched"
        assert MatchStatus.UNMATCHED.value == "unmatched"
        assert MatchStatus.UNCERTAIN.value == "uncertain"
        assert MatchStatus.ERROR.value == "error"


class TestMetadataEnrichment:
    """Tests for MetadataEnrichment dataclass."""

    def test_required_fields(self) -> None:
        """Can create with required fields only."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        assert enrichment.original_language == "eng"
        assert enrichment.external_source == "radarr"
        assert enrichment.external_id == 123
        assert enrichment.external_title == "Test Movie"

    def test_optional_fields_default_none(self) -> None:
        """Optional fields default to None."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        assert enrichment.external_year is None
        assert enrichment.imdb_id is None
        assert enrichment.tmdb_id is None
        assert enrichment.series_title is None
        assert enrichment.season_number is None
        assert enrichment.episode_number is None
        assert enrichment.episode_title is None
        assert enrichment.tvdb_id is None

    def test_frozen_dataclass(self) -> None:
        """Instance is immutable (frozen=True)."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        with pytest.raises(AttributeError):
            enrichment.external_id = 456  # type: ignore[misc]

    def test_to_dict_includes_required_fields(self) -> None:
        """to_dict() includes all required fields."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        result = enrichment.to_dict()
        assert result["original_language"] == "eng"
        assert result["external_source"] == "radarr"
        assert result["external_id"] == 123
        assert result["external_title"] == "Test Movie"

    def test_to_dict_excludes_none_optional_fields(self) -> None:
        """to_dict() omits None values for optional fields."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        result = enrichment.to_dict()
        # Optional fields should not be in dict when None
        assert "external_year" not in result
        assert "imdb_id" not in result
        assert "tmdb_id" not in result
        assert "series_title" not in result
        assert "season_number" not in result
        assert "episode_number" not in result
        assert "episode_title" not in result
        assert "tvdb_id" not in result

    def test_to_dict_includes_present_optional_fields(self) -> None:
        """to_dict() includes optional fields when set."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
            external_year=2024,
            imdb_id="tt1234567",
            tmdb_id=9999,
        )
        result = enrichment.to_dict()
        assert result["external_year"] == 2024
        assert result["imdb_id"] == "tt1234567"
        assert result["tmdb_id"] == 9999

    def test_tv_specific_fields_in_dict(self) -> None:
        """TV fields (series_title, season/episode, tvdb_id) included."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="sonarr",
            external_id=456,
            external_title="Test Series",
            series_title="Test Series",
            season_number=1,
            episode_number=5,
            episode_title="Test Episode",
            tvdb_id=12345,
        )
        result = enrichment.to_dict()
        assert result["series_title"] == "Test Series"
        assert result["season_number"] == 1
        assert result["episode_number"] == 5
        assert result["episode_title"] == "Test Episode"
        assert result["tvdb_id"] == 12345

    def test_movie_enrichment_roundtrip(self) -> None:
        """Movie enrichment data survives to_dict conversion."""
        enrichment = MetadataEnrichment(
            original_language="fra",
            external_source="radarr",
            external_id=999,
            external_title="Un Film Francais",
            external_year=2020,
            imdb_id="tt9999999",
            tmdb_id=88888,
        )
        result = enrichment.to_dict()
        assert result["original_language"] == "fra"
        assert result["external_source"] == "radarr"
        assert result["external_id"] == 999
        assert result["external_title"] == "Un Film Francais"
        assert result["external_year"] == 2020
        assert result["imdb_id"] == "tt9999999"
        assert result["tmdb_id"] == 88888

    def test_tv_enrichment_roundtrip(self) -> None:
        """TV show enrichment data survives to_dict conversion."""
        enrichment = MetadataEnrichment(
            original_language="jpn",
            external_source="sonarr",
            external_id=789,
            external_title="Anime Series",
            series_title="Anime Series",
            season_number=2,
            episode_number=12,
            episode_title="Final Episode",
            tvdb_id=77777,
        )
        result = enrichment.to_dict()
        assert len(result) == 9  # 4 required + 5 TV fields


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_matched_status_with_enrichment(self) -> None:
        """MATCHED status with enrichment."""
        enrichment = MetadataEnrichment(
            original_language="eng",
            external_source="radarr",
            external_id=123,
            external_title="Test Movie",
        )
        result = MatchResult(
            status=MatchStatus.MATCHED,
            enrichment=enrichment,
        )
        assert result.status == MatchStatus.MATCHED
        assert result.enrichment is not None
        assert result.enrichment.external_id == 123

    def test_error_status_with_message(self) -> None:
        """ERROR status should have error_message."""
        result = MatchResult(
            status=MatchStatus.ERROR,
            error_message="Connection failed",
        )
        assert result.status == MatchStatus.ERROR
        assert result.error_message == "Connection failed"
        assert result.enrichment is None

    def test_uncertain_with_candidates(self) -> None:
        """UNCERTAIN can have candidate IDs."""
        result = MatchResult(
            status=MatchStatus.UNCERTAIN,
            candidates=(123, 456, 789),
        )
        assert result.status == MatchStatus.UNCERTAIN
        assert result.candidates == (123, 456, 789)

    def test_unmatched_minimal(self) -> None:
        """UNMATCHED works with defaults."""
        result = MatchResult(status=MatchStatus.UNMATCHED)
        assert result.status == MatchStatus.UNMATCHED
        assert result.enrichment is None
        assert result.error_message is None
        assert result.candidates == ()

    def test_frozen_dataclass(self) -> None:
        """Instance is immutable."""
        result = MatchResult(status=MatchStatus.UNMATCHED)
        with pytest.raises(AttributeError):
            result.status = MatchStatus.MATCHED  # type: ignore[misc]

    def test_candidates_is_tuple(self) -> None:
        """candidates field is tuple (immutable)."""
        result = MatchResult(
            status=MatchStatus.UNCERTAIN,
            candidates=(1, 2, 3),
        )
        assert isinstance(result.candidates, tuple)
