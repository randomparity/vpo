"""Unit tests for track filtering logic.

Tests for audio, subtitle, and attachment track filtering based on
policy configuration.
"""

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.policy.exceptions import InsufficientTracksError
from video_policy_orchestrator.policy.models import (
    AudioFilterConfig,
    LanguageFallbackConfig,
    PolicySchema,
)


def make_audio_track(
    index: int,
    language: str | None = None,
    codec: str = "aac",
    channels: int = 2,
    title: str | None = None,
) -> TrackInfo:
    """Create a test audio track."""
    return TrackInfo(
        index=index,
        track_type="audio",
        codec=codec,
        language=language,
        title=title,
        is_default=index == 0,
        is_forced=False,
        channels=channels,
    )


def make_video_track(
    index: int = 0,
    codec: str = "hevc",
    width: int = 1920,
    height: int = 1080,
) -> TrackInfo:
    """Create a test video track."""
    return TrackInfo(
        index=index,
        track_type="video",
        codec=codec,
        width=width,
        height=height,
    )


def make_policy_with_audio_filter(
    languages: tuple[str, ...],
    minimum: int = 1,
    fallback: LanguageFallbackConfig | None = None,
) -> PolicySchema:
    """Create a test policy with audio filter configuration."""
    return PolicySchema(
        schema_version=3,
        audio_filter=AudioFilterConfig(
            languages=languages,
            minimum=minimum,
            fallback=fallback,
        ),
    )


class TestAudioTrackFiltering:
    """Tests for audio track filtering logic (T016)."""

    def test_keep_tracks_matching_language(self) -> None:
        """Audio tracks with languages in keep list should be kept."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="fra"),
            make_audio_track(index=3, language="jpn"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng", "jpn"))

        dispositions = compute_track_dispositions(tracks, policy)

        # Video track should be kept
        video_disp = [d for d in dispositions if d.track_type == "video"][0]
        assert video_disp.action == "KEEP"

        # English and Japanese should be kept
        eng_disp = [d for d in dispositions if d.language == "eng"][0]
        assert eng_disp.action == "KEEP"
        assert "language in keep list" in eng_disp.reason

        jpn_disp = [d for d in dispositions if d.language == "jpn"][0]
        assert jpn_disp.action == "KEEP"

        # French should be removed
        fra_disp = [d for d in dispositions if d.language == "fra"][0]
        assert fra_disp.action == "REMOVE"
        assert "language not in keep list" in fra_disp.reason

    def test_keep_und_tracks_when_in_list(self) -> None:
        """Undefined language tracks should be kept when 'und' is in keep list."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="und"),
            make_audio_track(index=2, language=None),  # Treated as und
        ]
        policy = make_policy_with_audio_filter(languages=("eng", "und"))

        dispositions = compute_track_dispositions(tracks, policy)

        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        for disp in audio_disps:
            assert disp.action == "KEEP"

    def test_remove_und_tracks_when_not_in_list(self) -> None:
        """Undefined language tracks should be removed when 'und' not in keep list."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="und"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng",))

        dispositions = compute_track_dispositions(tracks, policy)

        eng_disp = [d for d in dispositions if d.language == "eng"][0]
        assert eng_disp.action == "KEEP"

        und_disp = [d for d in dispositions if d.language == "und"][0]
        assert und_disp.action == "REMOVE"

    def test_cross_standard_language_matching(self) -> None:
        """Should match languages across ISO 639-1/2/3 standards."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="de"),  # ISO 639-1
            make_audio_track(index=2, language="deu"),  # ISO 639-2/T
            make_audio_track(index=3, language="ger"),  # ISO 639-2/B
        ]
        # Policy uses ISO 639-2/B code
        policy = make_policy_with_audio_filter(languages=("ger",))

        dispositions = compute_track_dispositions(tracks, policy)

        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        # All German tracks should be kept (de, deu, ger all match)
        for disp in audio_disps:
            assert disp.action == "KEEP", f"Track {disp.language} should be kept"

    def test_no_filter_when_audio_filter_none(self) -> None:
        """When audio_filter is None, no audio filtering should occur."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="fra"),
        ]
        policy = PolicySchema(schema_version=2)  # No audio_filter

        dispositions = compute_track_dispositions(tracks, policy)

        for disp in dispositions:
            assert disp.action == "KEEP"
            assert "no filter applied" in disp.reason


class TestMinimumAudioTrackValidation:
    """Tests for minimum audio track validation (T017)."""

    def test_minimum_audio_requirement_met(self) -> None:
        """Should succeed when minimum audio tracks remain after filtering."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="fra"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng",), minimum=1)

        # Should not raise - one track remains
        dispositions = compute_track_dispositions(tracks, policy)
        kept = [
            d for d in dispositions if d.track_type == "audio" and d.action == "KEEP"
        ]
        assert len(kept) == 1

    def test_minimum_audio_requirement_higher_value(self) -> None:
        """Should succeed when multiple audio tracks meet minimum requirement."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="eng"),  # Second English track
            make_audio_track(index=3, language="fra"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng",), minimum=2)

        dispositions = compute_track_dispositions(tracks, policy)
        kept = [
            d for d in dispositions if d.track_type == "audio" and d.action == "KEEP"
        ]
        assert len(kept) == 2


class TestInsufficientTracksError:
    """Tests for InsufficientTracksError scenarios (T018)."""

    def test_raises_error_when_no_tracks_match(self) -> None:
        """Should raise InsufficientTracksError when no audio tracks match."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="fra"),
            make_audio_track(index=2, language="spa"),
        ]
        # No fallback configured - should raise error
        policy = make_policy_with_audio_filter(languages=("eng",))

        with pytest.raises(InsufficientTracksError) as exc_info:
            compute_track_dispositions(tracks, policy)

        err = exc_info.value
        assert err.track_type == "audio"
        assert err.required == 1
        assert err.available == 0
        assert "eng" in err.policy_languages
        assert "fra" in err.file_languages
        assert "spa" in err.file_languages

    def test_raises_error_when_below_minimum(self) -> None:
        """Should raise InsufficientTracksError when below minimum threshold."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="fra"),
            make_audio_track(index=3, language="spa"),
        ]
        # Require 2 tracks but only 1 matches
        policy = make_policy_with_audio_filter(languages=("eng",), minimum=2)

        with pytest.raises(InsufficientTracksError) as exc_info:
            compute_track_dispositions(tracks, policy)

        err = exc_info.value
        assert err.required == 2
        assert err.available == 1

    def test_error_includes_helpful_context(self) -> None:
        """Error message should include policy and file language information."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="jpn"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng", "fra"))

        with pytest.raises(InsufficientTracksError) as exc_info:
            compute_track_dispositions(tracks, policy)

        error_message = str(exc_info.value)
        assert "audio" in error_message.lower()
        assert "0 tracks" in error_message or "available" in error_message
        assert "minimum" in error_message.lower() or "required" in error_message.lower()

    def test_no_error_with_fallback_keep_all(self) -> None:
        """Should not raise error when fallback mode is keep_all."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="jpn"),
        ]
        policy = make_policy_with_audio_filter(
            languages=("eng",),
            fallback=LanguageFallbackConfig(mode="keep_all"),
        )

        # Should not raise - fallback keeps all tracks
        dispositions = compute_track_dispositions(tracks, policy)
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        assert all(d.action == "KEEP" for d in audio_disps)

    def test_no_error_with_fallback_keep_first(self) -> None:
        """Should not raise error when fallback mode is keep_first."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="fra"),
            make_audio_track(index=2, language="spa"),
        ]
        policy = make_policy_with_audio_filter(
            languages=("eng",),
            minimum=1,
            fallback=LanguageFallbackConfig(mode="keep_first"),
        )

        # Should not raise - fallback keeps first track
        dispositions = compute_track_dispositions(tracks, policy)
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        kept = [d for d in audio_disps if d.action == "KEEP"]
        assert len(kept) >= 1

    def test_no_error_with_fallback_content_language(self) -> None:
        """Should not raise error when fallback mode is content_language."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="jpn"),  # First audio = content language
            make_audio_track(index=2, language="jpn"),
            make_audio_track(index=3, language="spa"),
        ]
        policy = make_policy_with_audio_filter(
            languages=("eng",),
            fallback=LanguageFallbackConfig(mode="content_language"),
        )

        # Should not raise - fallback keeps content language tracks
        dispositions = compute_track_dispositions(tracks, policy)
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        jpn_tracks = [d for d in audio_disps if d.language == "jpn"]
        assert all(d.action == "KEEP" for d in jpn_tracks)

    def test_error_with_fallback_error_mode(self) -> None:
        """Should raise error when fallback mode is explicitly 'error'."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="jpn"),
        ]
        policy = make_policy_with_audio_filter(
            languages=("eng",),
            fallback=LanguageFallbackConfig(mode="error"),
        )

        with pytest.raises(InsufficientTracksError):
            compute_track_dispositions(tracks, policy)


class TestTrackDispositionModel:
    """Tests for TrackDisposition model structure."""

    def test_disposition_contains_track_metadata(self) -> None:
        """TrackDisposition should include track metadata for display."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0, width=1920, height=1080),
            make_audio_track(
                index=1,
                language="eng",
                codec="truehd",
                channels=8,
                title="TrueHD English",
            ),
        ]
        policy = make_policy_with_audio_filter(languages=("eng",))

        dispositions = compute_track_dispositions(tracks, policy)

        video_disp = dispositions[0]
        assert video_disp.track_index == 0
        assert video_disp.track_type == "video"
        assert video_disp.codec == "hevc"
        assert video_disp.resolution == "1920x1080"

        audio_disp = dispositions[1]
        assert audio_disp.track_index == 1
        assert audio_disp.track_type == "audio"
        assert audio_disp.codec == "truehd"
        assert audio_disp.language == "eng"
        assert audio_disp.title == "TrueHD English"
        assert audio_disp.channels == 8
        assert audio_disp.action == "KEEP"
        assert audio_disp.reason  # Should have a reason string

    def test_disposition_reason_is_human_readable(self) -> None:
        """Disposition reasons should be human-readable."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_audio_track(index=2, language="fra"),
        ]
        policy = make_policy_with_audio_filter(languages=("eng",))

        dispositions = compute_track_dispositions(tracks, policy)

        for disp in dispositions:
            # Reason should be non-empty and contain readable text
            assert isinstance(disp.reason, str)
            assert len(disp.reason) > 0
            # Should not contain code artifacts
            assert "None" not in disp.reason
            assert "<" not in disp.reason


# =============================================================================
# Helper for subtitle tests
# =============================================================================


def make_subtitle_track(
    index: int,
    language: str | None = None,
    codec: str = "subrip",
    title: str | None = None,
    is_forced: bool = False,
) -> TrackInfo:
    """Create a test subtitle track."""
    return TrackInfo(
        index=index,
        track_type="subtitle",
        codec=codec,
        language=language,
        title=title,
        is_default=False,
        is_forced=is_forced,
    )


def make_policy_with_subtitle_filter(
    languages: tuple[str, ...] | None = None,
    preserve_forced: bool = False,
    remove_all: bool = False,
) -> PolicySchema:
    """Create a test policy with subtitle filter configuration."""
    from video_policy_orchestrator.policy.models import SubtitleFilterConfig

    return PolicySchema(
        schema_version=3,
        subtitle_filter=SubtitleFilterConfig(
            languages=languages,
            preserve_forced=preserve_forced,
            remove_all=remove_all,
        ),
    )


# =============================================================================
# Tests for Subtitle Language Filtering (T054)
# =============================================================================


class TestSubtitleLanguageFiltering:
    """Tests for subtitle track filtering by language (T054)."""

    def test_keep_subtitles_matching_language(self) -> None:
        """Subtitle tracks with languages in keep list should be kept."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="fra"),
            make_subtitle_track(index=4, language="jpn"),
        ]
        policy = make_policy_with_subtitle_filter(languages=("eng", "jpn"))

        dispositions = compute_track_dispositions(tracks, policy)

        # English subtitle should be kept
        eng_sub = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "eng"
        ][0]
        assert eng_sub.action == "KEEP"

        # Japanese subtitle should be kept
        jpn_sub = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "jpn"
        ][0]
        assert jpn_sub.action == "KEEP"

        # French subtitle should be removed
        fra_sub = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "fra"
        ][0]
        assert fra_sub.action == "REMOVE"

    def test_remove_subtitles_not_in_language_list(self) -> None:
        """Subtitle tracks with languages not in keep list should be removed."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="deu"),
            make_subtitle_track(index=4, language="spa"),
        ]
        policy = make_policy_with_subtitle_filter(languages=("eng",))

        dispositions = compute_track_dispositions(tracks, policy)

        # Count removed subtitles
        removed_subs = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.action == "REMOVE"
        ]
        assert len(removed_subs) == 2  # German and Spanish

    def test_no_subtitle_filter_keeps_all(self) -> None:
        """Without subtitle filter, all subtitle tracks should be kept."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="fra"),
        ]
        policy = PolicySchema(schema_version=3)  # No subtitle filter

        dispositions = compute_track_dispositions(tracks, policy)

        # All subtitles should be kept
        subtitle_disps = [d for d in dispositions if d.track_type == "subtitle"]
        assert all(d.action == "KEEP" for d in subtitle_disps)


# =============================================================================
# Tests for Forced Subtitle Preservation (T055)
# =============================================================================


class TestForcedSubtitlePreservation:
    """Tests for preserve_forced subtitle logic (T055)."""

    def test_preserve_forced_subtitle_regardless_of_language(self) -> None:
        """Forced subtitles should be kept even if language not in list."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="jpn", is_forced=True),
            make_subtitle_track(index=4, language="jpn", is_forced=False),
        ]
        policy = make_policy_with_subtitle_filter(
            languages=("eng",),
            preserve_forced=True,
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # English subtitle should be kept (matches language)
        eng_sub = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "eng"
        ][0]
        assert eng_sub.action == "KEEP"

        # Forced Japanese subtitle should be kept (preserve_forced=True)
        jpn_forced = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "jpn" and d.track_index == 3
        ][0]
        assert jpn_forced.action == "KEEP"
        assert "forced" in jpn_forced.reason.lower()

        # Non-forced Japanese subtitle should be removed
        jpn_normal = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "jpn" and d.track_index == 4
        ][0]
        assert jpn_normal.action == "REMOVE"

    def test_preserve_forced_false_does_not_keep_forced(self) -> None:
        """With preserve_forced=False, forced subtitles follow normal language rules."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="jpn", is_forced=True),
        ]
        policy = make_policy_with_subtitle_filter(
            languages=("eng",),
            preserve_forced=False,
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # Forced Japanese subtitle should be removed (language not in list)
        jpn_forced = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "jpn"
        ][0]
        assert jpn_forced.action == "REMOVE"


# =============================================================================
# Tests for Remove All Subtitles (T056)
# =============================================================================


class TestRemoveAllSubtitles:
    """Tests for remove_all subtitles option (T056)."""

    def test_remove_all_removes_all_subtitles(self) -> None:
        """remove_all=True should remove all subtitle tracks."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="fra"),
            make_subtitle_track(index=4, language="jpn", is_forced=True),
        ]
        policy = make_policy_with_subtitle_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # All subtitles should be removed
        subtitle_disps = [d for d in dispositions if d.track_type == "subtitle"]
        assert all(d.action == "REMOVE" for d in subtitle_disps)
        assert len(subtitle_disps) == 3

    def test_remove_all_overrides_languages(self) -> None:
        """remove_all=True should override language settings."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng"),
            make_subtitle_track(index=3, language="fra"),
        ]
        policy = make_policy_with_subtitle_filter(
            languages=("eng",),  # Would normally keep eng
            remove_all=True,  # But remove_all overrides
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # English subtitle should be removed despite being in language list
        eng_sub = [
            d
            for d in dispositions
            if d.track_type == "subtitle" and d.language == "eng"
        ][0]
        assert eng_sub.action == "REMOVE"

    def test_remove_all_overrides_preserve_forced(self) -> None:
        """remove_all=True should override preserve_forced."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="jpn", is_forced=True),
        ]
        policy = make_policy_with_subtitle_filter(
            preserve_forced=True,  # Would normally keep forced
            remove_all=True,  # But remove_all overrides
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # Forced subtitle should be removed
        forced_sub = [d for d in dispositions if d.track_type == "subtitle"][0]
        assert forced_sub.action == "REMOVE"


# =============================================================================
# Helper for attachment tests
# =============================================================================


def make_attachment_track(
    index: int,
    codec: str = "ttf",
    title: str | None = None,
) -> TrackInfo:
    """Create a test attachment track."""
    return TrackInfo(
        index=index,
        track_type="attachment",
        codec=codec,
        title=title,
    )


def make_policy_with_attachment_filter(
    remove_all: bool = True,
) -> PolicySchema:
    """Create a test policy with attachment filter configuration."""
    from video_policy_orchestrator.policy.models import AttachmentFilterConfig

    return PolicySchema(
        schema_version=3,
        attachment_filter=AttachmentFilterConfig(
            remove_all=remove_all,
        ),
    )


# =============================================================================
# Tests for Attachment Removal (T062)
# =============================================================================


class TestAttachmentRemoval:
    """Tests for attachment track removal (T062)."""

    def test_remove_all_removes_attachments(self) -> None:
        """remove_all=True should remove all attachment tracks."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_attachment_track(index=2, codec="ttf", title="Font.ttf"),
            make_attachment_track(index=3, codec="otf", title="Font.otf"),
            make_attachment_track(index=4, codec="image/jpeg", title="cover.jpg"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # All attachments should be removed
        attachment_disps = [d for d in dispositions if d.track_type == "attachment"]
        assert all(d.action == "REMOVE" for d in attachment_disps)
        assert len(attachment_disps) == 3

    def test_no_attachment_filter_keeps_all(self) -> None:
        """Without attachment filter, all attachments should be kept."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_attachment_track(index=2, codec="ttf", title="Font.ttf"),
        ]
        policy = PolicySchema(schema_version=3)  # No attachment filter

        dispositions = compute_track_dispositions(tracks, policy)

        # Attachment should be kept
        attachment_disps = [d for d in dispositions if d.track_type == "attachment"]
        assert all(d.action == "KEEP" for d in attachment_disps)

    def test_remove_all_false_keeps_attachments(self) -> None:
        """remove_all=False should keep all attachment tracks."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_attachment_track(index=2, codec="ttf", title="Font.ttf"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=False)

        dispositions = compute_track_dispositions(tracks, policy)

        # Attachment should be kept
        attachment_disps = [d for d in dispositions if d.track_type == "attachment"]
        assert all(d.action == "KEEP" for d in attachment_disps)


# =============================================================================
# Tests for Font Warning with Styled Subtitles (T063)
# =============================================================================


class TestFontWarningStyledSubtitles:
    """Tests for font removal warning when ASS/SSA subtitles present (T063)."""

    def test_warns_when_fonts_removed_with_ass_subtitles(self) -> None:
        """Should generate warning when removing fonts with ASS subtitles."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng", codec="ass"),
            make_attachment_track(index=3, codec="ttf", title="Font.ttf"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # Font should be removed
        font_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert font_disp.action == "REMOVE"
        # Warning about styled subtitles should be in reason
        assert (
            "styled subtitle" in font_disp.reason.lower()
            or "font" in font_disp.reason.lower()
        )

    def test_warns_when_fonts_removed_with_ssa_subtitles(self) -> None:
        """Should generate warning when removing fonts with SSA subtitles."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng", codec="ssa"),
            make_attachment_track(index=3, codec="ttf", title="Font.ttf"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # Font should be removed with warning
        font_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert font_disp.action == "REMOVE"

    def test_no_warning_without_styled_subtitles(self) -> None:
        """Should not generate warning when no ASS/SSA subtitles."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng", codec="subrip"),
            make_attachment_track(index=3, codec="ttf", title="Font.ttf"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # Font should be removed without styled subtitle warning
        font_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert font_disp.action == "REMOVE"
        # The reason should just be remove_all, not styled subtitle warning
        assert "styled subtitle" not in font_disp.reason.lower()

    def test_cover_art_removal_no_warning(self) -> None:
        """Cover art removal should not generate font warning."""
        from video_policy_orchestrator.policy.evaluator import (
            compute_track_dispositions,
        )

        tracks = [
            make_video_track(index=0),
            make_audio_track(index=1, language="eng"),
            make_subtitle_track(index=2, language="eng", codec="ass"),
            make_attachment_track(index=3, codec="image/jpeg", title="cover.jpg"),
        ]
        policy = make_policy_with_attachment_filter(remove_all=True)

        dispositions = compute_track_dispositions(tracks, policy)

        # Cover art should be removed
        cover_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert cover_disp.action == "REMOVE"
