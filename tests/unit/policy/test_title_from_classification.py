"""Unit tests for compute_title_updates and _is_generic_title."""

import pytest

from vpo.db import TrackRecord, TranscriptionResultRecord
from vpo.policy.evaluator.transcription import (
    CLASSIFICATION_TITLES,
    _is_generic_title,
    compute_title_updates,
)
from vpo.policy.types import (
    EvaluationPolicy,
    TranscriptionPolicyOptions,
)

# =============================================================================
# _is_generic_title Tests
# =============================================================================


class TestIsGenericTitle:
    """Tests for _is_generic_title helper."""

    def test_none_is_generic(self):
        assert _is_generic_title(None) is True

    def test_empty_string_is_generic(self):
        assert _is_generic_title("") is True

    def test_whitespace_only_is_generic(self):
        assert _is_generic_title("   ") is True

    def test_stereo_is_generic(self):
        assert _is_generic_title("Stereo") is True

    def test_5_1_is_generic(self):
        assert _is_generic_title("5.1") is True

    def test_aac_stereo_is_generic(self):
        assert _is_generic_title("AAC Stereo") is True

    def test_codec_name_is_generic(self):
        assert _is_generic_title("DTS") is True

    def test_pcm_s16le_is_generic(self):
        assert _is_generic_title("pcm_s16le") is True

    def test_truehd_7_1_is_generic(self):
        assert _is_generic_title("TrueHD 7.1") is True

    def test_descriptive_title_not_generic(self):
        assert _is_generic_title("Director's Commentary") is False

    def test_custom_title_not_generic(self):
        assert _is_generic_title("English Audio") is False

    def test_classification_title_not_generic(self):
        """Previously set classification titles are not generic."""
        assert _is_generic_title("Commentary") is False
        assert _is_generic_title("Main") is False

    def test_mixed_generic_and_non_generic_tokens(self):
        """A mix of generic and non-generic tokens is not generic."""
        assert _is_generic_title("English Stereo") is False


# =============================================================================
# compute_title_updates Tests
# =============================================================================


class TestComputeTitleUpdates:
    """Tests for compute_title_updates function."""

    @pytest.fixture
    def audio_track(self):
        """Audio track with generic title."""
        return TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="pcm_s16le",
            track_index=1,
            language="eng",
            title="Stereo",
            is_default=False,
            is_forced=False,
        )

    @pytest.fixture
    def audio_track_no_title(self):
        """Audio track with no title."""
        return TrackRecord(
            id=2,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=2,
            language="eng",
            title=None,
            is_default=False,
            is_forced=False,
        )

    @pytest.fixture
    def policy_enabled(self):
        """Policy with title updates enabled."""
        return EvaluationPolicy(
            transcription=TranscriptionPolicyOptions(
                enabled=True,
                update_title_from_classification=True,
                confidence_threshold=0.8,
            ),
        )

    @pytest.fixture
    def policy_disabled(self):
        """Policy with title updates disabled."""
        return EvaluationPolicy(
            transcription=TranscriptionPolicyOptions(
                enabled=True,
                update_title_from_classification=False,
            ),
        )

    def _make_transcription_result(
        self, track_id: int, track_type: str, confidence: float = 0.95
    ) -> TranscriptionResultRecord:
        return TranscriptionResultRecord(
            id=track_id,
            track_id=track_id,
            detected_language="eng",
            confidence_score=confidence,
            track_type=track_type,
            transcript_sample=None,
            plugin_name="whisper-local",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

    def test_generates_title_for_main(self, audio_track, policy_enabled):
        """Main classification sets title 'Main'."""
        results = {audio_track.id: self._make_transcription_result(1, "main")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Main"

    def test_generates_title_for_commentary(self, audio_track, policy_enabled):
        """Commentary classification sets title 'Commentary'."""
        results = {audio_track.id: self._make_transcription_result(1, "commentary")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Commentary"

    def test_generates_title_for_music(self, audio_track, policy_enabled):
        """Music classification sets title 'Music'."""
        results = {audio_track.id: self._make_transcription_result(1, "music")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Music"

    def test_generates_title_for_sfx(self, audio_track, policy_enabled):
        """SFX classification sets title 'Sound Effects'."""
        results = {audio_track.id: self._make_transcription_result(1, "sfx")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Sound Effects"

    def test_generates_title_for_non_speech(self, audio_track, policy_enabled):
        """Non-speech classification sets title 'Non-Speech'."""
        results = {audio_track.id: self._make_transcription_result(1, "non_speech")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Non-Speech"

    def test_generates_title_for_alternate(self, audio_track, policy_enabled):
        """Alternate classification sets title 'Alternate'."""
        results = {audio_track.id: self._make_transcription_result(1, "alternate")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert updates[audio_track.track_index] == "Alternate"

    def test_all_classification_types_covered(self):
        """All known classification types have a title mapping."""
        expected_types = {
            "main",
            "commentary",
            "alternate",
            "music",
            "sfx",
            "non_speech",
        }
        assert set(CLASSIFICATION_TITLES.keys()) == expected_types

    def test_skips_when_disabled(self, audio_track, policy_disabled):
        """No updates when update_title_from_classification is False."""
        results = {audio_track.id: self._make_transcription_result(1, "main")}
        updates = compute_title_updates([audio_track], results, policy_disabled)
        assert len(updates) == 0

    def test_skips_when_no_transcription_settings(self, audio_track):
        """No updates when policy has no transcription settings."""
        policy = EvaluationPolicy()
        results = {audio_track.id: self._make_transcription_result(1, "main")}
        updates = compute_title_updates([audio_track], results, policy)
        assert len(updates) == 0

    def test_skips_below_confidence_threshold(self, audio_track, policy_enabled):
        """No updates when confidence is below threshold."""
        results = {
            audio_track.id: self._make_transcription_result(1, "main", confidence=0.5)
        }
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert len(updates) == 0

    def test_skips_non_audio_tracks(self, policy_enabled):
        """Does not process video tracks."""
        video_track = TrackRecord(
            id=1,
            file_id=100,
            track_type="video",
            codec="h264",
            track_index=0,
            language="und",
            title=None,
            is_default=True,
            is_forced=False,
        )
        results = {video_track.id: self._make_transcription_result(1, "main")}
        updates = compute_title_updates([video_track], results, policy_enabled)
        assert len(updates) == 0

    def test_skips_descriptive_titles(self, policy_enabled):
        """Does not overwrite descriptive (non-generic) titles."""
        track = TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=1,
            language="eng",
            title="Director's Commentary",
            is_default=False,
            is_forced=False,
        )
        results = {track.id: self._make_transcription_result(1, "commentary")}
        updates = compute_title_updates([track], results, policy_enabled)
        assert len(updates) == 0

    def test_handles_empty_tracks(self, policy_enabled):
        """Empty track list returns empty dict."""
        updates = compute_title_updates([], {}, policy_enabled)
        assert updates == {}

    def test_respects_custom_confidence_threshold(self, audio_track):
        """Custom confidence threshold is respected."""
        policy_low = EvaluationPolicy(
            transcription=TranscriptionPolicyOptions(
                enabled=True,
                update_title_from_classification=True,
                confidence_threshold=0.5,
            ),
        )
        results = {
            audio_track.id: self._make_transcription_result(1, "main", confidence=0.7)
        }
        updates = compute_title_updates([audio_track], results, policy_low)
        assert audio_track.track_index in updates

        policy_high = EvaluationPolicy(
            transcription=TranscriptionPolicyOptions(
                enabled=True,
                update_title_from_classification=True,
                confidence_threshold=0.8,
            ),
        )
        updates = compute_title_updates([audio_track], results, policy_high)
        assert len(updates) == 0

    def test_no_result_for_track(self, audio_track, policy_enabled):
        """Tracks without transcription results are skipped."""
        updates = compute_title_updates([audio_track], {}, policy_enabled)
        assert len(updates) == 0

    def test_unknown_track_type_skipped(self, audio_track, policy_enabled):
        """Unknown track_type (not in CLASSIFICATION_TITLES) is skipped."""
        results = {audio_track.id: self._make_transcription_result(1, "unknown_type")}
        updates = compute_title_updates([audio_track], results, policy_enabled)
        assert len(updates) == 0

    def test_idempotent_already_set(self, policy_enabled):
        """Track already titled 'Commentary' is not updated again."""
        track = TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=1,
            language="eng",
            title="Commentary",
            is_default=False,
            is_forced=False,
        )
        results = {track.id: self._make_transcription_result(1, "commentary")}
        updates = compute_title_updates([track], results, policy_enabled)
        assert len(updates) == 0

    def test_null_title_gets_updated(self, audio_track_no_title, policy_enabled):
        """Track with None title gets updated."""
        results = {audio_track_no_title.id: self._make_transcription_result(2, "main")}
        updates = compute_title_updates([audio_track_no_title], results, policy_enabled)
        assert updates[audio_track_no_title.track_index] == "Main"

    def test_multiple_tracks(self, policy_enabled):
        """Multiple tracks get independent title updates."""
        track1 = TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=1,
            language="eng",
            title="Stereo",
            is_default=True,
            is_forced=False,
        )
        track2 = TrackRecord(
            id=2,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=2,
            language="eng",
            title=None,
            is_default=False,
            is_forced=False,
        )
        results = {
            1: self._make_transcription_result(1, "main"),
            2: self._make_transcription_result(2, "commentary"),
        }
        updates = compute_title_updates([track1, track2], results, policy_enabled)
        assert updates[1] == "Main"
        assert updates[2] == "Commentary"
