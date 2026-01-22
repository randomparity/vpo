"""Tests for core/codecs.py - centralized codec registry."""

import pytest

from vpo.core.codecs import (
    AUDIO_CODEC_ALIASES,
    BITMAP_SUBTITLE_CODECS,
    DEFAULT_AUDIO_TRANSCODE_TARGET,
    MP4_AUDIO_TRANSCODE_DEFAULTS,
    MP4_COMPATIBLE_AUDIO_CODECS,
    MP4_COMPATIBLE_SUBTITLE_CODECS,
    MP4_COMPATIBLE_VIDEO_CODECS,
    MP4_CONVERTIBLE_SUBTITLE_CODECS,
    MP4_INCOMPATIBLE_CODECS,
    SUBTITLE_CODEC_ALIASES,
    VALID_TRANSCODE_AUDIO_CODECS,
    VALID_TRANSCODE_VIDEO_CODECS,
    VIDEO_CODEC_ALIASES,
    TranscodeTarget,
    audio_codec_matches,
    audio_codec_matches_any,
    codec_matches,
    get_canonical_codec,
    get_transcode_default,
    is_bitmap_subtitle,
    is_codec_compatible,
    is_codec_mp4_compatible,
    is_text_subtitle,
    normalize_codec,
    video_codec_matches,
    video_codec_matches_any,
)


class TestCodecAliases:
    """Tests for codec alias dictionaries."""

    def test_video_codec_aliases_uses_frozenset(self) -> None:
        """Video codec aliases values are frozensets."""
        for aliases in VIDEO_CODEC_ALIASES.values():
            assert isinstance(aliases, frozenset)

    def test_audio_codec_aliases_uses_frozenset(self) -> None:
        """Audio codec aliases values are frozensets."""
        for aliases in AUDIO_CODEC_ALIASES.values():
            assert isinstance(aliases, frozenset)

    def test_subtitle_codec_aliases_uses_frozenset(self) -> None:
        """Subtitle codec aliases values are frozensets."""
        for aliases in SUBTITLE_CODEC_ALIASES.values():
            assert isinstance(aliases, frozenset)

    def test_hevc_aliases_include_hvc1(self) -> None:
        """HEVC aliases include container-specific variants."""
        assert "hvc1" in VIDEO_CODEC_ALIASES["hevc"]
        assert "hev1" in VIDEO_CODEC_ALIASES["hevc"]

    def test_aac_aliases_include_mp4a(self) -> None:
        """AAC aliases include mp4a variant."""
        assert "mp4a" in AUDIO_CODEC_ALIASES["aac"]


class TestMP4CompatibilityMatrices:
    """Tests for MP4 compatibility constants."""

    def test_mp4_compatible_video_codecs_are_frozenset(self) -> None:
        """MP4 compatible video codecs is a frozenset."""
        assert isinstance(MP4_COMPATIBLE_VIDEO_CODECS, frozenset)

    def test_mp4_compatible_audio_codecs_are_frozenset(self) -> None:
        """MP4 compatible audio codecs is a frozenset."""
        assert isinstance(MP4_COMPATIBLE_AUDIO_CODECS, frozenset)

    def test_mp4_compatible_subtitle_codecs_are_frozenset(self) -> None:
        """MP4 compatible subtitle codecs is a frozenset."""
        assert isinstance(MP4_COMPATIBLE_SUBTITLE_CODECS, frozenset)

    def test_common_video_codecs_mp4_compatible(self) -> None:
        """Common video codecs are MP4 compatible."""
        assert "h264" in MP4_COMPATIBLE_VIDEO_CODECS
        assert "hevc" in MP4_COMPATIBLE_VIDEO_CODECS
        assert "av1" in MP4_COMPATIBLE_VIDEO_CODECS

    def test_common_audio_codecs_mp4_compatible(self) -> None:
        """Common audio codecs are MP4 compatible."""
        assert "aac" in MP4_COMPATIBLE_AUDIO_CODECS
        assert "ac3" in MP4_COMPATIBLE_AUDIO_CODECS
        assert "flac" in MP4_COMPATIBLE_AUDIO_CODECS

    def test_mov_text_subtitle_mp4_compatible(self) -> None:
        """mov_text subtitle is MP4 compatible."""
        assert "mov_text" in MP4_COMPATIBLE_SUBTITLE_CODECS

    def test_text_subtitles_convertible(self) -> None:
        """Text subtitle codecs are in convertible set."""
        assert "subrip" in MP4_CONVERTIBLE_SUBTITLE_CODECS
        assert "srt" in MP4_CONVERTIBLE_SUBTITLE_CODECS
        assert "ass" in MP4_CONVERTIBLE_SUBTITLE_CODECS

    def test_bitmap_subtitles_not_convertible(self) -> None:
        """Bitmap subtitles are in bitmap set."""
        assert "hdmv_pgs_subtitle" in BITMAP_SUBTITLE_CODECS
        assert "dvd_subtitle" in BITMAP_SUBTITLE_CODECS


class TestTranscodeDefaults:
    """Tests for transcode default configurations."""

    def test_transcode_target_dataclass(self) -> None:
        """TranscodeTarget is a frozen dataclass."""
        target = TranscodeTarget(codec="aac", bitrate="256k")
        assert target.codec == "aac"
        assert target.bitrate == "256k"
        with pytest.raises(AttributeError):
            target.codec = "mp3"  # type: ignore[misc]

    def test_default_transcode_target(self) -> None:
        """Default audio transcode target is AAC at 192k."""
        assert DEFAULT_AUDIO_TRANSCODE_TARGET.codec == "aac"
        assert DEFAULT_AUDIO_TRANSCODE_TARGET.bitrate == "192k"

    def test_truehd_transcode_default(self) -> None:
        """TrueHD has specific transcode default."""
        target = MP4_AUDIO_TRANSCODE_DEFAULTS["truehd"]
        assert target.codec == "aac"
        assert target.bitrate == "256k"

    def test_dts_hd_transcode_default(self) -> None:
        """DTS-HD has specific transcode default."""
        target = MP4_AUDIO_TRANSCODE_DEFAULTS["dts-hd"]
        assert target.codec == "aac"
        assert target.bitrate == "320k"


class TestValidationSets:
    """Tests for codec validation sets."""

    def test_valid_transcode_video_codecs(self) -> None:
        """Valid video transcode codecs are correct."""
        assert "h264" in VALID_TRANSCODE_VIDEO_CODECS
        assert "hevc" in VALID_TRANSCODE_VIDEO_CODECS
        assert "vp9" in VALID_TRANSCODE_VIDEO_CODECS
        assert "av1" in VALID_TRANSCODE_VIDEO_CODECS

    def test_valid_transcode_audio_codecs(self) -> None:
        """Valid audio transcode codecs are correct."""
        assert "aac" in VALID_TRANSCODE_AUDIO_CODECS
        assert "flac" in VALID_TRANSCODE_AUDIO_CODECS
        assert "opus" in VALID_TRANSCODE_AUDIO_CODECS


class TestNormalizeCodec:
    """Tests for normalize_codec function."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty string."""
        assert normalize_codec(None) == ""

    def test_lowercase_and_strip(self) -> None:
        """Codec is lowercased and stripped."""
        assert normalize_codec("  HEVC  ") == "hevc"

    def test_dts_hd_variants_normalize(self) -> None:
        """DTS-HD variants all normalize to 'dts-hd'."""
        assert normalize_codec("dts-hd ma") == "dts-hd"
        assert normalize_codec("dtshd") == "dts-hd"
        assert normalize_codec("DTS-HD MA") == "dts-hd"

    def test_truehd_normalizes(self) -> None:
        """TrueHD normalizes correctly."""
        assert normalize_codec("truehd") == "truehd"
        assert normalize_codec("TrueHD") == "truehd"


class TestGetCanonicalCodec:
    """Tests for get_canonical_codec function."""

    def test_video_codec_canonical(self) -> None:
        """Video codec returns canonical name."""
        assert get_canonical_codec("h265", "video") == "hevc"
        assert get_canonical_codec("avc", "video") == "h264"

    def test_audio_codec_canonical(self) -> None:
        """Audio codec returns canonical name."""
        assert get_canonical_codec("dca", "audio") == "dts"
        assert get_canonical_codec("mp4a", "audio") == "aac"

    def test_subtitle_codec_canonical(self) -> None:
        """Subtitle codec returns canonical name."""
        assert get_canonical_codec("srt", "subtitle") == "subrip"
        assert get_canonical_codec("ssa", "subtitle") == "ass"

    def test_unknown_codec_returns_normalized(self) -> None:
        """Unknown codec returns normalized version."""
        assert get_canonical_codec("unknown_codec", "video") == "unknown_codec"

    def test_unknown_track_type_returns_normalized(self) -> None:
        """Unknown track type returns normalized codec."""
        assert get_canonical_codec("HEVC", "data") == "hevc"


class TestCodecMatches:
    """Tests for generic codec_matches function."""

    def test_video_codec_matches(self) -> None:
        """Video codec matching works."""
        assert codec_matches("h265", "hevc", "video")
        assert not codec_matches("vp9", "hevc", "video")

    def test_audio_codec_matches(self) -> None:
        """Audio codec matching works."""
        assert codec_matches("dca", "dts", "audio")
        assert not codec_matches("aac", "flac", "audio")

    def test_subtitle_codec_matches(self) -> None:
        """Subtitle codec matching works."""
        assert codec_matches("srt", "subrip", "subtitle")
        assert not codec_matches("ass", "pgs", "subtitle")

    def test_none_codec_returns_false(self) -> None:
        """None codec returns False for all types."""
        assert not codec_matches(None, "hevc", "video")
        assert not codec_matches(None, "aac", "audio")
        assert not codec_matches(None, "srt", "subtitle")


class TestIsCodecMP4Compatible:
    """Tests for is_codec_mp4_compatible function."""

    def test_video_compatible(self) -> None:
        """Compatible video codecs return True."""
        assert is_codec_mp4_compatible("h264", "video")
        assert is_codec_mp4_compatible("hevc", "video")
        assert is_codec_mp4_compatible("av1", "video")

    def test_video_incompatible(self) -> None:
        """Incompatible video codecs return False."""
        assert not is_codec_mp4_compatible("prores", "video")

    def test_audio_compatible(self) -> None:
        """Compatible audio codecs return True."""
        assert is_codec_mp4_compatible("aac", "audio")
        assert is_codec_mp4_compatible("ac3", "audio")
        assert is_codec_mp4_compatible("flac", "audio")

    def test_audio_incompatible(self) -> None:
        """Incompatible audio codecs return False."""
        assert not is_codec_mp4_compatible("truehd", "audio")
        assert not is_codec_mp4_compatible("dts-hd", "audio")

    def test_subtitle_compatible(self) -> None:
        """Compatible subtitle codecs return True."""
        assert is_codec_mp4_compatible("mov_text", "subtitle")
        assert is_codec_mp4_compatible("webvtt", "subtitle")

    def test_subtitle_incompatible(self) -> None:
        """Incompatible subtitle codecs return False."""
        assert not is_codec_mp4_compatible("subrip", "subtitle")
        assert not is_codec_mp4_compatible("hdmv_pgs_subtitle", "subtitle")

    def test_case_insensitive(self) -> None:
        """Matching is case-insensitive."""
        assert is_codec_mp4_compatible("HEVC", "video")
        assert is_codec_mp4_compatible("AAC", "audio")

    def test_unknown_track_type_returns_false(self) -> None:
        """Unknown track types return False."""
        assert not is_codec_mp4_compatible("application/font", "attachment")


class TestIsCodecCompatible:
    """Tests for is_codec_compatible function."""

    def test_mp4_compatibility(self) -> None:
        """MP4 compatibility checks work."""
        assert is_codec_compatible("hevc", "mp4", "video")
        assert not is_codec_compatible("truehd", "mp4", "audio")

    def test_mkv_accepts_all(self) -> None:
        """MKV accepts all codecs."""
        assert is_codec_compatible("truehd", "mkv", "audio")
        assert is_codec_compatible("hdmv_pgs_subtitle", "mkv", "subtitle")
        assert is_codec_compatible("any_codec", "mkv", "video")

    def test_unknown_container_assumes_compatible(self) -> None:
        """Unknown containers assume compatibility."""
        assert is_codec_compatible("hevc", "avi", "video")
        assert is_codec_compatible("truehd", "unknown", "audio")


class TestGetTranscodeDefault:
    """Tests for get_transcode_default function."""

    def test_truehd_to_mp4(self) -> None:
        """TrueHD gets transcode default for MP4."""
        target = get_transcode_default("truehd", "mp4")
        assert target is not None
        assert target.codec == "aac"
        assert target.bitrate == "256k"

    def test_dts_hd_to_mp4(self) -> None:
        """DTS-HD gets transcode default for MP4."""
        target = get_transcode_default("dts-hd", "mp4")
        assert target is not None
        assert target.codec == "aac"
        assert target.bitrate == "320k"

    def test_known_incompatible_audio_gets_default(self) -> None:
        """Known incompatible audio codec gets default target."""
        # vorbis is in the explicit defaults
        target = get_transcode_default("vorbis", "mp4")
        assert target is not None
        assert target.codec == "aac"

    def test_pcm_variants_get_default(self) -> None:
        """PCM variants get default target."""
        target = get_transcode_default("pcm_s16le", "mp4")
        assert target is not None
        assert target.codec == "aac"

    def test_unknown_codec_returns_none(self) -> None:
        """Unknown codecs return None (require explicit config)."""
        target = get_transcode_default("some_weird_codec", "mp4")
        assert target is None

    def test_compatible_codec_returns_none(self) -> None:
        """Compatible codecs return None."""
        assert get_transcode_default("aac", "mp4") is None
        assert get_transcode_default("hevc", "mp4") is None

    def test_mkv_returns_none(self) -> None:
        """MKV container returns None (no transcode needed)."""
        assert get_transcode_default("truehd", "mkv") is None


class TestSubtitleClassification:
    """Tests for subtitle classification functions."""

    def test_is_text_subtitle(self) -> None:
        """Text subtitle detection works."""
        assert is_text_subtitle("subrip")
        assert is_text_subtitle("srt")
        assert is_text_subtitle("ass")
        assert is_text_subtitle("ssa")
        assert not is_text_subtitle("hdmv_pgs_subtitle")
        assert not is_text_subtitle("mov_text")  # Already MP4-compatible

    def test_is_bitmap_subtitle(self) -> None:
        """Bitmap subtitle detection works."""
        assert is_bitmap_subtitle("hdmv_pgs_subtitle")
        assert is_bitmap_subtitle("dvd_subtitle")
        assert is_bitmap_subtitle("pgssub")
        assert not is_bitmap_subtitle("subrip")
        assert not is_bitmap_subtitle("ass")


class TestMP4IncompatibleCodecs:
    """Tests for MP4_INCOMPATIBLE_CODECS set."""

    def test_lossless_audio_incompatible(self) -> None:
        """Lossless audio codecs are in incompatible set."""
        assert "truehd" in MP4_INCOMPATIBLE_CODECS
        assert "dts-hd ma" in MP4_INCOMPATIBLE_CODECS

    def test_bitmap_subtitles_incompatible(self) -> None:
        """Bitmap subtitles are in incompatible set."""
        assert "hdmv_pgs_subtitle" in MP4_INCOMPATIBLE_CODECS
        assert "dvd_subtitle" in MP4_INCOMPATIBLE_CODECS

    def test_text_subtitles_needing_conversion(self) -> None:
        """Text subtitles that need conversion are incompatible."""
        assert "subrip" in MP4_INCOMPATIBLE_CODECS
        assert "ass" in MP4_INCOMPATIBLE_CODECS


class TestVideoCodecMatchingBehavior:
    """Tests for video_codec_matches and video_codec_matches_any."""

    def test_matches_with_list(self) -> None:
        """video_codec_matches_any accepts lists."""
        assert video_codec_matches_any("hevc", ["hevc", "h264"])
        assert video_codec_matches_any("hevc", ("hevc", "h264"))

    def test_alias_matching_bidirectional(self) -> None:
        """Alias matching works both directions."""
        assert video_codec_matches("hvc1", "hevc")
        assert video_codec_matches("hevc", "hvc1")


class TestAudioCodecMatchingBehavior:
    """Tests for audio_codec_matches and audio_codec_matches_any."""

    def test_matches_with_list(self) -> None:
        """audio_codec_matches_any accepts lists."""
        assert audio_codec_matches_any("aac", ["aac", "flac"])
        assert audio_codec_matches_any("flac", ("aac", "flac"))

    def test_pcm_wildcard_matching(self) -> None:
        """PCM variants match with wildcard."""
        assert audio_codec_matches("pcm_s16le", "pcm_*")
        assert audio_codec_matches("pcm_s24le", "pcm_*")
        assert audio_codec_matches("pcm_f32le", "pcm_*")
