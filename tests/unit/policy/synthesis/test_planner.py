"""Unit tests for policy/synthesis/planner.py.

Tests the synthesis plan generation functions:
- plan_synthesis: Generate complete synthesis plan for a file
- _evaluate_skip_if_exists: Check if synthesis should be skipped
- _compare_channels: Compare channel counts with operators
- _build_final_track_order: Build projected final track order
"""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from vpo.db.types import TrackInfo
from vpo.policy.synthesis.models import (
    AudioCodec,
    ChannelConfig,
    Position,
    PreferenceCriterion,
    SkippedSynthesis,
    SkipReason,
    SourcePreferences,
    SourceTrackSelection,
    SynthesisOperation,
    SynthesisPlan,
    SynthesisTrackDefinition,
)
from vpo.policy.synthesis.planner import (
    _build_final_track_order,
    _compare_channels,
    _convert_ref_to_definition,
    _evaluate_skip_if_exists,
    _resolve_track_position,
    plan_synthesis,
    resolve_synthesis_operation,
)
from vpo.policy.types import (
    AudioSynthesisConfig,
    Comparison,
    ComparisonOperator,
    SkipIfExistsCriteria,
    SynthesisTrackDefinitionRef,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def make_audio_track():
    """Factory for creating audio TrackInfo objects."""

    def _make(
        index: int = 0,
        codec: str = "aac",
        channels: int = 2,
        language: str = "eng",
        title: str | None = None,
        is_default: bool = False,
        is_forced: bool = False,
    ) -> TrackInfo:
        return TrackInfo(
            index=index,
            track_type="audio",
            codec=codec,
            channels=channels,
            language=language,
            title=title,
            is_default=is_default,
            is_forced=is_forced,
        )

    return _make


@pytest.fixture
def make_video_track():
    """Factory for creating video TrackInfo objects."""

    def _make(
        index: int = 0, codec: str = "h264", width: int = 1920, height: int = 1080
    ) -> TrackInfo:
        return TrackInfo(
            index=index,
            track_type="video",
            codec=codec,
            width=width,
            height=height,
        )

    return _make


@pytest.fixture
def sample_tracks(make_audio_track, make_video_track):
    """Create a sample set of tracks for testing."""
    return [
        make_video_track(index=0),
        make_audio_track(index=1, codec="truehd", channels=8, language="eng"),
        make_audio_track(index=2, codec="aac", channels=2, language="eng"),
        make_audio_track(index=3, codec="aac", channels=2, language="jpn"),
    ]


@pytest.fixture
def make_synthesis_definition():
    """Factory for creating SynthesisTrackDefinition objects."""

    def _make(
        name: str = "stereo_downmix",
        codec: AudioCodec = AudioCodec.AAC,
        channels: int | ChannelConfig = 2,
        bitrate: str | None = None,
        title: str = "inherit",
        language: str = "inherit",
        position: Position | int = Position.END,
        create_if=None,
        prefer: tuple[PreferenceCriterion, ...] = (),
    ) -> SynthesisTrackDefinition:
        return SynthesisTrackDefinition(
            name=name,
            codec=codec,
            channels=channels,
            source=SourcePreferences(prefer=prefer),
            bitrate=bitrate,
            create_if=create_if,
            title=title,
            language=language,
            position=position,
        )

    return _make


@pytest.fixture
def make_synthesis_ref():
    """Factory for creating SynthesisTrackDefinitionRef objects."""

    def _make(
        name: str = "stereo_downmix",
        codec: str = "aac",
        channels: str | int = "stereo",
        source_prefer: tuple[dict, ...] = (),
        bitrate: str | None = None,
        skip_if_exists: SkipIfExistsCriteria | None = None,
    ) -> SynthesisTrackDefinitionRef:
        return SynthesisTrackDefinitionRef(
            name=name,
            codec=codec,
            channels=channels,
            source_prefer=source_prefer,
            bitrate=bitrate,
            skip_if_exists=skip_if_exists,
        )

    return _make


# =============================================================================
# Tests for _compare_channels
# =============================================================================


class TestCompareChannels:
    """Tests for _compare_channels function."""

    def test_exact_match_int(self):
        """Integer criteria matches exact channel count."""
        assert _compare_channels(6, 6) is True
        assert _compare_channels(2, 2) is True
        assert _compare_channels(8, 8) is True

    def test_exact_match_int_fails(self):
        """Integer criteria fails when channels don't match."""
        assert _compare_channels(6, 2) is False
        assert _compare_channels(2, 6) is False
        assert _compare_channels(8, 6) is False

    def test_comparison_eq(self):
        """EQ comparison matches exact value."""
        criteria = Comparison(operator=ComparisonOperator.EQ, value=6)
        assert _compare_channels(6, criteria) is True
        assert _compare_channels(5, criteria) is False
        assert _compare_channels(7, criteria) is False

    def test_comparison_lt(self):
        """LT comparison matches values less than threshold."""
        criteria = Comparison(operator=ComparisonOperator.LT, value=6)
        assert _compare_channels(5, criteria) is True
        assert _compare_channels(2, criteria) is True
        assert _compare_channels(6, criteria) is False
        assert _compare_channels(8, criteria) is False

    def test_comparison_lte(self):
        """LTE comparison matches values less than or equal to threshold."""
        criteria = Comparison(operator=ComparisonOperator.LTE, value=6)
        assert _compare_channels(6, criteria) is True
        assert _compare_channels(5, criteria) is True
        assert _compare_channels(2, criteria) is True
        assert _compare_channels(7, criteria) is False
        assert _compare_channels(8, criteria) is False

    def test_comparison_gt(self):
        """GT comparison matches values greater than threshold."""
        criteria = Comparison(operator=ComparisonOperator.GT, value=2)
        assert _compare_channels(6, criteria) is True
        assert _compare_channels(8, criteria) is True
        assert _compare_channels(3, criteria) is True
        assert _compare_channels(2, criteria) is False
        assert _compare_channels(1, criteria) is False

    def test_comparison_gte(self):
        """GTE comparison matches values greater than or equal to threshold."""
        criteria = Comparison(operator=ComparisonOperator.GTE, value=6)
        assert _compare_channels(6, criteria) is True
        assert _compare_channels(8, criteria) is True
        assert _compare_channels(7, criteria) is True
        assert _compare_channels(5, criteria) is False
        assert _compare_channels(2, criteria) is False


# =============================================================================
# Tests for _evaluate_skip_if_exists
# =============================================================================


class TestEvaluateSkipIfExists:
    """Tests for _evaluate_skip_if_exists function."""

    def test_skips_when_codec_matches(self, make_audio_track):
        """Skips synthesis when codec matches criteria."""
        criteria = SkipIfExistsCriteria(codec="aac")
        tracks = [make_audio_track(codec="aac", channels=2)]

        should_skip, reason = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True
        assert "codec=aac" in reason

    def test_skips_when_codec_matches_case_insensitive(self, make_audio_track):
        """Codec matching is case-insensitive."""
        criteria = SkipIfExistsCriteria(codec="AAC")
        tracks = [make_audio_track(codec="aac", channels=2)]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True

    def test_skips_when_codec_matches_tuple(self, make_audio_track):
        """Skips when codec matches any value in tuple."""
        criteria = SkipIfExistsCriteria(codec=("aac", "opus"))
        tracks = [make_audio_track(codec="opus", channels=2)]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True

    def test_skips_when_channels_match_exact(self, make_audio_track):
        """Skips when channel count matches exactly."""
        criteria = SkipIfExistsCriteria(channels=6)
        tracks = [make_audio_track(channels=6)]

        should_skip, reason = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True
        assert "channels=6" in reason

    def test_skips_when_channels_match_comparison_lt(self, make_audio_track):
        """Skips when channels match LT comparison."""
        criteria = SkipIfExistsCriteria(
            channels=Comparison(operator=ComparisonOperator.LT, value=4)
        )
        tracks = [make_audio_track(channels=2)]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True

    def test_skips_when_channels_match_comparison_gte(self, make_audio_track):
        """Skips when channels match GTE comparison."""
        criteria = SkipIfExistsCriteria(
            channels=Comparison(operator=ComparisonOperator.GTE, value=6)
        )
        tracks = [make_audio_track(channels=8)]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True

    def test_skips_when_language_matches_case_insensitive(self, make_audio_track):
        """Skips when language matches (case-insensitive)."""
        criteria = SkipIfExistsCriteria(language="ENG")
        tracks = [make_audio_track(language="eng")]

        should_skip, reason = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True
        assert "language=eng" in reason

    def test_skips_when_language_matches_tuple(self, make_audio_track):
        """Skips when language matches any value in tuple."""
        criteria = SkipIfExistsCriteria(language=("eng", "und"))
        tracks = [make_audio_track(language="und")]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True

    def test_requires_all_criteria_to_match(self, make_audio_track):
        """All specified criteria must match (AND logic)."""
        criteria = SkipIfExistsCriteria(codec="aac", channels=6, language="eng")
        # This track has aac and eng but only 2 channels
        tracks = [make_audio_track(codec="aac", channels=2, language="eng")]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is False  # Channels don't match

    def test_not_commentary_filtering(self, make_audio_track):
        """not_commentary=True skips commentary tracks."""
        criteria = SkipIfExistsCriteria(codec="aac", not_commentary=True)
        # Track with "Commentary" in title should not match
        tracks = [make_audio_track(codec="aac", title="Director's Commentary")]

        should_skip, _ = _evaluate_skip_if_exists(
            criteria, tracks, commentary_patterns=("commentary",)
        )

        assert should_skip is False  # Track is commentary, filtered out

    def test_not_commentary_matches_non_commentary(self, make_audio_track):
        """not_commentary=True matches non-commentary tracks."""
        criteria = SkipIfExistsCriteria(codec="aac", not_commentary=True)
        tracks = [make_audio_track(codec="aac", title="English")]

        should_skip, reason = _evaluate_skip_if_exists(
            criteria, tracks, commentary_patterns=("commentary",)
        )

        assert should_skip is True
        assert "not_commentary" in reason

    def test_returns_false_when_no_tracks_match(self, make_audio_track):
        """Returns (False, None) when no tracks match all criteria."""
        criteria = SkipIfExistsCriteria(codec="opus")
        tracks = [make_audio_track(codec="aac")]

        should_skip, reason = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is False
        assert reason is None

    def test_returns_false_when_track_has_no_channels(self, make_audio_track):
        """Returns False when track has no channel info."""
        criteria = SkipIfExistsCriteria(channels=2)
        track = TrackInfo(index=0, track_type="audio", codec="aac", channels=None)
        tracks = [track]

        should_skip, _ = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is False

    def test_checks_multiple_tracks(self, make_audio_track):
        """Checks all tracks and matches the first that satisfies criteria."""
        criteria = SkipIfExistsCriteria(codec="opus")
        tracks = [
            make_audio_track(index=0, codec="aac"),
            make_audio_track(index=1, codec="truehd"),
            make_audio_track(index=2, codec="opus"),  # This one matches
        ]

        should_skip, reason = _evaluate_skip_if_exists(criteria, tracks)

        assert should_skip is True
        assert "Track 2" in reason


# =============================================================================
# Tests for plan_synthesis
# =============================================================================


class TestPlanSynthesis:
    """Tests for plan_synthesis function."""

    def test_creates_valid_plan_for_single_track(
        self, make_audio_track, make_synthesis_ref
    ):
        """Creates a plan with one synthesis operation."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]
        config = AudioSynthesisConfig(
            tracks=(make_synthesis_ref(name="stereo", codec="aac", channels="stereo"),)
        )

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            plan = plan_synthesis(
                file_id=str(uuid.uuid4()),
                file_path=Path("/test.mkv"),
                tracks=tracks,
                synthesis_config=config,
            )

        assert isinstance(plan, SynthesisPlan)
        assert len(plan.operations) == 1
        assert plan.operations[0].definition_name == "stereo"
        assert plan.operations[0].target_codec == AudioCodec.AAC

    def test_creates_plan_with_multiple_track_definitions(
        self, make_audio_track, make_synthesis_ref
    ):
        """Creates a plan with multiple synthesis operations."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]
        config = AudioSynthesisConfig(
            tracks=(
                make_synthesis_ref(name="stereo", codec="aac", channels="stereo"),
                make_synthesis_ref(name="surround", codec="eac3", channels="5.1"),
            )
        )

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            plan = plan_synthesis(
                file_id=str(uuid.uuid4()),
                file_path=Path("/test.mkv"),
                tracks=tracks,
                synthesis_config=config,
            )

        assert len(plan.operations) == 2
        assert plan.operations[0].definition_name == "stereo"
        assert plan.operations[1].definition_name == "surround"

    def test_skips_when_track_exists_matching_criteria(
        self, make_audio_track, make_synthesis_ref
    ):
        """Skips synthesis when skip_if_exists matches an existing track."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="aac", channels=2),  # Existing stereo AAC
        ]
        ref = make_synthesis_ref(
            name="stereo",
            codec="aac",
            channels="stereo",
            skip_if_exists=SkipIfExistsCriteria(codec="aac", channels=2),
        )
        config = AudioSynthesisConfig(tracks=(ref,))

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            plan = plan_synthesis(
                file_id=str(uuid.uuid4()),
                file_path=Path("/test.mkv"),
                tracks=tracks,
                synthesis_config=config,
            )

        assert len(plan.operations) == 0
        assert len(plan.skipped) == 1
        assert plan.skipped[0].reason == SkipReason.ALREADY_EXISTS

    def test_builds_correct_final_track_order(
        self, make_audio_track, make_synthesis_ref
    ):
        """Plan includes projected final track order."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]
        config = AudioSynthesisConfig(
            tracks=(make_synthesis_ref(name="stereo", codec="aac", channels="stereo"),)
        )

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            plan = plan_synthesis(
                file_id=str(uuid.uuid4()),
                file_path=Path("/test.mkv"),
                tracks=tracks,
                synthesis_config=config,
            )

        assert len(plan.final_track_order) >= 1
        # Original track should be in order
        original = [t for t in plan.final_track_order if t.track_type == "original"]
        assert len(original) == 1
        # Synthesized track should be in order
        synth = [t for t in plan.final_track_order if t.track_type == "synthesized"]
        assert len(synth) == 1

    def test_threads_plugin_metadata_through_pipeline(
        self, make_audio_track, make_synthesis_ref
    ):
        """Plugin metadata is passed through to condition evaluation."""
        from vpo.policy.types import PluginMetadataCondition, PluginMetadataOperator

        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]

        # Create a ref with create_if condition
        ref = SynthesisTrackDefinitionRef(
            name="anime_stereo",
            codec="aac",
            channels="stereo",
            source_prefer=(),
            create_if=PluginMetadataCondition(
                plugin="radarr",
                field="original_language",
                value="jpn",
                operator=PluginMetadataOperator.EQ,
            ),
        )
        config = AudioSynthesisConfig(tracks=(ref,))

        plugin_metadata = {"radarr": {"original_language": "eng"}}  # Not Japanese

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            plan = plan_synthesis(
                file_id=str(uuid.uuid4()),
                file_path=Path("/test.mkv"),
                tracks=tracks,
                synthesis_config=config,
                plugin_metadata=plugin_metadata,
            )

        # Should be skipped because condition not met
        assert len(plan.operations) == 0
        assert len(plan.skipped) == 1
        assert plan.skipped[0].reason == SkipReason.CONDITION_NOT_MET


# =============================================================================
# Tests for _build_final_track_order
# =============================================================================


class TestBuildFinalTrackOrder:
    """Tests for _build_final_track_order function."""

    def test_preserves_original_tracks(self, make_audio_track):
        """Original tracks are included in final order."""
        audio_tracks = [
            make_audio_track(index=0, codec="truehd", channels=8),
            make_audio_track(index=1, codec="aac", channels=2),
        ]
        operations = []

        result = _build_final_track_order(audio_tracks, operations)

        assert len(result) == 2
        assert all(t.track_type == "original" for t in result)
        assert result[0].codec == "truehd"
        assert result[1].codec == "aac"

    def test_includes_synthesized_tracks(self, make_audio_track):
        """Synthesized tracks are included in final order."""
        audio_tracks = [make_audio_track(index=0, codec="truehd", channels=8)]

        source_selection = SourceTrackSelection(
            track_index=0,
            track_info=audio_tracks[0],
            score=100,
            is_fallback=False,
            match_reasons=(),
        )
        operations = [
            SynthesisOperation(
                definition_name="stereo",
                source_track=source_selection,
                target_codec=AudioCodec.AAC,
                target_channels=2,
                target_bitrate=192000,
                target_title="Stereo",
                target_language="eng",
                target_position=1,  # After source
                downmix_filter="pan=stereo|...",
            )
        ]

        result = _build_final_track_order(audio_tracks, operations)

        assert len(result) == 2
        original = [t for t in result if t.track_type == "original"]
        synth = [t for t in result if t.track_type == "synthesized"]
        assert len(original) == 1
        assert len(synth) == 1
        assert synth[0].codec == "aac"
        assert synth[0].synthesis_name == "stereo"

    def test_renumbers_indices_after_insertion(self, make_audio_track):
        """Indices are renumbered after synthesized track insertion."""
        audio_tracks = [
            make_audio_track(index=0, codec="truehd", channels=8),
            make_audio_track(index=1, codec="aac", channels=2),
        ]

        source_selection = SourceTrackSelection(
            track_index=0,
            track_info=audio_tracks[0],
            score=100,
            is_fallback=False,
            match_reasons=(),
        )
        operations = [
            SynthesisOperation(
                definition_name="synth",
                source_track=source_selection,
                target_codec=AudioCodec.EAC3,
                target_channels=6,
                target_bitrate=640000,
                target_title="Synth",
                target_language="eng",
                target_position=1,  # Insert at position 1
                downmix_filter=None,
            )
        ]

        result = _build_final_track_order(audio_tracks, operations)

        # Verify indices are sequential
        for i, entry in enumerate(result):
            assert entry.index == i


# =============================================================================
# Tests for resolve_synthesis_operation
# =============================================================================


class TestResolveSynthesisOperation:
    """Tests for resolve_synthesis_operation function."""

    def test_returns_operation_for_valid_definition(
        self, make_audio_track, make_synthesis_definition
    ):
        """Returns SynthesisOperation for valid definition."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]
        definition = make_synthesis_definition()

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            result = resolve_synthesis_operation(definition, tracks)

        assert isinstance(result, SynthesisOperation)
        assert result.definition_name == "stereo_downmix"

    def test_returns_skipped_when_encoder_unavailable(
        self, make_audio_track, make_synthesis_definition
    ):
        """Returns SkippedSynthesis when encoder is not available."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="truehd", channels=8),
        ]
        definition = make_synthesis_definition()

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=False
        ):
            result = resolve_synthesis_operation(definition, tracks)

        assert isinstance(result, SkippedSynthesis)
        assert result.reason == SkipReason.ENCODER_UNAVAILABLE

    def test_returns_skipped_when_no_audio_tracks(self, make_synthesis_definition):
        """Returns SkippedSynthesis when no audio tracks available."""
        tracks = [TrackInfo(index=0, track_type="video", codec="h264")]
        definition = make_synthesis_definition()

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            result = resolve_synthesis_operation(definition, tracks)

        assert isinstance(result, SkippedSynthesis)
        assert result.reason == SkipReason.NO_SOURCE_AVAILABLE

    def test_returns_skipped_when_would_upmix(
        self, make_audio_track, make_synthesis_definition
    ):
        """Returns SkippedSynthesis when synthesis would require upmixing."""
        tracks = [
            TrackInfo(index=0, track_type="video", codec="h264"),
            make_audio_track(index=1, codec="aac", channels=2),  # 2ch source
        ]
        # Request 6 channels (5.1) from 2ch source = upmix
        definition = make_synthesis_definition(channels=6)

        with patch(
            "vpo.policy.synthesis.planner.is_encoder_available", return_value=True
        ):
            result = resolve_synthesis_operation(definition, tracks)

        assert isinstance(result, SkippedSynthesis)
        assert result.reason == SkipReason.WOULD_UPMIX


# =============================================================================
# Tests for _resolve_track_position
# =============================================================================


class TestResolveTrackPosition:
    """Tests for _resolve_track_position function."""

    def test_explicit_position_integer(self, make_audio_track):
        """Explicit integer position is converted (1-based to 0-based)."""
        audio_tracks = [make_audio_track(index=0)]

        result = _resolve_track_position(
            position=1,  # 1-based
            source_track_index=0,
            audio_tracks=audio_tracks,
            existing_synth_count=0,
        )

        assert result == 0  # Converted to 0-based

    def test_position_after_source(self, make_audio_track):
        """AFTER_SOURCE places track after source."""
        audio_tracks = [
            make_audio_track(index=0),
            make_audio_track(index=1),
        ]

        result = _resolve_track_position(
            position=Position.AFTER_SOURCE,
            source_track_index=0,
            audio_tracks=audio_tracks,
            existing_synth_count=0,
        )

        assert result == 1  # After track at index 0

    def test_position_end(self, make_audio_track):
        """END places track at end of audio tracks."""
        audio_tracks = [
            make_audio_track(index=0),
            make_audio_track(index=1),
        ]

        result = _resolve_track_position(
            position=Position.END,
            source_track_index=0,
            audio_tracks=audio_tracks,
            existing_synth_count=0,
        )

        assert result == 2  # After all tracks

    def test_position_end_accounts_for_existing_synth(self, make_audio_track):
        """END position accounts for already-planned synthesis tracks."""
        audio_tracks = [make_audio_track(index=0)]

        result = _resolve_track_position(
            position=Position.END,
            source_track_index=0,
            audio_tracks=audio_tracks,
            existing_synth_count=2,  # 2 already planned
        )

        assert result == 3  # 1 original + 2 existing synth


# =============================================================================
# Tests for _convert_ref_to_definition
# =============================================================================


class TestConvertRefToDefinition:
    """Tests for _convert_ref_to_definition function."""

    def test_converts_basic_ref(self, make_synthesis_ref):
        """Converts basic ref to full definition."""
        ref = make_synthesis_ref(name="test", codec="aac", channels="stereo")

        result = _convert_ref_to_definition(ref)

        assert isinstance(result, SynthesisTrackDefinition)
        assert result.name == "test"
        assert result.codec == AudioCodec.AAC
        assert result.target_channels == 2

    def test_converts_channel_configs(self, make_synthesis_ref):
        """Correctly converts channel configuration strings."""
        for channels_str, expected_count in [
            ("mono", 1),
            ("stereo", 2),
            ("5.1", 6),
            ("7.1", 8),
        ]:
            ref = make_synthesis_ref(channels=channels_str)
            result = _convert_ref_to_definition(ref)
            assert result.target_channels == expected_count

    def test_converts_integer_channels(self, make_synthesis_ref):
        """Preserves integer channel counts."""
        ref = make_synthesis_ref(channels=4)

        result = _convert_ref_to_definition(ref)

        assert result.channels == 4

    def test_converts_source_preferences(self, make_synthesis_ref):
        """Converts source_prefer to SourcePreferences."""
        ref = make_synthesis_ref(
            source_prefer=(
                {"language": "eng", "not_commentary": True},
                {"channels": "max"},
            )
        )

        result = _convert_ref_to_definition(ref)

        assert len(result.source.prefer) == 2
        assert result.source.prefer[0].language == "eng"
        assert result.source.prefer[0].not_commentary is True
