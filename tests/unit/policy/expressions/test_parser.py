"""Tests for the expression language parser."""

import pytest

from vpo.policy.expressions import parse_expression
from vpo.policy.expressions.errors import ParseError
from vpo.policy.types.conditions import (
    AndCondition,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    ContainerMetadataCondition,
    CountCondition,
    ExistsCondition,
    IsDubbedCondition,
    IsOriginalCondition,
    MetadataComparisonOperator,
    NotCondition,
    OrCondition,
    PluginMetadataCondition,
    TrackFilters,
)


class TestExistsCondition:
    def test_bare_exists(self):
        result = parse_expression("exists(video)")
        assert result == ExistsCondition(track_type="video", filters=TrackFilters())

    def test_exists_with_language(self):
        result = parse_expression("exists(audio, lang == eng)")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
        )

    def test_exists_with_codec(self):
        result = parse_expression("exists(video, codec == hevc)")
        assert result == ExistsCondition(
            track_type="video",
            filters=TrackFilters(codec="hevc"),
        )

    def test_exists_with_codec_list(self):
        result = parse_expression("exists(video, codec in [hevc, h265])")
        assert result == ExistsCondition(
            track_type="video",
            filters=TrackFilters(codec=("hevc", "h265")),
        )

    def test_exists_with_height_comparison(self):
        result = parse_expression("exists(video, height >= 2160)")
        assert result == ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                height=Comparison(operator=ComparisonOperator.GTE, value=2160),
            ),
        )

    def test_exists_with_channels_exact(self):
        result = parse_expression("exists(audio, channels == 2)")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(channels=2),
        )

    def test_exists_with_channels_comparison(self):
        result = parse_expression("exists(audio, channels >= 6)")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(
                channels=Comparison(operator=ComparisonOperator.GTE, value=6),
            ),
        )

    def test_exists_with_multiple_filters(self):
        result = parse_expression("exists(video, codec == hevc, height >= 2160)")
        assert result == ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                codec="hevc",
                height=Comparison(operator=ComparisonOperator.GTE, value=2160),
            ),
        )

    def test_exists_with_default_flag(self):
        result = parse_expression("exists(audio, default == true)")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(is_default=True),
        )

    def test_exists_with_forced_flag(self):
        result = parse_expression("exists(subtitle, forced == true)")
        assert result == ExistsCondition(
            track_type="subtitle",
            filters=TrackFilters(is_forced=True),
        )

    def test_exists_with_title(self):
        result = parse_expression('exists(audio, title == "Director Commentary")')
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(title="Director Commentary"),
        )

    def test_exists_with_not_commentary(self):
        result = parse_expression("exists(audio, not_commentary == true)")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(not_commentary=True),
        )

    def test_exists_subtitle(self):
        result = parse_expression("exists(subtitle, lang == eng)")
        assert result == ExistsCondition(
            track_type="subtitle",
            filters=TrackFilters(language="eng"),
        )

    def test_exists_attachment(self):
        result = parse_expression("exists(attachment)")
        assert result == ExistsCondition(
            track_type="attachment", filters=TrackFilters()
        )

    def test_exists_lang_list(self):
        result = parse_expression("exists(audio, lang in [eng, jpn, und])")
        assert result == ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language=("eng", "jpn", "und")),
        )

    def test_exists_invalid_track_type(self):
        with pytest.raises(ParseError, match="Invalid track type"):
            parse_expression("exists(unknown)")

    def test_exists_no_track_type(self):
        with pytest.raises(ParseError, match="requires a track type"):
            parse_expression("exists()")


class TestCountCondition:
    def test_count_equals(self):
        result = parse_expression("count(audio) == 1")
        assert result == CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.EQ,
            value=1,
        )

    def test_count_gte(self):
        result = parse_expression("count(audio) >= 2")
        assert result == CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.GTE,
            value=2,
        )

    def test_count_with_filters(self):
        result = parse_expression("count(audio, lang == eng) >= 2")
        assert result == CountCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
            operator=ComparisonOperator.GTE,
            value=2,
        )

    def test_count_lt(self):
        result = parse_expression("count(subtitle) < 5")
        assert result == CountCondition(
            track_type="subtitle",
            filters=TrackFilters(),
            operator=ComparisonOperator.LT,
            value=5,
        )

    def test_count_missing_comparison(self):
        with pytest.raises(ParseError, match="requires a trailing comparison"):
            parse_expression("count(audio)")

    def test_count_non_integer_value(self):
        with pytest.raises(ParseError, match="must be an integer"):
            parse_expression("count(audio) >= 2.5")


class TestBooleanOperators:
    def test_and(self):
        result = parse_expression("exists(video) and exists(audio, lang == eng)")
        assert isinstance(result, AndCondition)
        assert len(result.conditions) == 2
        assert result.conditions[0] == ExistsCondition(
            track_type="video", filters=TrackFilters()
        )
        assert result.conditions[1] == ExistsCondition(
            track_type="audio", filters=TrackFilters(language="eng")
        )

    def test_or(self):
        result = parse_expression("exists(video) or exists(audio)")
        assert isinstance(result, OrCondition)
        assert len(result.conditions) == 2

    def test_not(self):
        result = parse_expression("not exists(audio, lang == eng)")
        assert isinstance(result, NotCondition)
        assert result.inner == ExistsCondition(
            track_type="audio", filters=TrackFilters(language="eng")
        )

    def test_double_not(self):
        result = parse_expression("not not exists(video)")
        assert isinstance(result, NotCondition)
        assert isinstance(result.inner, NotCondition)
        assert result.inner.inner == ExistsCondition(
            track_type="video", filters=TrackFilters()
        )

    def test_precedence_and_binds_tighter_than_or(self):
        result = parse_expression("exists(video) or exists(audio) and exists(subtitle)")
        # Should parse as: exists(video) or (exists(audio) and exists(subtitle))
        assert isinstance(result, OrCondition)
        assert len(result.conditions) == 2
        assert isinstance(result.conditions[1], AndCondition)

    def test_parenthesized_or_in_and(self):
        result = parse_expression(
            "(exists(video) or exists(audio)) and exists(subtitle)"
        )
        assert isinstance(result, AndCondition)
        assert len(result.conditions) == 2
        assert isinstance(result.conditions[0], OrCondition)

    def test_triple_and(self):
        result = parse_expression(
            "exists(video) and exists(audio) and exists(subtitle)"
        )
        assert isinstance(result, AndCondition)
        assert len(result.conditions) == 3

    def test_not_with_and(self):
        result = parse_expression("not exists(video) and exists(audio)")
        assert isinstance(result, AndCondition)
        assert isinstance(result.conditions[0], NotCondition)

    def test_complex_nested(self):
        result = parse_expression(
            "(exists(video, codec == hevc) or exists(video, codec == h265)) "
            "and not exists(audio, lang == eng)"
        )
        assert isinstance(result, AndCondition)
        assert isinstance(result.conditions[0], OrCondition)
        assert isinstance(result.conditions[1], NotCondition)


class TestMultiLanguageCondition:
    def test_bare(self):
        result = parse_expression("multi_language()")
        assert result == AudioIsMultiLanguageCondition()

    def test_with_threshold(self):
        result = parse_expression("multi_language(threshold == 0.1)")
        assert result == AudioIsMultiLanguageCondition(threshold=0.1)

    def test_with_primary_language(self):
        result = parse_expression("multi_language(primary_language == eng)")
        assert result == AudioIsMultiLanguageCondition(primary_language="eng")

    def test_with_track_index(self):
        result = parse_expression("multi_language(track_index == 0)")
        assert result == AudioIsMultiLanguageCondition(track_index=0)


class TestPluginMetadataCondition:
    def test_equality(self):
        result = parse_expression('plugin(radarr, original_language) == "jpn"')
        assert result == PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=MetadataComparisonOperator.EQ,
        )

    def test_not_equal(self):
        result = parse_expression('plugin(radarr, status) != "ended"')
        assert result == PluginMetadataCondition(
            plugin="radarr",
            field="status",
            value="ended",
            operator=MetadataComparisonOperator.NEQ,
        )

    def test_exists(self):
        """Plugin without trailing comparison implies EXISTS check."""
        result = parse_expression("plugin(radarr, original_language)")
        assert result == PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            operator=MetadataComparisonOperator.EXISTS,
        )

    def test_numeric_comparison(self):
        result = parse_expression("plugin(radarr, year) >= 2020")
        assert result == PluginMetadataCondition(
            plugin="radarr",
            field="year",
            value=2020,
            operator=MetadataComparisonOperator.GTE,
        )

    def test_missing_args(self):
        with pytest.raises(ParseError, match="requires two positional"):
            parse_expression("plugin(radarr)")


class TestContainerMetaCondition:
    def test_equality(self):
        result = parse_expression('container_meta(title) == "720p"')
        assert result == ContainerMetadataCondition(
            field="title",
            value="720p",
            operator=MetadataComparisonOperator.EQ,
        )

    def test_not_equal(self):
        result = parse_expression('container_meta(title) != ""')
        assert result == ContainerMetadataCondition(
            field="title",
            value="",
            operator=MetadataComparisonOperator.NEQ,
        )

    def test_exists(self):
        result = parse_expression("container_meta(encoder)")
        assert result == ContainerMetadataCondition(
            field="encoder",
            operator=MetadataComparisonOperator.EXISTS,
        )


class TestIsOriginalCondition:
    def test_bare(self):
        result = parse_expression("is_original()")
        assert result == IsOriginalCondition()

    def test_with_language(self):
        result = parse_expression("is_original(lang == jpn)")
        assert result == IsOriginalCondition(language="jpn")

    def test_with_confidence(self):
        result = parse_expression("is_original(confidence == 0.8)")
        assert result == IsOriginalCondition(min_confidence=0.8)

    def test_with_value_false(self):
        result = parse_expression("is_original(value == false)")
        assert result == IsOriginalCondition(value=False)


class TestIsDubbedCondition:
    def test_bare(self):
        result = parse_expression("is_dubbed()")
        assert result == IsDubbedCondition()

    def test_with_language(self):
        result = parse_expression("is_dubbed(lang == eng)")
        assert result == IsDubbedCondition(language="eng")

    def test_with_confidence_and_lang(self):
        result = parse_expression("is_dubbed(lang == eng, confidence == 0.8)")
        assert result == IsDubbedCondition(language="eng", min_confidence=0.8)


class TestErrorHandling:
    def test_empty_expression(self):
        with pytest.raises(ParseError, match="Empty expression"):
            parse_expression("")

    def test_whitespace_only(self):
        with pytest.raises(ParseError, match="Empty expression"):
            parse_expression("   ")

    def test_unknown_function(self):
        with pytest.raises(ParseError, match="Unknown function"):
            parse_expression("unknown(video)")

    def test_trailing_tokens(self):
        with pytest.raises(ParseError, match="Unexpected token"):
            parse_expression("exists(video) extra")

    def test_unknown_filter(self):
        with pytest.raises(ParseError, match="Unknown filter"):
            parse_expression("exists(audio, bogus == 1)")

    def test_error_formatting(self):
        with pytest.raises(ParseError) as exc_info:
            parse_expression("exists(bad_type)")
        err = exc_info.value
        formatted = err.format_error()
        assert "^" in formatted
        assert "exists(bad_type)" in formatted
