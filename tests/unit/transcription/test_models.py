"""Unit tests for transcription models."""

from datetime import datetime, timezone

import pytest

from video_policy_orchestrator.transcription.models import (
    COMMENTARY_KEYWORDS,
    MUSIC_KEYWORDS,
    SFX_KEYWORDS,
    TrackClassification,
    TranscriptionConfig,
    TranscriptionResult,
    detect_track_classification,
    is_hallucination,
    is_music_by_metadata,
    is_sfx_by_metadata,
)


class TestTrackClassification:
    """Tests for TrackClassification enum."""

    def test_values(self):
        """Test enum values match expected strings."""
        assert TrackClassification.MAIN.value == "main"
        assert TrackClassification.COMMENTARY.value == "commentary"
        assert TrackClassification.ALTERNATE.value == "alternate"
        assert TrackClassification.MUSIC.value == "music"
        assert TrackClassification.SFX.value == "sfx"
        assert TrackClassification.NON_SPEECH.value == "non_speech"

    def test_from_string(self):
        """Test creating enum from string value."""
        assert TrackClassification("main") == TrackClassification.MAIN
        assert TrackClassification("commentary") == TrackClassification.COMMENTARY
        assert TrackClassification("alternate") == TrackClassification.ALTERNATE
        assert TrackClassification("music") == TrackClassification.MUSIC
        assert TrackClassification("sfx") == TrackClassification.SFX
        assert TrackClassification("non_speech") == TrackClassification.NON_SPEECH


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid transcription result."""
        now = datetime.now(timezone.utc)
        result = TranscriptionResult(
            track_id=1,
            detected_language="en",
            confidence_score=0.95,
            track_type=TrackClassification.MAIN,
            transcript_sample="Hello world...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )
        assert result.track_id == 1
        assert result.detected_language == "en"
        assert result.confidence_score == 0.95
        assert result.track_type == TrackClassification.MAIN
        assert result.transcript_sample == "Hello world..."
        assert result.plugin_name == "whisper-local"

    def test_none_language(self):
        """Test result with no detected language."""
        now = datetime.now(timezone.utc)
        result = TranscriptionResult(
            track_id=1,
            detected_language=None,
            confidence_score=0.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test-plugin",
            created_at=now,
            updated_at=now,
        )
        assert result.detected_language is None
        assert result.transcript_sample is None

    def test_confidence_score_validation_too_low(self):
        """Test that confidence score below 0 raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=-0.1,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )

    def test_confidence_score_validation_too_high(self):
        """Test that confidence score above 1 raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=1.5,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )

    def test_confidence_score_boundary_values(self):
        """Test boundary values for confidence score."""
        now = datetime.now(timezone.utc)
        # 0.0 should be valid
        result_zero = TranscriptionResult(
            track_id=1,
            detected_language=None,
            confidence_score=0.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test",
            created_at=now,
            updated_at=now,
        )
        assert result_zero.confidence_score == 0.0

        # 1.0 should be valid
        result_one = TranscriptionResult(
            track_id=2,
            detected_language="en",
            confidence_score=1.0,
            track_type=TrackClassification.MAIN,
            transcript_sample=None,
            plugin_name="test",
            created_at=now,
            updated_at=now,
        )
        assert result_one.confidence_score == 1.0

    def test_empty_plugin_name_raises_error(self):
        """Test that empty plugin name raises error."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="plugin_name must be non-empty"):
            TranscriptionResult(
                track_id=1,
                detected_language="en",
                confidence_score=0.5,
                track_type=TrackClassification.MAIN,
                transcript_sample=None,
                plugin_name="",
                created_at=now,
                updated_at=now,
            )

    def test_from_record(self):
        """Test creating domain model from database record."""
        from video_policy_orchestrator.db.models import TranscriptionResultRecord

        record = TranscriptionResultRecord(
            id=1,
            track_id=42,
            detected_language="fr",
            confidence_score=0.87,
            track_type="commentary",
            transcript_sample="Bonjour...",
            plugin_name="whisper-local",
            created_at="2025-01-15T10:30:00+00:00",
            updated_at="2025-01-15T10:30:00+00:00",
        )

        result = TranscriptionResult.from_record(record)

        assert result.track_id == 42
        assert result.detected_language == "fr"
        assert result.confidence_score == 0.87
        assert result.track_type == TrackClassification.COMMENTARY
        assert result.transcript_sample == "Bonjour..."
        assert result.plugin_name == "whisper-local"
        assert result.created_at == datetime(
            2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc
        )


class TestTranscriptionConfig:
    """Tests for TranscriptionConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = TranscriptionConfig()
        assert config.enabled_plugin is None
        assert config.model_size == "base"
        assert config.sample_duration == 30
        assert config.gpu_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TranscriptionConfig(
            enabled_plugin="whisper-local",
            model_size="small",
            sample_duration=120,
            gpu_enabled=False,
        )
        assert config.enabled_plugin == "whisper-local"
        assert config.model_size == "small"
        assert config.sample_duration == 120
        assert config.gpu_enabled is False

    def test_valid_model_sizes(self):
        """Test all valid model sizes."""
        for size in ["tiny", "base", "small", "medium", "large"]:
            config = TranscriptionConfig(model_size=size)
            assert config.model_size == size

    def test_invalid_model_size(self):
        """Test that invalid model size raises error."""
        with pytest.raises(ValueError, match="model_size must be one of"):
            TranscriptionConfig(model_size="invalid")

    def test_negative_sample_duration(self):
        """Test that negative sample duration raises error."""
        with pytest.raises(ValueError, match="sample_duration must be non-negative"):
            TranscriptionConfig(sample_duration=-1)

    def test_zero_sample_duration_valid(self):
        """Test that zero sample duration is valid (means full track)."""
        config = TranscriptionConfig(sample_duration=0)
        assert config.sample_duration == 0


class TestCommentaryKeywords:
    """Tests for commentary detection keywords."""

    def test_keywords_exist(self):
        """Test that commentary keywords list is not empty."""
        assert len(COMMENTARY_KEYWORDS) > 0

    def test_expected_keywords_present(self):
        """Test that expected keywords are in the list."""
        expected = ["commentary", "director", "cast", "crew"]
        for keyword in expected:
            assert keyword in COMMENTARY_KEYWORDS


class TestMusicKeywords:
    """Tests for music detection keywords."""

    def test_keywords_exist(self):
        """Test that music keywords list is not empty."""
        assert len(MUSIC_KEYWORDS) > 0

    def test_expected_keywords_present(self):
        """Test that expected keywords are in the list."""
        expected = ["music", "score", "soundtrack", "isolated score", "m&e"]
        for keyword in expected:
            assert keyword in MUSIC_KEYWORDS


class TestSfxKeywords:
    """Tests for SFX detection keywords."""

    def test_keywords_exist(self):
        """Test that SFX keywords list is not empty."""
        assert len(SFX_KEYWORDS) > 0

    def test_expected_keywords_present(self):
        """Test that expected keywords are in the list."""
        expected = ["sfx", "sound effects", "effects only", "ambient"]
        for keyword in expected:
            assert keyword in SFX_KEYWORDS


class TestMusicMetadataDetection:
    """Tests for is_music_by_metadata function."""

    def test_exact_match(self):
        """Test exact keyword matches."""
        assert is_music_by_metadata("Music") is True
        assert is_music_by_metadata("Score") is True
        assert is_music_by_metadata("Soundtrack") is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert is_music_by_metadata("MUSIC") is True
        assert is_music_by_metadata("MuSiC") is True

    def test_substring_match(self):
        """Test keyword as part of larger title."""
        assert is_music_by_metadata("Isolated Score") is True
        assert is_music_by_metadata("Music and Effects") is True
        assert is_music_by_metadata("M&E Track") is True

    def test_non_music_titles(self):
        """Test non-music titles return False."""
        assert is_music_by_metadata("Main Audio") is False
        assert is_music_by_metadata("English") is False
        assert is_music_by_metadata("Commentary") is False

    def test_none_or_empty(self):
        """Test None or empty string returns False."""
        assert is_music_by_metadata(None) is False
        assert is_music_by_metadata("") is False


class TestSfxMetadataDetection:
    """Tests for is_sfx_by_metadata function."""

    def test_exact_match(self):
        """Test exact keyword matches."""
        assert is_sfx_by_metadata("SFX") is True
        assert is_sfx_by_metadata("Sound Effects") is True
        assert is_sfx_by_metadata("Effects Only") is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert is_sfx_by_metadata("SFX") is True
        assert is_sfx_by_metadata("sfx") is True

    def test_substring_match(self):
        """Test keyword as part of larger title."""
        assert is_sfx_by_metadata("Ambient Sounds Only") is True
        assert is_sfx_by_metadata("Foley Track") is True

    def test_effects_alone_not_matched(self):
        """Test 'effects' alone is not matched (too broad)."""
        # "effects" alone could mean visual effects
        assert is_sfx_by_metadata("Visual Effects") is False
        assert is_sfx_by_metadata("Special Effects") is False

    def test_sound_effects_matched(self):
        """Test 'sound effects' is matched."""
        assert is_sfx_by_metadata("Sound Effects") is True
        assert is_sfx_by_metadata("Sound Effects Only") is True

    def test_non_sfx_titles(self):
        """Test non-SFX titles return False."""
        assert is_sfx_by_metadata("Main Audio") is False
        assert is_sfx_by_metadata("English") is False
        assert is_sfx_by_metadata("Music") is False

    def test_none_or_empty(self):
        """Test None or empty string returns False."""
        assert is_sfx_by_metadata(None) is False
        assert is_sfx_by_metadata("") is False


class TestHallucinationDetection:
    """Tests for is_hallucination function."""

    def test_empty_transcript(self):
        """Empty transcript is treated as hallucination."""
        assert is_hallucination(None) is True
        assert is_hallucination("") is True
        assert is_hallucination("   ") is True

    def test_short_transcript(self):
        """Very short transcript is treated as hallucination."""
        assert is_hallucination("Hi") is True
        assert is_hallucination("...") is True

    def test_youtube_outro_patterns(self):
        """YouTube-style outro patterns are hallucinations."""
        assert is_hallucination("Thank you for watching") is True
        assert is_hallucination("Thank you for listening") is True
        assert is_hallucination("Please subscribe") is True
        assert is_hallucination("Don't forget to subscribe") is True

    def test_music_notation(self):
        """Music notation patterns are hallucinations."""
        assert is_hallucination("[Music]") is True
        assert is_hallucination("[music]") is True
        assert is_hallucination("[Applause]") is True
        assert is_hallucination("[Silence]") is True

    def test_real_speech(self):
        """Real speech is not a hallucination."""
        assert is_hallucination("Hello, how are you today?") is False
        assert is_hallucination("The quick brown fox jumps over the lazy dog.") is False


class TestTrackClassificationDetection:
    """Tests for detect_track_classification function."""

    def test_music_by_metadata(self):
        """Track titled 'Isolated Score' should be MUSIC."""
        result = detect_track_classification(
            title="Isolated Score",
            transcript_sample=None,
            has_speech=True,
            confidence=0.9,
        )
        assert result == TrackClassification.MUSIC

    def test_sfx_by_metadata(self):
        """Track titled 'Sound Effects' should be SFX."""
        result = detect_track_classification(
            title="Sound Effects",
            transcript_sample=None,
            has_speech=True,
            confidence=0.9,
        )
        assert result == TrackClassification.SFX

    def test_commentary_by_metadata(self):
        """Track titled 'Director Commentary' should be COMMENTARY."""
        result = detect_track_classification(
            title="Director Commentary",
            transcript_sample=None,
            has_speech=True,
            confidence=0.9,
        )
        assert result == TrackClassification.COMMENTARY

    def test_non_speech_detection(self):
        """Low confidence + no speech should be NON_SPEECH."""
        result = detect_track_classification(
            title=None,
            transcript_sample=None,
            has_speech=False,
            confidence=0.2,
        )
        assert result == TrackClassification.NON_SPEECH

    def test_hallucination_low_confidence(self):
        """Low confidence + hallucination should be NON_SPEECH."""
        result = detect_track_classification(
            title=None,
            transcript_sample="Thank you for watching",
            has_speech=True,
            confidence=0.3,
        )
        assert result == TrackClassification.NON_SPEECH

    def test_main_with_speech(self):
        """Normal speech with high confidence should be MAIN."""
        result = detect_track_classification(
            title="Main Audio",
            transcript_sample="Hello, how are you today?",
            has_speech=True,
            confidence=0.95,
        )
        assert result == TrackClassification.MAIN

    def test_metadata_takes_priority(self):
        """Metadata should take priority over transcription signals."""
        # Music metadata should win even with speech detected
        result = detect_track_classification(
            title="M&E Track",
            transcript_sample="Hello world",
            has_speech=True,
            confidence=0.9,
        )
        assert result == TrackClassification.MUSIC

    def test_sfx_priority_over_music(self):
        """SFX detection should be checked before music."""
        # SFX is more specific than music
        result = detect_track_classification(
            title="SFX",
            transcript_sample=None,
            has_speech=False,
            confidence=0.2,
        )
        assert result == TrackClassification.SFX

    def test_quiet_dialog_preserved(self):
        """Low confidence but real transcript should remain MAIN."""
        # Real speech even at low confidence should not be marked as non-speech
        result = detect_track_classification(
            title=None,
            transcript_sample="The quick brown fox jumps over the lazy dog.",
            has_speech=True,
            confidence=0.35,  # Low but above hallucination
        )
        # With has_speech=True and real transcript, should be MAIN
        assert result == TrackClassification.MAIN
