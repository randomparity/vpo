"""Unit tests for transcription configuration."""

import pytest

from video_policy_orchestrator.config.models import (
    TranscriptionPluginConfig,
    VPOConfig,
)


class TestTranscriptionPluginConfig:
    """Tests for TranscriptionPluginConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = TranscriptionPluginConfig()

        assert config.plugin is None
        assert config.model_size == "base"
        assert config.sample_duration == 30
        assert config.gpu_enabled is True
        # Multi-sample detection defaults
        assert config.max_samples == 3
        assert config.confidence_threshold == 0.85
        assert config.incumbent_bonus == 0.15

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TranscriptionPluginConfig(
            plugin="whisper-local",
            model_size="medium",
            sample_duration=120,
            gpu_enabled=False,
        )

        assert config.plugin == "whisper-local"
        assert config.model_size == "medium"
        assert config.sample_duration == 120
        assert config.gpu_enabled is False

    def test_valid_model_sizes(self):
        """Test all valid model sizes."""
        valid_sizes = ["tiny", "base", "small", "medium", "large"]
        for size in valid_sizes:
            config = TranscriptionPluginConfig(model_size=size)
            assert config.model_size == size

    def test_invalid_model_size(self):
        """Test that invalid model size raises error."""
        with pytest.raises(ValueError, match="model_size must be one of"):
            TranscriptionPluginConfig(model_size="invalid")

    def test_negative_sample_duration(self):
        """Test that negative sample duration raises error."""
        with pytest.raises(ValueError, match="sample_duration must be non-negative"):
            TranscriptionPluginConfig(sample_duration=-10)

    def test_zero_sample_duration(self):
        """Test that zero sample duration is valid (full track)."""
        config = TranscriptionPluginConfig(sample_duration=0)
        assert config.sample_duration == 0

    def test_max_samples_validation(self):
        """Test that max_samples must be at least 1."""
        with pytest.raises(ValueError, match="max_samples must be at least 1"):
            TranscriptionPluginConfig(max_samples=0)

    def test_confidence_threshold_validation_low(self):
        """Test that confidence_threshold must be >= 0."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            TranscriptionPluginConfig(confidence_threshold=-0.1)

    def test_confidence_threshold_validation_high(self):
        """Test that confidence_threshold must be <= 1."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            TranscriptionPluginConfig(confidence_threshold=1.1)

    def test_incumbent_bonus_validation(self):
        """Test that incumbent_bonus must be non-negative."""
        with pytest.raises(ValueError, match="incumbent_bonus must be non-negative"):
            TranscriptionPluginConfig(incumbent_bonus=-0.1)


class TestVPOConfigTranscription:
    """Tests for transcription section in VPOConfig."""

    def test_default_transcription_config(self):
        """Test that VPOConfig has default transcription config."""
        config = VPOConfig()

        assert hasattr(config, "transcription")
        assert isinstance(config.transcription, TranscriptionPluginConfig)
        assert config.transcription.model_size == "base"

    def test_custom_transcription_config(self):
        """Test VPOConfig with custom transcription settings."""
        config = VPOConfig(
            transcription=TranscriptionPluginConfig(
                plugin="custom-plugin",
                model_size="large",
            )
        )

        assert config.transcription.plugin == "custom-plugin"
        assert config.transcription.model_size == "large"
