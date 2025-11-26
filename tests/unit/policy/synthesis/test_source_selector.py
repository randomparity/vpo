"""Unit tests for source track selection."""

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.synthesis.models import (
    ChannelPreference,
    PreferenceCriterion,
    SourcePreferences,
)
from video_policy_orchestrator.policy.synthesis.source_selector import (
    _is_commentary_track,
    filter_audio_tracks,
    score_track,
    select_source_track,
)


def make_audio_track(
    index: int,
    language: str | None = "eng",
    codec: str = "truehd",
    channels: int = 8,
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


class TestScoreTrack:
    """Tests for score_track function."""

    def test_language_match_scores(self):
        """Test that matching language adds score."""
        track = make_audio_track(0, language="eng")
        criterion = PreferenceCriterion(language="eng")

        score, reasons = score_track(track, criterion)

        assert score > 0
        assert "language=eng" in reasons

    def test_language_no_match(self):
        """Test that non-matching language doesn't add score."""
        track = make_audio_track(0, language="jpn")
        criterion = PreferenceCriterion(language="eng")

        score, reasons = score_track(track, criterion)

        assert score == 0
        assert not reasons

    def test_not_commentary_scores(self):
        """Test that non-commentary tracks get score with not_commentary."""
        track = make_audio_track(0, title="Main Audio")
        criterion = PreferenceCriterion(not_commentary=True)

        score, reasons = score_track(track, criterion)

        assert score > 0
        assert "not_commentary" in reasons

    def test_commentary_no_score(self):
        """Test that commentary tracks don't get not_commentary score."""
        track = make_audio_track(0, title="Director's Commentary")
        criterion = PreferenceCriterion(not_commentary=True)

        score, reasons = score_track(track, criterion)

        assert score == 0

    def test_channels_max_preference(self):
        """Test that max channels preference scores by channel count."""
        track = make_audio_track(0, channels=8)
        criterion = PreferenceCriterion(channels=ChannelPreference.MAX)

        score, reasons = score_track(track, criterion)

        # 8 channels * 10 points per channel = 80
        assert score == 80
        assert "channels=8" in reasons

    def test_channels_min_preference(self):
        """Test that min channels preference penalizes high counts."""
        track = make_audio_track(0, channels=8)
        criterion = PreferenceCriterion(channels=ChannelPreference.MIN)

        score, reasons = score_track(track, criterion)

        # 8 channels * -10 points per channel = -80
        assert score == -80

    def test_codec_match(self):
        """Test that matching codec adds score."""
        track = make_audio_track(0, codec="truehd")
        criterion = PreferenceCriterion(codec="truehd")

        score, reasons = score_track(track, criterion)

        assert score > 0
        assert "codec=truehd" in reasons

    def test_codec_no_match(self):
        """Test that non-matching codec doesn't add score."""
        track = make_audio_track(0, codec="aac")
        criterion = PreferenceCriterion(codec="truehd")

        score, reasons = score_track(track, criterion)

        assert score == 0

    def test_multiple_criteria_accumulate(self):
        """Test that multiple matching criteria accumulate score."""
        track = make_audio_track(0, language="eng", channels=6, title="Main")
        criterion = PreferenceCriterion(
            language="eng",
            not_commentary=True,
            channels=ChannelPreference.MAX,
        )

        score, reasons = score_track(track, criterion)

        # language(100) + not_commentary(80) + channels(60) = 240
        assert score == 240
        assert len(reasons) == 3


class TestIsCommentaryTrack:
    """Tests for _is_commentary_track function."""

    def test_commentary_in_title(self):
        """Test that 'commentary' in title is detected."""
        track = make_audio_track(0, title="Audio Commentary")
        assert _is_commentary_track(track) is True

    def test_director_in_title(self):
        """Test that 'director' in title is detected."""
        track = make_audio_track(0, title="Director's Commentary")
        assert _is_commentary_track(track) is True

    def test_no_title(self):
        """Test that tracks without title are not commentary."""
        track = make_audio_track(0, title=None)
        assert _is_commentary_track(track) is False

    def test_normal_title(self):
        """Test that normal titles are not commentary."""
        track = make_audio_track(0, title="TrueHD 7.1")
        assert _is_commentary_track(track) is False


class TestSelectSourceTrack:
    """Tests for select_source_track function."""

    def test_selects_best_match(self):
        """Test that highest scoring track is selected."""
        tracks = [
            make_audio_track(0, language="jpn", channels=2),
            make_audio_track(1, language="eng", channels=8),
            make_audio_track(2, language="eng", channels=2),
        ]
        prefs = SourcePreferences(
            prefer=(
                PreferenceCriterion(language="eng"),
                PreferenceCriterion(channels=ChannelPreference.MAX),
            )
        )

        result = select_source_track(tracks, prefs)

        assert result is not None
        assert result.track_index == 1  # eng with 8 channels
        assert result.is_fallback is False

    def test_fallback_to_first(self):
        """Test fallback to first track when no criteria match."""
        tracks = [
            make_audio_track(0, language="fra"),
            make_audio_track(1, language="deu"),
        ]
        prefs = SourcePreferences(prefer=(PreferenceCriterion(language="jpn"),))

        result = select_source_track(tracks, prefs)

        assert result is not None
        assert result.track_index == 0
        assert result.is_fallback is True

    def test_empty_tracks_returns_none(self):
        """Test that empty track list returns None."""
        prefs = SourcePreferences(prefer=(PreferenceCriterion(language="eng"),))

        result = select_source_track([], prefs)

        assert result is None

    def test_prefers_non_commentary(self):
        """Test that non-commentary tracks are preferred."""
        tracks = [
            make_audio_track(0, language="eng", title="Commentary"),
            make_audio_track(1, language="eng", title="Main Audio"),
        ]
        prefs = SourcePreferences(
            prefer=(
                PreferenceCriterion(language="eng"),
                PreferenceCriterion(not_commentary=True),
            )
        )

        result = select_source_track(tracks, prefs)

        assert result is not None
        assert result.track_index == 1


class TestFilterAudioTracks:
    """Tests for filter_audio_tracks function."""

    def test_filters_to_audio_only(self):
        """Test that only audio tracks are returned."""
        tracks = [
            TrackInfo(
                track_type="video",
                index=0,
                codec="hevc",
            ),
            TrackInfo(
                track_type="audio",
                index=1,
                codec="truehd",
            ),
            TrackInfo(
                track_type="subtitle",
                index=2,
                codec="subrip",
            ),
            TrackInfo(
                track_type="audio",
                index=3,
                codec="aac",
            ),
        ]

        result = filter_audio_tracks(tracks)

        assert len(result) == 2
        assert all(t.track_type == "audio" for t in result)
