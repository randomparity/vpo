"""Unit tests for synthesis planner with plugin_metadata conditions."""

from __future__ import annotations

import pytest

from vpo.db.models import TrackInfo
from vpo.db.types import PluginMetadataDict
from vpo.policy.models import (
    PluginMetadataCondition,
    PluginMetadataOperator,
)
from vpo.policy.synthesis.models import (
    SkippedSynthesis,
    SkipReason,
)
from vpo.policy.synthesis.planner import (
    _evaluate_create_condition,
    resolve_synthesis_operation,
)


def make_audio_track(
    index: int,
    language: str | None = "eng",
    codec: str = "aac",
    channels: int = 2,
    title: str | None = None,
) -> TrackInfo:
    """Create a mock audio track for testing."""
    return TrackInfo(
        track_type="audio",
        index=index,
        codec=codec,
        language=language,
        channels=channels,
        title=title,
        is_default=False,
        is_forced=False,
    )


def make_synthesis_definition():
    """Create a minimal synthesis definition for testing."""
    from vpo.policy.synthesis.models import (
        AudioCodec,
        Position,
        SourcePreferences,
        SynthesisTrackDefinition,
    )

    return SynthesisTrackDefinition(
        name="test_synthesis",
        codec=AudioCodec.AAC,
        target_channels=2,
        bitrate=None,
        source=SourcePreferences(),
        position=Position.END,
        title="Test Track",
        language="inherit",
        create_if=None,
    )


class TestEvaluateCreateConditionWithPluginMetadata:
    """Tests for _evaluate_create_condition with plugin_metadata."""

    def test_plugin_metadata_condition_passes(self) -> None:
        """Test create_if with plugin_metadata condition that matches."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        tracks = [make_audio_track(0)]
        plugin_metadata: PluginMetadataDict = {"radarr": {"original_language": "jpn"}}

        result, reason = _evaluate_create_condition(
            condition, tracks, "test_def", plugin_metadata
        )

        assert result is True
        assert "True" in reason

    def test_plugin_metadata_condition_fails(self) -> None:
        """Test create_if with plugin_metadata condition that doesn't match."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        tracks = [make_audio_track(0)]
        plugin_metadata: PluginMetadataDict = {"radarr": {"original_language": "eng"}}

        result, reason = _evaluate_create_condition(
            condition, tracks, "test_def", plugin_metadata
        )

        assert result is False

    def test_plugin_metadata_condition_no_metadata(self) -> None:
        """Test create_if returns False when no plugin_metadata provided."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        tracks = [make_audio_track(0)]

        result, reason = _evaluate_create_condition(
            condition, tracks, "test_def", plugin_metadata=None
        )

        assert result is False
        assert "no plugin metadata available" in reason

    def test_plugin_metadata_condition_plugin_not_found(self) -> None:
        """Test create_if returns False when plugin not in metadata."""
        condition = PluginMetadataCondition(
            plugin="radarr",
            field="original_language",
            value="jpn",
            operator=PluginMetadataOperator.EQ,
        )
        tracks = [make_audio_track(0)]
        plugin_metadata: PluginMetadataDict = {"sonarr": {"series_title": "Test"}}

        result, reason = _evaluate_create_condition(
            condition, tracks, "test_def", plugin_metadata
        )

        assert result is False
        assert "plugin 'radarr' not in metadata" in reason

    def test_no_condition_returns_true(self) -> None:
        """Test that None condition returns True (always create)."""
        tracks = [make_audio_track(0)]

        result, reason = _evaluate_create_condition(
            None, tracks, "test_def", plugin_metadata=None
        )

        assert result is True
        assert "no condition specified" in reason


class TestResolveSynthesisOperationWithPluginMetadata:
    """Tests for resolve_synthesis_operation with plugin_metadata."""

    @pytest.fixture
    def definition_with_plugin_condition(self):
        """Create a synthesis definition with a plugin_metadata create_if condition."""
        from vpo.policy.synthesis.models import (
            AudioCodec,
            Position,
            PreferenceCriterion,
            SourcePreferences,
            SynthesisTrackDefinition,
        )

        return SynthesisTrackDefinition(
            name="anime_stereo",
            codec=AudioCodec.AAC,
            channels=2,
            source=SourcePreferences(prefer=(PreferenceCriterion(),)),
            bitrate=None,
            position=Position.END,
            title="Stereo for Anime",
            language="inherit",
            create_if=PluginMetadataCondition(
                plugin="radarr",
                field="original_language",
                value="jpn",
                operator=PluginMetadataOperator.EQ,
            ),
        )

    def test_skipped_when_condition_not_met(
        self, definition_with_plugin_condition
    ) -> None:
        """Test operation is skipped when plugin_metadata condition fails."""
        tracks = [make_audio_track(0, channels=6)]  # 6ch for valid downmix
        plugin_metadata: PluginMetadataDict = {"radarr": {"original_language": "eng"}}

        result = resolve_synthesis_operation(
            definition_with_plugin_condition,
            tracks,
            commentary_patterns=None,
            existing_operations=None,
            plugin_metadata=plugin_metadata,
        )

        assert isinstance(result, SkippedSynthesis)
        assert result.reason == SkipReason.CONDITION_NOT_MET
        assert "Condition not satisfied" in result.details

    def test_skipped_when_no_plugin_metadata(
        self, definition_with_plugin_condition
    ) -> None:
        """Test operation is skipped when no plugin_metadata available."""
        tracks = [make_audio_track(0, channels=6)]

        result = resolve_synthesis_operation(
            definition_with_plugin_condition,
            tracks,
            commentary_patterns=None,
            existing_operations=None,
            plugin_metadata=None,
        )

        assert isinstance(result, SkippedSynthesis)
        assert result.reason == SkipReason.CONDITION_NOT_MET
