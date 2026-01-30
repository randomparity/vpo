"""Unit tests for DefaultFlags conversion from Pydantic model to frozen dataclass."""

from vpo.policy.loader import load_policy_from_dict


def _make_policy_dict(*, default_flags: dict | None = None) -> dict:
    """Build a minimal valid policy dict with an optional default_flags section."""
    phase = {"name": "flags"}
    if default_flags is not None:
        phase["default_flags"] = default_flags
    return {
        "schema_version": 12,
        "phases": [phase],
    }


class TestPreferredAudioCodecConversion:
    """Verify preferred_audio_codec converts list to tuple."""

    def test_preferred_audio_codec_list_converts_to_tuple(self):
        data = _make_policy_dict(
            default_flags={"preferred_audio_codec": ["eac3", "ac3"]}
        )
        policy = load_policy_from_dict(data)
        result = policy.phases[0].default_flags.preferred_audio_codec
        assert result == ("eac3", "ac3")
        assert isinstance(result, tuple)

    def test_preferred_audio_codec_none_converts_to_none(self):
        data = _make_policy_dict(default_flags={})
        policy = load_policy_from_dict(data)
        result = policy.phases[0].default_flags.preferred_audio_codec
        assert result is None
