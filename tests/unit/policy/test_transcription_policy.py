"""Unit tests for transcription policy options."""

import pytest

from video_policy_orchestrator.db.models import TrackRecord, TranscriptionResultRecord
from video_policy_orchestrator.policy.evaluator import compute_language_updates
from video_policy_orchestrator.policy.loader import (
    PolicyValidationError,
    load_policy_from_dict,
)
from video_policy_orchestrator.policy.models import (
    TranscriptionPolicyOptions,
)

# =============================================================================
# TranscriptionPolicyOptions Model Tests
# =============================================================================


class TestTranscriptionPolicyOptionsModel:
    """Tests for TranscriptionPolicyOptions dataclass."""

    def test_default_values(self):
        """Default values should be sensible."""
        options = TranscriptionPolicyOptions()
        assert options.enabled is False
        assert options.update_language_from_transcription is False
        assert options.confidence_threshold == 0.8
        assert options.detect_commentary is False
        assert options.reorder_commentary is False

    def test_custom_values(self):
        """Custom values should be accepted."""
        options = TranscriptionPolicyOptions(
            enabled=True,
            update_language_from_transcription=True,
            confidence_threshold=0.9,
            detect_commentary=True,
            reorder_commentary=True,
        )
        assert options.enabled is True
        assert options.update_language_from_transcription is True
        assert options.confidence_threshold == 0.9
        assert options.detect_commentary is True
        assert options.reorder_commentary is True

    def test_confidence_threshold_validation_low(self):
        """Confidence threshold below 0.0 should raise error."""
        with pytest.raises(ValueError, match="confidence_threshold"):
            TranscriptionPolicyOptions(confidence_threshold=-0.1)

    def test_confidence_threshold_validation_high(self):
        """Confidence threshold above 1.0 should raise error."""
        with pytest.raises(ValueError, match="confidence_threshold"):
            TranscriptionPolicyOptions(confidence_threshold=1.5)

    def test_confidence_threshold_boundaries(self):
        """Confidence threshold at boundaries (0.0, 1.0) should be valid."""
        options_zero = TranscriptionPolicyOptions(confidence_threshold=0.0)
        assert options_zero.confidence_threshold == 0.0

        options_one = TranscriptionPolicyOptions(confidence_threshold=1.0)
        assert options_one.confidence_threshold == 1.0

    def test_reorder_requires_detect(self):
        """reorder_commentary=True requires detect_commentary=True."""
        with pytest.raises(ValueError, match="reorder_commentary requires"):
            TranscriptionPolicyOptions(
                detect_commentary=False,
                reorder_commentary=True,
            )

    def test_reorder_with_detect_valid(self):
        """reorder_commentary=True with detect_commentary=True is valid."""
        options = TranscriptionPolicyOptions(
            detect_commentary=True,
            reorder_commentary=True,
        )
        assert options.detect_commentary is True
        assert options.reorder_commentary is True


# =============================================================================
# Policy Loader Tests for Transcription
# =============================================================================


class TestTranscriptionPolicyLoading:
    """Tests for loading transcription policy options from dict."""

    def test_load_policy_with_transcription(self):
        """Loading policy with transcription options should work."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                    "update_language_from_transcription": True,
                    "confidence_threshold": 0.85,
                    "detect_commentary": True,
                    "reorder_commentary": True,
                },
            }
        )
        assert policy.transcription is not None
        assert policy.transcription.enabled is True
        assert policy.transcription.update_language_from_transcription is True
        assert policy.transcription.confidence_threshold == 0.85
        assert policy.transcription.detect_commentary is True
        assert policy.transcription.reorder_commentary is True

    def test_load_policy_without_transcription(self):
        """Loading policy without transcription options should work."""
        policy = load_policy_from_dict({"schema_version": 12})
        assert policy.transcription is None

    def test_load_policy_partial_transcription(self):
        """Partial transcription options should use defaults."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                },
            }
        )
        assert policy.transcription is not None
        assert policy.transcription.enabled is True
        # Defaults
        assert policy.transcription.update_language_from_transcription is False
        assert policy.transcription.confidence_threshold == 0.8
        assert policy.transcription.detect_commentary is False
        assert policy.transcription.reorder_commentary is False

    def test_load_policy_invalid_confidence_threshold(self):
        """Invalid confidence_threshold should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 12,
                    "transcription": {
                        "confidence_threshold": 1.5,
                    },
                }
            )

    def test_load_policy_invalid_transcription_field(self):
        """Extra field in transcription should raise error."""
        with pytest.raises(PolicyValidationError):
            load_policy_from_dict(
                {
                    "schema_version": 12,
                    "transcription": {
                        "enabled": True,
                        "invalid_field": "value",
                    },
                }
            )

    def test_has_transcription_settings_property(self):
        """has_transcription_settings should return True when enabled."""
        policy_disabled = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {"enabled": False},
            }
        )
        assert policy_disabled.has_transcription_settings is False

        policy_enabled = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {"enabled": True},
            }
        )
        assert policy_enabled.has_transcription_settings is True

        policy_none = load_policy_from_dict({"schema_version": 12})
        assert policy_none.has_transcription_settings is False


# =============================================================================
# Language Update Computation Tests
# =============================================================================


class TestComputeLanguageUpdates:
    """Tests for compute_language_updates function."""

    @pytest.fixture
    def audio_track(self):
        """Create a sample audio track."""
        return TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=1,
            language="und",
            title=None,
            is_default=False,
            is_forced=False,
        )

    @pytest.fixture
    def transcription_result(self):
        """Create a sample transcription result."""
        return TranscriptionResultRecord(
            id=1,
            track_id=1,
            detected_language="eng",
            confidence_score=0.95,
            track_type="main",
            transcript_sample=None,
            plugin_name="whisper-local",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

    @pytest.fixture
    def policy_enabled(self):
        """Create a policy with transcription enabled."""
        return load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                    "update_language_from_transcription": True,
                    "confidence_threshold": 0.8,
                },
            }
        )

    @pytest.fixture
    def policy_disabled(self):
        """Create a policy with transcription disabled."""
        return load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": False,
                },
            }
        )

    def test_compute_updates_when_enabled(
        self, audio_track, transcription_result, policy_enabled
    ):
        """Should compute updates when transcription is enabled."""
        results = {audio_track.id: transcription_result}
        updates = compute_language_updates([audio_track], results, policy_enabled)

        assert audio_track.track_index in updates
        assert updates[audio_track.track_index] == "eng"

    def test_no_updates_when_disabled(
        self, audio_track, transcription_result, policy_disabled
    ):
        """Should return no updates when transcription is disabled."""
        results = {audio_track.id: transcription_result}
        updates = compute_language_updates([audio_track], results, policy_disabled)

        assert len(updates) == 0

    def test_no_updates_when_language_matches(
        self, transcription_result, policy_enabled
    ):
        """Should not update when current language matches detected."""
        track = TrackRecord(
            id=1,
            file_id=100,
            track_type="audio",
            codec="aac",
            track_index=1,
            language="eng",  # Already matches
            title=None,
            is_default=False,
            is_forced=False,
        )
        results = {track.id: transcription_result}
        updates = compute_language_updates([track], results, policy_enabled)

        assert len(updates) == 0

    def test_no_updates_below_threshold(self, audio_track, policy_enabled):
        """Should not update when confidence is below threshold."""
        low_confidence_result = TranscriptionResultRecord(
            id=1,
            track_id=1,
            detected_language="eng",
            confidence_score=0.5,  # Below 0.8 threshold
            track_type="main",
            transcript_sample=None,
            plugin_name="whisper-local",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        results = {audio_track.id: low_confidence_result}
        updates = compute_language_updates([audio_track], results, policy_enabled)

        assert len(updates) == 0

    def test_no_updates_for_video_tracks(self, transcription_result, policy_enabled):
        """Should not process video tracks."""
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
        results = {video_track.id: transcription_result}
        updates = compute_language_updates([video_track], results, policy_enabled)

        assert len(updates) == 0

    def test_no_updates_when_no_transcription_result(self, audio_track, policy_enabled):
        """Should not update tracks without transcription results."""
        updates = compute_language_updates([audio_track], {}, policy_enabled)
        assert len(updates) == 0

    def test_no_updates_when_update_language_disabled(
        self, audio_track, transcription_result
    ):
        """Should not update when update_language_from_transcription is False."""
        policy = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                    "update_language_from_transcription": False,  # Disabled
                },
            }
        )
        results = {audio_track.id: transcription_result}
        updates = compute_language_updates([audio_track], results, policy)

        assert len(updates) == 0

    def test_custom_confidence_threshold(self, audio_track):
        """Should respect custom confidence threshold."""
        result = TranscriptionResultRecord(
            id=1,
            track_id=1,
            detected_language="eng",
            confidence_score=0.7,  # Between 0.5 and 0.8
            track_type="main",
            transcript_sample=None,
            plugin_name="whisper-local",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )

        # With 0.5 threshold, should update
        policy_low = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                    "update_language_from_transcription": True,
                    "confidence_threshold": 0.5,
                },
            }
        )
        results = {audio_track.id: result}
        updates = compute_language_updates([audio_track], results, policy_low)
        assert audio_track.track_index in updates

        # With 0.8 threshold, should not update
        policy_high = load_policy_from_dict(
            {
                "schema_version": 12,
                "transcription": {
                    "enabled": True,
                    "update_language_from_transcription": True,
                    "confidence_threshold": 0.8,
                },
            }
        )
        updates = compute_language_updates([audio_track], results, policy_high)
        assert len(updates) == 0

    def test_no_policy_transcription_settings(self, audio_track, transcription_result):
        """Should return empty when policy has no transcription settings."""
        policy = load_policy_from_dict({"schema_version": 12})
        results = {audio_track.id: transcription_result}
        updates = compute_language_updates([audio_track], results, policy)

        assert len(updates) == 0

    def test_no_detected_language_skipped(self, audio_track, policy_enabled):
        """Should skip tracks where detected_language is None."""
        result = TranscriptionResultRecord(
            id=1,
            track_id=1,
            detected_language=None,  # No language detected
            confidence_score=0.95,
            track_type="main",
            transcript_sample=None,
            plugin_name="whisper-local",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        results = {audio_track.id: result}
        updates = compute_language_updates([audio_track], results, policy_enabled)

        assert len(updates) == 0
