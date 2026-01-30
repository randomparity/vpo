"""Unit tests for Pydantic config models."""

from vpo.policy.pydantic_models.config import DefaultFlagsModel


class TestDefaultFlagsModelPreferredAudioCodec:
    """Tests for preferred_audio_codec field validation."""

    def test_bare_string_coerced_to_list(self):
        """A bare string (from YAML scalar) is coerced to a single-element list."""
        model = DefaultFlagsModel(preferred_audio_codec="eac3")
        assert model.preferred_audio_codec == ["eac3"]

    def test_list_accepted(self):
        """A list of strings is accepted as-is."""
        model = DefaultFlagsModel(preferred_audio_codec=["eac3", "ac3"])
        assert model.preferred_audio_codec == ["eac3", "ac3"]

    def test_casefolds_names(self):
        """Codec names are casefolded for case-insensitive matching."""
        model = DefaultFlagsModel(preferred_audio_codec=["EAC3", "AC3"])
        assert model.preferred_audio_codec == ["eac3", "ac3"]

    def test_bare_string_casefolds(self):
        """A bare string is both coerced to list and casefolded."""
        model = DefaultFlagsModel(preferred_audio_codec="TrueHD")
        assert model.preferred_audio_codec == ["truehd"]

    def test_none_passthrough(self):
        """None passes through unchanged."""
        model = DefaultFlagsModel(preferred_audio_codec=None)
        assert model.preferred_audio_codec is None

    def test_default_is_none(self):
        """Default value when omitted is None."""
        model = DefaultFlagsModel()
        assert model.preferred_audio_codec is None

    def test_empty_list_accepted(self):
        """An empty list is accepted (distinct from None)."""
        model = DefaultFlagsModel(preferred_audio_codec=[])
        assert model.preferred_audio_codec == []
