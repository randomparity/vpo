"""Tests for policy/codecs.py - unified codec matching."""

from vpo.policy.codecs import (
    AUDIO_CODEC_ALIASES,
    VIDEO_CODEC_ALIASES,
    audio_codec_matches,
    audio_codec_matches_any,
    normalize_audio_codec,
    normalize_video_codec,
    video_codec_matches,
    video_codec_matches_any,
)


class TestVideoCodecAliases:
    """Tests for VIDEO_CODEC_ALIASES coverage."""

    def test_hevc_aliases(self) -> None:
        """HEVC has expected aliases."""
        assert "hevc" in VIDEO_CODEC_ALIASES
        assert "h265" in VIDEO_CODEC_ALIASES["hevc"]
        assert "x265" in VIDEO_CODEC_ALIASES["hevc"]

    def test_h264_aliases(self) -> None:
        """H.264 has expected aliases."""
        assert "h264" in VIDEO_CODEC_ALIASES
        assert "avc" in VIDEO_CODEC_ALIASES["h264"]
        assert "x264" in VIDEO_CODEC_ALIASES["h264"]


class TestAudioCodecAliases:
    """Tests for AUDIO_CODEC_ALIASES coverage."""

    def test_truehd_aliases(self) -> None:
        """TrueHD has expected aliases."""
        assert "truehd" in AUDIO_CODEC_ALIASES
        assert "dolby truehd" in AUDIO_CODEC_ALIASES["truehd"]

    def test_dts_hd_aliases(self) -> None:
        """DTS-HD has expected aliases."""
        assert "dts-hd" in AUDIO_CODEC_ALIASES
        assert "dts-hd ma" in AUDIO_CODEC_ALIASES["dts-hd"]
        assert "dtshd" in AUDIO_CODEC_ALIASES["dts-hd"]


class TestNormalizeVideoCodec:
    """Tests for normalize_video_codec function."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty string."""
        assert normalize_video_codec(None) == ""

    def test_lowercase(self) -> None:
        """Codec is lowercased."""
        assert normalize_video_codec("HEVC") == "hevc"

    def test_strips_whitespace(self) -> None:
        """Whitespace is stripped."""
        assert normalize_video_codec("  hevc  ") == "hevc"


class TestNormalizeAudioCodec:
    """Tests for normalize_audio_codec function."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty string."""
        assert normalize_audio_codec(None) == ""

    def test_dts_hd_variants_normalize(self) -> None:
        """DTS-HD variants all normalize to 'dts-hd'."""
        assert normalize_audio_codec("dts-hd ma") == "dts-hd"
        assert normalize_audio_codec("dtshd") == "dts-hd"
        assert normalize_audio_codec("DTS-HD MA") == "dts-hd"

    def test_truehd_normalizes(self) -> None:
        """TrueHD variants normalize to 'truehd'."""
        assert normalize_audio_codec("truehd") == "truehd"
        assert normalize_audio_codec("TrueHD") == "truehd"

    def test_regular_codec_unchanged(self) -> None:
        """Regular codecs just get lowercased."""
        assert normalize_audio_codec("AAC") == "aac"
        assert normalize_audio_codec("FLAC") == "flac"


class TestVideoCodecMatches:
    """Tests for video_codec_matches function."""

    def test_exact_match(self) -> None:
        """Exact codec name matches."""
        assert video_codec_matches("hevc", "hevc")
        assert video_codec_matches("h264", "h264")

    def test_case_insensitive(self) -> None:
        """Matching is case-insensitive."""
        assert video_codec_matches("HEVC", "hevc")
        assert video_codec_matches("hevc", "HEVC")

    def test_alias_match_h265_to_hevc(self) -> None:
        """h265 matches hevc target."""
        assert video_codec_matches("h265", "hevc")
        assert video_codec_matches("x265", "hevc")

    def test_alias_match_hevc_to_h265(self) -> None:
        """hevc matches h265 target."""
        assert video_codec_matches("hevc", "h265")

    def test_avc_aliases(self) -> None:
        """AVC aliases work correctly."""
        assert video_codec_matches("avc", "h264")
        assert video_codec_matches("h264", "avc")
        assert video_codec_matches("x264", "h264")

    def test_no_match(self) -> None:
        """Non-matching codecs return False."""
        assert not video_codec_matches("hevc", "h264")
        assert not video_codec_matches("vp9", "av1")

    def test_none_codec_returns_false(self) -> None:
        """None codec returns False."""
        assert not video_codec_matches(None, "hevc")


class TestVideoCodecMatchesAny:
    """Tests for video_codec_matches_any function."""

    def test_none_patterns_returns_true(self) -> None:
        """None patterns = always passes."""
        assert video_codec_matches_any("hevc", None)

    def test_none_codec_returns_false(self) -> None:
        """None codec returns False."""
        assert not video_codec_matches_any(None, ("hevc", "h264"))

    def test_matches_first_pattern(self) -> None:
        """Matches first pattern in tuple."""
        assert video_codec_matches_any("hevc", ("hevc", "h264"))

    def test_matches_second_pattern(self) -> None:
        """Matches second pattern in tuple."""
        assert video_codec_matches_any("h264", ("hevc", "h264"))

    def test_matches_via_alias(self) -> None:
        """Matches via alias."""
        assert video_codec_matches_any("h265", ("hevc",))
        assert video_codec_matches_any("avc", ("h264",))

    def test_no_match_returns_false(self) -> None:
        """No match returns False."""
        assert not video_codec_matches_any("vp9", ("hevc", "h264"))


class TestAudioCodecMatches:
    """Tests for audio_codec_matches function."""

    def test_exact_match(self) -> None:
        """Exact codec name matches."""
        assert audio_codec_matches("aac", "aac")
        assert audio_codec_matches("flac", "flac")

    def test_alias_group_match(self) -> None:
        """Alias group name matches variants."""
        assert audio_codec_matches("truehd", "truehd")
        assert audio_codec_matches("dolby truehd", "truehd")

    def test_dts_alias_match(self) -> None:
        """DTS aliases work correctly."""
        assert audio_codec_matches("dts", "dts")
        assert audio_codec_matches("dca", "dts")

    def test_wildcard_match(self) -> None:
        """Wildcard patterns work."""
        assert audio_codec_matches("pcm_s16le", "pcm_*")
        assert audio_codec_matches("pcm_s24le", "pcm_*")

    def test_fuzzy_match(self) -> None:
        """Fuzzy matching (pattern in codec) works."""
        assert audio_codec_matches("pcm_s16le", "pcm")

    def test_none_codec_returns_false(self) -> None:
        """None codec returns False."""
        assert not audio_codec_matches(None, "aac")

    def test_no_match(self) -> None:
        """Non-matching codecs return False."""
        assert not audio_codec_matches("aac", "flac")
        assert not audio_codec_matches("opus", "vorbis")


class TestAudioCodecMatchesAny:
    """Tests for audio_codec_matches_any function."""

    def test_none_patterns_returns_true(self) -> None:
        """None patterns returns True (no filter = always passes)."""
        assert audio_codec_matches_any("aac", None)

    def test_none_codec_returns_false(self) -> None:
        """None codec returns False."""
        assert not audio_codec_matches_any(None, ("aac", "flac"))

    def test_matches_any_in_list(self) -> None:
        """Matches any pattern in list."""
        assert audio_codec_matches_any("aac", ("aac", "flac"))
        assert audio_codec_matches_any("flac", ("aac", "flac"))

    def test_no_match_returns_false(self) -> None:
        """No match returns False."""
        assert not audio_codec_matches_any("opus", ("aac", "flac"))
