"""Tests for the expression language serializer."""

import pytest

from vpo.policy.expressions import parse_expression, serialize_condition
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


class TestSerializeExists:
    def test_bare(self):
        cond = ExistsCondition(track_type="video", filters=TrackFilters())
        assert serialize_condition(cond) == "exists(video)"

    def test_with_language(self):
        cond = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
        )
        assert serialize_condition(cond) == "exists(audio, lang == eng)"

    def test_with_codec_tuple(self):
        cond = ExistsCondition(
            track_type="video",
            filters=TrackFilters(codec=("hevc", "h265")),
        )
        assert serialize_condition(cond) == "exists(video, codec in [hevc, h265])"

    def test_with_height_comparison(self):
        cond = ExistsCondition(
            track_type="video",
            filters=TrackFilters(
                height=Comparison(operator=ComparisonOperator.GTE, value=2160),
            ),
        )
        assert serialize_condition(cond) == "exists(video, height >= 2160)"

    def test_with_channels_exact(self):
        cond = ExistsCondition(
            track_type="audio",
            filters=TrackFilters(channels=2),
        )
        assert serialize_condition(cond) == "exists(audio, channels == 2)"


class TestSerializeCount:
    def test_basic(self):
        cond = CountCondition(
            track_type="audio",
            filters=TrackFilters(),
            operator=ComparisonOperator.EQ,
            value=1,
        )
        assert serialize_condition(cond) == "count(audio) == 1"

    def test_with_filters(self):
        cond = CountCondition(
            track_type="audio",
            filters=TrackFilters(language="eng"),
            operator=ComparisonOperator.GTE,
            value=2,
        )
        assert serialize_condition(cond) == "count(audio, lang == eng) >= 2"


class TestSerializeBooleans:
    def test_and(self):
        cond = AndCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(
                    track_type="audio",
                    filters=TrackFilters(language="eng"),
                ),
            )
        )
        result = serialize_condition(cond)
        assert result == "exists(video) and exists(audio, lang == eng)"

    def test_or(self):
        cond = OrCondition(
            conditions=(
                ExistsCondition(track_type="video", filters=TrackFilters()),
                ExistsCondition(track_type="audio", filters=TrackFilters()),
            )
        )
        result = serialize_condition(cond)
        assert result == "exists(video) or exists(audio)"

    def test_not(self):
        cond = NotCondition(
            inner=ExistsCondition(
                track_type="audio",
                filters=TrackFilters(language="eng"),
            )
        )
        result = serialize_condition(cond)
        assert result == "not exists(audio, lang == eng)"

    def test_or_in_and_gets_parens(self):
        """OR inside AND should be parenthesized."""
        cond = AndCondition(
            conditions=(
                OrCondition(
                    conditions=(
                        ExistsCondition(track_type="video", filters=TrackFilters()),
                        ExistsCondition(track_type="audio", filters=TrackFilters()),
                    )
                ),
                ExistsCondition(track_type="subtitle", filters=TrackFilters()),
            )
        )
        result = serialize_condition(cond)
        assert result == "(exists(video) or exists(audio)) and exists(subtitle)"

    def test_and_in_or_no_parens(self):
        """AND inside OR should NOT be parenthesized (higher precedence)."""
        cond = OrCondition(
            conditions=(
                AndCondition(
                    conditions=(
                        ExistsCondition(track_type="video", filters=TrackFilters()),
                        ExistsCondition(track_type="audio", filters=TrackFilters()),
                    )
                ),
                ExistsCondition(track_type="subtitle", filters=TrackFilters()),
            )
        )
        result = serialize_condition(cond)
        assert result == "exists(video) and exists(audio) or exists(subtitle)"


class TestSerializeSpecialized:
    def test_multi_language_defaults(self):
        cond = AudioIsMultiLanguageCondition()
        assert serialize_condition(cond) == "multi_language()"

    def test_multi_language_with_threshold(self):
        cond = AudioIsMultiLanguageCondition(threshold=0.1)
        assert serialize_condition(cond) == "multi_language(threshold == 0.1)"

    def test_plugin_equality(self):
        cond = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=MetadataComparisonOperator.EQ,
        )
        assert serialize_condition(cond) == "plugin(radarr, original_language) == jpn"

    def test_plugin_exists(self):
        cond = PluginMetadataCondition(
            plugin="radarr",
            field="year",
            operator=MetadataComparisonOperator.EXISTS,
        )
        assert serialize_condition(cond) == "plugin(radarr, year)"

    def test_container_meta(self):
        cond = ContainerMetadataCondition(
            field="title",
            value="720p",
            operator=MetadataComparisonOperator.EQ,
        )
        assert serialize_condition(cond) == "container_meta(title) == 720p"

    def test_is_original_defaults(self):
        cond = IsOriginalCondition()
        assert serialize_condition(cond) == "is_original()"

    def test_is_original_with_lang(self):
        cond = IsOriginalCondition(language="jpn")
        assert serialize_condition(cond) == "is_original(lang == jpn)"

    def test_is_dubbed_defaults(self):
        cond = IsDubbedCondition()
        assert serialize_condition(cond) == "is_dubbed()"

    def test_is_dubbed_with_lang_and_confidence(self):
        cond = IsDubbedCondition(language="eng", min_confidence=0.8)
        assert serialize_condition(cond) == "is_dubbed(confidence == 0.8, lang == eng)"


class TestRoundTrip:
    """Verify that parse -> serialize -> parse produces equivalent results."""

    @pytest.mark.parametrize(
        "expression",
        [
            "exists(video)",
            "exists(audio, lang == eng)",
            "exists(video, codec in [hevc, h265])",
            "exists(video, height >= 2160)",
            "count(audio) == 1",
            "count(audio, lang == eng) >= 2",
            "not exists(audio, lang == eng)",
            "exists(video) and exists(audio)",
            "exists(video) or exists(audio)",
            "multi_language()",
            "multi_language(threshold == 0.1)",
            "is_original()",
            "is_dubbed(lang == eng)",
        ],
    )
    def test_round_trip(self, expression):
        """Parse, serialize, re-parse: conditions should be equal."""
        cond1 = parse_expression(expression)
        serialized = serialize_condition(cond1)
        cond2 = parse_expression(serialized)
        assert cond1 == cond2
