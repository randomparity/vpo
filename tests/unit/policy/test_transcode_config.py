"""Tests for TranscodePolicyConfig.from_dict() factory method."""

import pytest

from vpo.policy.models import TranscodePolicyConfig


class TestTranscodePolicyConfigFromDict:
    """Tests for the from_dict factory method."""

    def test_from_dict_all_fields(self):
        """All fields are populated correctly."""
        data = {
            "target_video_codec": "hevc",
            "target_crf": 20,
            "target_bitrate": "5M",
            "max_resolution": "1080p",
            "max_width": 1920,
            "max_height": 1080,
            "audio_preserve_codecs": ["truehd", "dts-hd"],
            "audio_transcode_to": "opus",
            "audio_transcode_bitrate": "256k",
            "audio_downmix": "stereo",
            "destination": "{show}/{season}",
            "destination_fallback": "Unknown Show",
        }

        config = TranscodePolicyConfig.from_dict(data)

        assert config.target_video_codec == "hevc"
        assert config.target_crf == 20
        assert config.target_bitrate == "5M"
        assert config.max_resolution == "1080p"
        assert config.max_width == 1920
        assert config.max_height == 1080
        assert config.audio_preserve_codecs == ("truehd", "dts-hd")
        assert config.audio_transcode_to == "opus"
        assert config.audio_transcode_bitrate == "256k"
        assert config.audio_downmix == "stereo"
        assert config.destination == "{show}/{season}"
        assert config.destination_fallback == "Unknown Show"

    def test_from_dict_defaults(self):
        """Missing fields use defaults."""
        config = TranscodePolicyConfig.from_dict({})

        assert config.target_video_codec is None
        assert config.target_crf is None
        assert config.target_bitrate is None
        assert config.max_resolution is None
        assert config.max_width is None
        assert config.max_height is None
        assert config.audio_preserve_codecs == ()
        assert config.audio_transcode_to == "aac"
        assert config.audio_transcode_bitrate == "192k"
        assert config.audio_downmix is None
        assert config.destination is None
        assert config.destination_fallback == "Unknown"

    def test_from_dict_legacy_audio_bitrate(self):
        """Supports legacy 'audio_bitrate' key for backward compatibility."""
        data = {"audio_bitrate": "320k"}

        config = TranscodePolicyConfig.from_dict(data)

        assert config.audio_transcode_bitrate == "320k"

    def test_from_dict_prefers_new_audio_bitrate_key(self):
        """New 'audio_transcode_bitrate' key takes precedence over legacy."""
        data = {
            "audio_transcode_bitrate": "256k",
            "audio_bitrate": "128k",  # Legacy key should be ignored
        }

        config = TranscodePolicyConfig.from_dict(data)

        assert config.audio_transcode_bitrate == "256k"

    def test_from_dict_validation_invalid_codec(self):
        """Invalid video codec raises ValueError."""
        data = {"target_video_codec": "invalid_codec"}

        with pytest.raises(ValueError, match="Invalid target_video_codec"):
            TranscodePolicyConfig.from_dict(data)

    def test_from_dict_validation_invalid_crf(self):
        """Invalid CRF value raises ValueError."""
        data = {"target_crf": 100}  # Valid range is 0-51

        with pytest.raises(ValueError, match="Invalid target_crf"):
            TranscodePolicyConfig.from_dict(data)

    def test_from_dict_validation_invalid_resolution(self):
        """Invalid resolution raises ValueError."""
        data = {"max_resolution": "invalid"}

        with pytest.raises(ValueError, match="Invalid max_resolution"):
            TranscodePolicyConfig.from_dict(data)

    def test_from_dict_validation_invalid_audio_codec(self):
        """Invalid audio codec raises ValueError."""
        data = {"audio_transcode_to": "invalid_audio"}

        with pytest.raises(ValueError, match="Invalid audio_transcode_to"):
            TranscodePolicyConfig.from_dict(data)

    def test_from_dict_validation_invalid_downmix(self):
        """Invalid downmix value raises ValueError."""
        data = {"audio_downmix": "mono"}  # Only stereo and 5.1 are valid

        with pytest.raises(ValueError, match="Invalid audio_downmix"):
            TranscodePolicyConfig.from_dict(data)

    def test_from_dict_valid_codecs(self):
        """All valid video codecs are accepted."""
        for codec in ["h264", "hevc", "vp9", "av1"]:
            config = TranscodePolicyConfig.from_dict({"target_video_codec": codec})
            assert config.target_video_codec == codec

    def test_from_dict_valid_resolutions(self):
        """All valid resolutions are accepted."""
        for resolution in ["480p", "720p", "1080p", "1440p", "4k", "8k"]:
            config = TranscodePolicyConfig.from_dict({"max_resolution": resolution})
            assert config.max_resolution == resolution

    def test_from_dict_audio_preserve_codecs_tuple(self):
        """audio_preserve_codecs is converted to tuple."""
        data = {"audio_preserve_codecs": ["truehd", "flac"]}

        config = TranscodePolicyConfig.from_dict(data)

        assert isinstance(config.audio_preserve_codecs, tuple)
        assert config.audio_preserve_codecs == ("truehd", "flac")

    def test_from_dict_partial_fields(self):
        """Partial fields work correctly."""
        data = {
            "target_video_codec": "hevc",
            "target_crf": 23,
            # Other fields use defaults
        }

        config = TranscodePolicyConfig.from_dict(data)

        assert config.target_video_codec == "hevc"
        assert config.target_crf == 23
        assert config.audio_transcode_to == "aac"  # default
        assert config.audio_transcode_bitrate == "192k"  # default
