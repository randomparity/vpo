"""Unit tests for audio preservation during video transcoding (US8).

Tests the AudioTranscodeConfig dataclass and preserve (codec matching) logic.
"""

import pytest

from vpo.db import TrackInfo
from vpo.policy.codecs import (
    audio_codec_matches,
    audio_codec_matches_any,
    normalize_audio_codec,
)
from vpo.policy.types import (
    AudioTranscodeConfig,
)


def should_preserve_codec(codec: str | None, preserve_list: tuple[str, ...]) -> bool:
    """Check if a codec should be preserved (stream-copied).

    This is a compatibility wrapper for tests - the actual logic is in
    audio_codec_matches_any.
    """
    return audio_codec_matches_any(codec, preserve_list)


class TestAudioTranscodeConfigDataclass:
    """T032: Unit tests for AudioTranscodeConfig dataclass."""

    def test_default_values(self) -> None:
        """AudioTranscodeConfig has sensible defaults for lossless preservation."""
        config = AudioTranscodeConfig()

        assert config.preserve == ("truehd", "dts-hd", "flac", "pcm_s24le")
        assert config.to == "aac"
        assert config.bitrate == "192k"

    def test_custom_preserve(self) -> None:
        """AudioTranscodeConfig accepts custom preserve list."""
        config = AudioTranscodeConfig(
            preserve=("truehd", "dts-hd ma", "flac", "pcm_s16le", "pcm_s24le"),
            to="eac3",
            bitrate="640k",
        )

        assert "truehd" in config.preserve
        assert "dts-hd ma" in config.preserve
        assert config.to == "eac3"
        assert config.bitrate == "640k"

    def test_invalid_to_codec(self) -> None:
        """AudioTranscodeConfig rejects invalid target codec."""
        with pytest.raises(ValueError, match="Invalid target codec"):
            AudioTranscodeConfig(to="invalid_codec")

    def test_invalid_bitrate_format(self) -> None:
        """AudioTranscodeConfig rejects invalid bitrate format."""
        with pytest.raises(ValueError, match="Invalid bitrate"):
            AudioTranscodeConfig(bitrate="invalid")

    def test_valid_audio_codecs(self) -> None:
        """All common audio codecs can be used as transcode target."""
        valid_targets = ["aac", "ac3", "eac3", "flac", "opus", "mp3"]
        for codec in valid_targets:
            config = AudioTranscodeConfig(to=codec)
            assert config.to == codec

    def test_immutable(self) -> None:
        """AudioTranscodeConfig is frozen/immutable."""
        config = AudioTranscodeConfig()
        with pytest.raises(AttributeError):
            config.to = "ac3"  # type: ignore[misc]


class TestPreserveCodecsMatching:
    """T033: Unit tests for preserve (codec matching) logic."""

    def test_exact_codec_match(self) -> None:
        """Exact codec name matches."""
        assert audio_codec_matches("truehd", "truehd") is True
        assert audio_codec_matches("flac", "flac") is True
        assert audio_codec_matches("aac", "aac") is True

    def test_case_insensitive_match(self) -> None:
        """Codec matching is case-insensitive."""
        assert audio_codec_matches("TrueHD", "truehd") is True
        assert audio_codec_matches("truehd", "TRUEHD") is True
        assert audio_codec_matches("FLAC", "flac") is True

    def test_dts_hd_variants(self) -> None:
        """DTS-HD variants all match 'dts-hd' pattern."""
        assert audio_codec_matches("dts-hd ma", "dts-hd") is True
        assert audio_codec_matches("dts-hd", "dts-hd") is True
        assert audio_codec_matches("dtshd", "dts-hd") is True

    def test_pcm_variants(self) -> None:
        """PCM variants match 'pcm' pattern."""
        assert audio_codec_matches("pcm_s16le", "pcm") is True
        assert audio_codec_matches("pcm_s24le", "pcm") is True
        assert audio_codec_matches("pcm_s32le", "pcm") is True

    def test_wildcard_patterns(self) -> None:
        """Wildcard patterns work for codec matching."""
        assert audio_codec_matches("pcm_s24le", "pcm_*") is True
        assert audio_codec_matches("pcm_s16le", "pcm_*") is True

    def test_no_match(self) -> None:
        """Non-matching codecs return False."""
        assert audio_codec_matches("aac", "truehd") is False
        assert audio_codec_matches("ac3", "flac") is False

    def test_none_codec(self) -> None:
        """None codec returns False."""
        assert audio_codec_matches(None, "truehd") is False


class TestShouldPreserveCodec:
    """Additional tests for should_preserve_codec function."""

    def test_preserve_lossless_by_default(self) -> None:
        """Default preserve list includes common lossless codecs."""
        default_preserve = ("truehd", "dts-hd", "flac", "pcm_s24le")

        assert should_preserve_codec("truehd", default_preserve) is True
        assert should_preserve_codec("flac", default_preserve) is True
        assert should_preserve_codec("pcm_s24le", default_preserve) is True

    def test_transcode_lossy_by_default(self) -> None:
        """Lossy codecs are not preserved by default."""
        default_preserve = ("truehd", "dts-hd", "flac", "pcm_s24le")

        assert should_preserve_codec("aac", default_preserve) is False
        assert should_preserve_codec("ac3", default_preserve) is False
        assert should_preserve_codec("mp3", default_preserve) is False

    def test_empty_preserve_list(self) -> None:
        """Empty preserve list means nothing is preserved."""
        assert should_preserve_codec("truehd", ()) is False
        assert should_preserve_codec("flac", ()) is False


class TestAudioTrackPlanning:
    """T034: Unit tests for audio track planning (COPY vs TRANSCODE)."""

    def _make_audio_track(
        self,
        index: int,
        codec: str,
        language: str = "eng",
        channels: int = 6,
        channel_layout: str = "5.1",
    ) -> TrackInfo:
        """Create a test audio track."""
        return TrackInfo(
            index=index,
            track_type="audio",
            codec=codec,
            language=language,
            title=None,
            is_default=False,
            is_forced=False,
            channels=channels,
            channel_layout=channel_layout,
            width=None,
            height=None,
            frame_rate=None,
        )

    def test_lossless_track_is_copied(self) -> None:
        """Lossless audio track with codec in preserve list is copied."""
        track = self._make_audio_track(1, "truehd", channels=8, channel_layout="7.1")
        preserve_codecs = ("truehd", "dts-hd", "flac")

        # Check if codec should be preserved
        assert should_preserve_codec(track.codec, preserve_codecs) is True

    def test_lossy_track_is_transcoded(self) -> None:
        """Lossy audio track not in preserve list is transcoded."""
        track = self._make_audio_track(2, "ac3", channels=6, channel_layout="5.1")
        preserve_codecs = ("truehd", "dts-hd", "flac")

        # Check if codec should be transcoded
        assert should_preserve_codec(track.codec, preserve_codecs) is False

    def test_multiple_tracks_mixed_actions(self) -> None:
        """Multiple audio tracks can have different actions."""
        tracks = [
            self._make_audio_track(0, "truehd", channels=8),
            self._make_audio_track(1, "ac3", channels=6),
            self._make_audio_track(2, "aac", channels=2),
        ]
        preserve_codecs = ("truehd", "dts-hd", "flac")

        # TrueHD should be preserved
        assert should_preserve_codec(tracks[0].codec, preserve_codecs) is True
        # AC3 should be transcoded
        assert should_preserve_codec(tracks[1].codec, preserve_codecs) is False
        # AAC should be transcoded
        assert should_preserve_codec(tracks[2].codec, preserve_codecs) is False

    def test_preserve_dts_hd_ma(self) -> None:
        """DTS-HD MA specifically should be preserved."""
        track = self._make_audio_track(0, "dts-hd ma", channels=8)
        preserve_codecs = ("truehd", "dts-hd", "flac")

        assert should_preserve_codec(track.codec, preserve_codecs) is True

    def test_preserve_flac(self) -> None:
        """FLAC should be preserved as lossless."""
        track = self._make_audio_track(0, "flac", channels=2)
        preserve_codecs = ("truehd", "dts-hd", "flac")

        assert should_preserve_codec(track.codec, preserve_codecs) is True


class TestNormalizeAudioCodec:
    """Tests for audio codec name normalization."""

    def test_normalize_truehd(self) -> None:
        """TrueHD variants normalize correctly."""
        assert normalize_audio_codec("truehd") == "truehd"
        assert normalize_audio_codec("TrueHD") == "truehd"
        assert normalize_audio_codec("TRUEHD") == "truehd"

    def test_normalize_dts_hd(self) -> None:
        """DTS-HD variants normalize correctly."""
        assert normalize_audio_codec("dts-hd ma") == "dts-hd"
        assert normalize_audio_codec("dts-hd") == "dts-hd"
        assert normalize_audio_codec("dtshd") == "dts-hd"
        assert normalize_audio_codec("DTS-HD MA") == "dts-hd"

    def test_normalize_standard_codecs(self) -> None:
        """Standard codecs normalize to lowercase."""
        assert normalize_audio_codec("AAC") == "aac"
        assert normalize_audio_codec("AC3") == "ac3"
        assert normalize_audio_codec("FLAC") == "flac"

    def test_normalize_none(self) -> None:
        """None input returns empty string."""
        assert normalize_audio_codec(None) == ""
