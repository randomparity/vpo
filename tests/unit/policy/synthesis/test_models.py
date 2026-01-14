"""Unit tests for audio synthesis models."""

from pathlib import Path

from vpo.policy.synthesis.models import (
    AudioCodec,
    ChannelConfig,
    ChannelPreference,
    Position,
    PreferenceCriterion,
    SkippedSynthesis,
    SkipReason,
    SourcePreferences,
    SynthesisPlan,
    SynthesisTrackDefinition,
    TrackOrderEntry,
    get_default_bitrate,
)


class TestAudioCodec:
    """Tests for AudioCodec enum."""

    def test_all_values_defined(self):
        """Test that all expected codecs are defined."""
        assert AudioCodec.EAC3 == "eac3"
        assert AudioCodec.AAC == "aac"
        assert AudioCodec.AC3 == "ac3"
        assert AudioCodec.OPUS == "opus"
        assert AudioCodec.FLAC == "flac"


class TestChannelConfig:
    """Tests for ChannelConfig enum."""

    def test_channel_count_property(self):
        """Test channel_count property returns correct values."""
        assert ChannelConfig.MONO.channel_count == 1
        assert ChannelConfig.STEREO.channel_count == 2
        assert ChannelConfig.SURROUND_51.channel_count == 6
        assert ChannelConfig.SURROUND_71.channel_count == 8


class TestPosition:
    """Tests for Position enum."""

    def test_values(self):
        """Test position enum values."""
        assert Position.AFTER_SOURCE == "after_source"
        assert Position.END == "end"


class TestSkipReason:
    """Tests for SkipReason enum."""

    def test_all_reasons_defined(self):
        """Test that all skip reasons are defined."""
        assert SkipReason.CONDITION_NOT_MET
        assert SkipReason.NO_SOURCE_AVAILABLE
        assert SkipReason.WOULD_UPMIX
        assert SkipReason.ENCODER_UNAVAILABLE
        assert SkipReason.ALREADY_EXISTS


class TestGetDefaultBitrate:
    """Tests for get_default_bitrate function."""

    def test_eac3_51_default(self):
        """Test default bitrate for EAC3 5.1."""
        assert get_default_bitrate(AudioCodec.EAC3, 6) == 640_000

    def test_eac3_stereo_default(self):
        """Test default bitrate for EAC3 stereo."""
        assert get_default_bitrate(AudioCodec.EAC3, 2) == 384_000

    def test_aac_stereo_default(self):
        """Test default bitrate for AAC stereo."""
        assert get_default_bitrate(AudioCodec.AAC, 2) == 192_000

    def test_aac_51_default(self):
        """Test default bitrate for AAC 5.1."""
        assert get_default_bitrate(AudioCodec.AAC, 6) == 384_000

    def test_flac_returns_none(self):
        """Test that FLAC (lossless) returns None."""
        assert get_default_bitrate(AudioCodec.FLAC, 6) is None

    def test_nearest_channel_count(self):
        """Test that nearest supported channel count is used."""
        # 4 channels should use 5.1 (6ch) bitrate for EAC3
        result = get_default_bitrate(AudioCodec.EAC3, 4)
        assert result == 640_000  # Uses 5.1 bitrate


class TestPreferenceCriterion:
    """Tests for PreferenceCriterion dataclass."""

    def test_language_criterion(self):
        """Test creating a language criterion."""
        criterion = PreferenceCriterion(language=("eng", "und"))
        assert criterion.language == ("eng", "und")
        assert criterion.not_commentary is None

    def test_channels_max_criterion(self):
        """Test creating a max channels criterion."""
        criterion = PreferenceCriterion(channels=ChannelPreference.MAX)
        assert criterion.channels == ChannelPreference.MAX

    def test_codec_criterion(self):
        """Test creating a codec criterion."""
        criterion = PreferenceCriterion(codec=("truehd", "dts"))
        assert criterion.codec == ("truehd", "dts")


class TestSourcePreferences:
    """Tests for SourcePreferences dataclass."""

    def test_create_preferences(self):
        """Test creating source preferences."""
        prefs = SourcePreferences(
            prefer=(
                PreferenceCriterion(language="eng"),
                PreferenceCriterion(not_commentary=True),
                PreferenceCriterion(channels=ChannelPreference.MAX),
            )
        )
        assert len(prefs.prefer) == 3


class TestSynthesisTrackDefinition:
    """Tests for SynthesisTrackDefinition dataclass."""

    def test_target_channels_from_config(self):
        """Test target_channels property with ChannelConfig."""
        defn = SynthesisTrackDefinition(
            name="Test",
            codec=AudioCodec.EAC3,
            channels=ChannelConfig.SURROUND_51,
            source=SourcePreferences(prefer=(PreferenceCriterion(language="eng"),)),
        )
        assert defn.target_channels == 6

    def test_target_channels_from_int(self):
        """Test target_channels property with integer."""
        defn = SynthesisTrackDefinition(
            name="Test",
            codec=AudioCodec.EAC3,
            channels=4,
            source=SourcePreferences(prefer=(PreferenceCriterion(language="eng"),)),
        )
        assert defn.target_channels == 4

    def test_defaults(self):
        """Test default values."""
        defn = SynthesisTrackDefinition(
            name="Test",
            codec=AudioCodec.EAC3,
            channels=ChannelConfig.STEREO,
            source=SourcePreferences(prefer=(PreferenceCriterion(language="eng"),)),
        )
        assert defn.title == "inherit"
        assert defn.language == "inherit"
        assert defn.position == Position.END
        assert defn.bitrate is None


class TestSynthesisPlan:
    """Tests for SynthesisPlan dataclass."""

    def test_is_empty_with_no_operations(self):
        """Test is_empty returns True when no operations."""
        plan = SynthesisPlan(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            operations=(),
            skipped=(),
        )
        assert plan.is_empty is True

    def test_is_empty_with_skipped_only(self):
        """Test is_empty returns False when only skipped."""
        plan = SynthesisPlan(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            operations=(),
            skipped=(
                SkippedSynthesis(
                    definition_name="Test",
                    reason=SkipReason.CONDITION_NOT_MET,
                    details="Condition not satisfied",
                ),
            ),
        )
        # Skipped-only is not empty (there's something to report)
        assert plan.is_empty is False

    def test_has_operations(self):
        """Test has_operations property."""
        plan = SynthesisPlan(
            file_id="test-id",
            file_path=Path("/test/file.mkv"),
            operations=(),
            skipped=(),
        )
        assert plan.has_operations is False


class TestTrackOrderEntry:
    """Tests for TrackOrderEntry dataclass."""

    def test_original_track_entry(self):
        """Test creating an entry for an original track."""
        entry = TrackOrderEntry(
            index=0,
            track_type="original",
            codec="truehd",
            channels=8,
            language="eng",
            title="TrueHD 7.1",
            original_index=1,
        )
        assert entry.track_type == "original"
        assert entry.original_index == 1
        assert entry.synthesis_name is None

    def test_synthesized_track_entry(self):
        """Test creating an entry for a synthesized track."""
        entry = TrackOrderEntry(
            index=1,
            track_type="synthesized",
            codec="eac3",
            channels=6,
            language="eng",
            title="EAC3 5.1",
            synthesis_name="EAC3 Compatibility",
        )
        assert entry.track_type == "synthesized"
        assert entry.synthesis_name == "EAC3 Compatibility"
        assert entry.original_index is None


class TestSynthesisTrackNameValidation:
    """Tests for synthesis track name validation (security: path traversal prevention).

    The validation in SynthesisTrackDefinitionModel.validate_name() prevents path
    traversal attacks by rejecting names containing '/', '\\', or '..'. The name
    is used in file path construction (synth_{name}.ext) in executor.py.
    """

    def test_valid_names_accepted(self):
        """Test that valid names are accepted."""
        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        # Valid names that should work
        valid_names = [
            "EAC3 5.1 Compatibility",
            "AAC Stereo",
            "Test-Track_123",
            "Simple Name",
            "Track with spaces and hyphens-underscores_123",
        ]

        for name in valid_names:
            # Should not raise
            model = SynthesisTrackDefinitionModel(
                name=name,
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )
            assert model.name == name.strip()

    def test_single_dot_names_accepted(self):
        """Test that names with single dots (not '..') are accepted."""
        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        # Single dots are fine - only '..' is rejected
        valid_names = [".test", "test.", "test.name", "a.b.c", "v1.0 Release"]

        for name in valid_names:
            model = SynthesisTrackDefinitionModel(
                name=name,
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )
            assert model.name == name

    def test_path_traversal_with_forward_slash_rejected(self):
        """Test that names with forward slashes are rejected."""
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError) as exc_info:
            SynthesisTrackDefinitionModel(
                name="../../../tmp/evil",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

        assert "path separators" in str(exc_info.value).lower()

    def test_path_traversal_with_backslash_rejected(self):
        """Test that names with backslashes are rejected."""
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError) as exc_info:
            SynthesisTrackDefinitionModel(
                name="..\\..\\tmp\\evil",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

        assert "path separators" in str(exc_info.value).lower()

    def test_names_containing_dotdot_rejected(self):
        """Test that names containing '..' are rejected (conservative check).

        Note: This is intentionally conservative - names like "Track..v2" are
        rejected even though they're not actual path traversal attempts.
        """
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError) as exc_info:
            SynthesisTrackDefinitionModel(
                name="..evil",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

        assert "path separators" in str(exc_info.value).lower() or ".." in str(
            exc_info.value
        )

    def test_dotdot_embedded_in_name_rejected(self):
        """Test that '..' embedded in name is rejected (conservative check).

        Note: "test..test" is not actually a path traversal, but we reject it
        anyway for safety. This is documented in the validator docstring.
        """
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError):
            SynthesisTrackDefinitionModel(
                name="test..test",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

    def test_triple_dot_rejected(self):
        """Test that '...' is rejected (contains '..')."""
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError):
            SynthesisTrackDefinitionModel(
                name="...",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

    def test_empty_name_rejected(self):
        """Test that empty names are rejected."""
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError) as exc_info:
            SynthesisTrackDefinitionModel(
                name="",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_name_rejected(self):
        """Test that whitespace-only names are rejected."""
        import pytest
        from pydantic import ValidationError

        from vpo.policy.pydantic_models import (
            SynthesisTrackDefinitionModel,
        )

        with pytest.raises(ValidationError) as exc_info:
            SynthesisTrackDefinitionModel(
                name="   ",
                codec="eac3",
                channels="5.1",
                source={"prefer": [{"language": "eng"}]},
            )

        assert "empty" in str(exc_info.value).lower()
