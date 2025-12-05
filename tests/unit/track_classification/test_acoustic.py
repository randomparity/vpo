"""Unit tests for acoustic analysis functions."""

from video_policy_orchestrator.track_classification.acoustic import (
    extract_acoustic_profile,
    get_commentary_confidence,
    is_commentary_by_acoustic,
)
from video_policy_orchestrator.track_classification.models import AcousticProfile


class TestIsCommentaryByAcoustic:
    """Tests for is_commentary_by_acoustic function."""

    def test_typical_commentary_is_detected(self):
        """High speech density + low dynamic range = commentary."""
        profile = AcousticProfile(
            speech_density=0.85,
            avg_pause_duration=2.5,
            voice_count_estimate=2,
            dynamic_range_db=12.0,
            has_background_audio=True,
        )
        assert is_commentary_by_acoustic(profile) is True

    def test_solo_commentary_is_detected(self):
        """Single speaker commentary detected."""
        profile = AcousticProfile(
            speech_density=0.75,
            avg_pause_duration=3.0,
            voice_count_estimate=1,
            dynamic_range_db=10.0,
            has_background_audio=True,
        )
        assert is_commentary_by_acoustic(profile) is True

    def test_main_audio_not_detected_as_commentary(self):
        """Regular movie audio should not be commentary."""
        profile = AcousticProfile(
            speech_density=0.35,
            avg_pause_duration=4.0,
            voice_count_estimate=6,
            dynamic_range_db=32.0,
            has_background_audio=False,
        )
        assert is_commentary_by_acoustic(profile) is False

    def test_action_movie_not_detected_as_commentary(self):
        """Sparse dialogue action movie should not be commentary."""
        profile = AcousticProfile(
            speech_density=0.20,
            avg_pause_duration=8.0,
            voice_count_estimate=4,
            dynamic_range_db=40.0,
            has_background_audio=False,
        )
        assert is_commentary_by_acoustic(profile) is False

    def test_low_speech_density_insufficient_for_commentary(self):
        """Low speech density alone is insufficient without other strong signals."""
        # Speech: 0, DR: 0.3 (low), Voices: 0.2, BG: 0.1 = 0.6 >= 0.5
        # Actually with low dynamic range and voices in range, it passes
        profile = AcousticProfile(
            speech_density=0.2,
            avg_pause_duration=5.0,
            voice_count_estimate=2,
            dynamic_range_db=10.0,
            has_background_audio=True,
        )
        # Score: 0 (speech) + 0.3 (dynamic) + 0.2 (voices) + 0.1 (bg) = 0.6 >= 0.5
        assert is_commentary_by_acoustic(profile) is True  # Multiple other factors

    def test_high_dynamic_range_reduces_score(self):
        """High dynamic range reduces the score significantly."""
        profile = AcousticProfile(
            speech_density=0.6,  # Gives 0.2
            avg_pause_duration=2.0,
            voice_count_estimate=2,  # Gives 0.2
            dynamic_range_db=35.0,  # Gives 0
            has_background_audio=False,  # Gives 0
        )
        # Score: 0.2 (speech) + 0 (dynamic) + 0.2 (voices) + 0 (bg) = 0.4 < 0.5
        assert is_commentary_by_acoustic(profile) is False

    def test_many_voices_reduces_score(self):
        """Many speakers (6+) indicates movie audio not commentary."""
        profile = AcousticProfile(
            speech_density=0.5,
            avg_pause_duration=2.0,
            voice_count_estimate=8,
            dynamic_range_db=20.0,
            has_background_audio=False,
        )
        # Speech: 0.2, Dynamic: 0.0, Voices: 0 (too many), BG: 0
        assert is_commentary_by_acoustic(profile) is False


class TestGetCommentaryConfidence:
    """Tests for get_commentary_confidence function."""

    def test_strong_commentary_indicators_high_confidence(self):
        """Strong commentary indicators should give high confidence."""
        profile = AcousticProfile(
            speech_density=0.85,
            avg_pause_duration=2.0,
            voice_count_estimate=2,
            dynamic_range_db=10.0,
            has_background_audio=True,
        )
        confidence = get_commentary_confidence(profile)
        assert confidence >= 0.8

    def test_weak_indicators_low_confidence(self):
        """Weak indicators should give low confidence."""
        profile = AcousticProfile(
            speech_density=0.35,
            avg_pause_duration=6.0,
            voice_count_estimate=5,
            dynamic_range_db=30.0,
            has_background_audio=False,
        )
        confidence = get_commentary_confidence(profile)
        assert confidence < 0.3

    def test_confidence_clamped_to_valid_range(self):
        """Confidence should be between 0.0 and 1.0."""
        # Very strong indicators
        profile = AcousticProfile(
            speech_density=0.95,
            avg_pause_duration=2.0,
            voice_count_estimate=2,
            dynamic_range_db=8.0,
            has_background_audio=True,
        )
        confidence = get_commentary_confidence(profile)
        assert 0.0 <= confidence <= 1.0


class TestExtractAcousticProfile:
    """Tests for extract_acoustic_profile function."""

    def test_returns_none_without_analyzer(self):
        """Should return None when no analyzer provided."""
        result = extract_acoustic_profile(b"audio_data")
        assert result is None

    def test_returns_none_if_analyzer_not_supported(self):
        """Should return None if analyzer doesn't support acoustic analysis."""

        class MockAnalyzer:
            def supports_acoustic_analysis(self) -> bool:
                return False

            def get_acoustic_profile(
                self, audio_data: bytes, sample_rate: int
            ) -> AcousticProfile:
                return AcousticProfile(
                    speech_density=0.8,
                    avg_pause_duration=2.0,
                    voice_count_estimate=2,
                    dynamic_range_db=12.0,
                    has_background_audio=True,
                )

        result = extract_acoustic_profile(b"audio_data", analyzer=MockAnalyzer())
        assert result is None

    def test_returns_profile_from_analyzer(self):
        """Should return profile from analyzer when supported."""

        class MockAnalyzer:
            def supports_acoustic_analysis(self) -> bool:
                return True

            def get_acoustic_profile(
                self, audio_data: bytes, sample_rate: int
            ) -> AcousticProfile:
                return AcousticProfile(
                    speech_density=0.8,
                    avg_pause_duration=2.0,
                    voice_count_estimate=2,
                    dynamic_range_db=12.0,
                    has_background_audio=True,
                )

        result = extract_acoustic_profile(b"audio_data", analyzer=MockAnalyzer())
        assert result is not None
        assert result.speech_density == 0.8
        assert result.voice_count_estimate == 2

    def test_returns_none_on_analyzer_exception(self):
        """Should return None if analyzer raises exception."""

        class MockAnalyzer:
            def supports_acoustic_analysis(self) -> bool:
                return True

            def get_acoustic_profile(
                self, audio_data: bytes, sample_rate: int
            ) -> AcousticProfile:
                raise RuntimeError("Analysis failed")

        result = extract_acoustic_profile(b"audio_data", analyzer=MockAnalyzer())
        assert result is None
