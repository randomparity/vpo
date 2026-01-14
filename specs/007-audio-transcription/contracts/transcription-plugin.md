# TranscriptionPlugin Protocol Contract

**Version**: 1.0.0
**Feature**: 007-audio-transcription

## Overview

The TranscriptionPlugin protocol defines the interface for audio transcription backends.
Plugins implementing this protocol can provide language detection and transcription capabilities.

## Protocol Definition

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TranscriptionPlugin(Protocol):
    """Protocol for transcription plugins.

    Plugins must implement this protocol to provide transcription services.
    The protocol supports both language detection (fast) and full transcription.

    Required Attributes:
        name: Unique plugin identifier (e.g., "whisper-local")
        version: Plugin version using semver (e.g., "1.0.0")

    Optional Attributes:
        description: Human-readable description
        supported_features: List of features ("language_detection", "transcription", "commentary_detection")
    """

    name: str
    version: str

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> "TranscriptionResult":
        """Detect the spoken language in audio data.

        Args:
            audio_data: Raw audio bytes (WAV format, mono)
            sample_rate: Sample rate of audio (default 16kHz for Whisper)

        Returns:
            TranscriptionResult with detected_language and confidence_score.
            transcript_sample will be None for language-only detection.

        Raises:
            TranscriptionError: If detection fails
        """
        ...

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> "TranscriptionResult":
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (WAV format, mono)
            sample_rate: Sample rate of audio (default 16kHz for Whisper)
            language: Optional language hint (ISO 639-1 code)

        Returns:
            TranscriptionResult with full transcript in transcript_sample.
            Also includes detected_language and confidence_score.

        Raises:
            TranscriptionError: If transcription fails
        """
        ...

    def supports_feature(self, feature: str) -> bool:
        """Check if plugin supports a specific feature.

        Args:
            feature: Feature name to check. Valid values:
                - "language_detection": Can detect spoken language
                - "transcription": Can produce text transcripts
                - "commentary_detection": Can identify commentary patterns

        Returns:
            True if feature is supported, False otherwise
        """
        ...

    def configure(self, config: dict) -> None:
        """Configure plugin with settings.

        Args:
            config: Plugin-specific configuration dict.
                    For Whisper plugin, supports:
                    - model_size: "tiny", "base", "small", "medium", "large"
                    - gpu_enabled: bool
                    - sample_duration: int (seconds)

        Raises:
            ConfigurationError: If config is invalid
        """
        ...
```

## Data Types

### TranscriptionResult

```python
@dataclass
class TranscriptionResult:
    """Result from transcription plugin."""

    detected_language: str | None
    """ISO 639-1 language code (e.g., "en", "fr") or None if unknown"""

    confidence_score: float
    """Confidence in detection, 0.0 to 1.0"""

    track_type: str
    """Classification: "main", "commentary", or "alternate" """

    transcript_sample: str | None
    """Text transcript or sample (may be truncated)"""

    plugin_name: str
    """Name of plugin that produced this result"""

    metadata: dict | None = None
    """Optional plugin-specific metadata"""
```

### TranscriptionError

```python
class TranscriptionError(Exception):
    """Base exception for transcription errors."""

    def __init__(
        self,
        message: str,
        recoverable: bool = True,
        details: dict | None = None
    ):
        self.message = message
        self.recoverable = recoverable
        self.details = details or {}
        super().__init__(message)
```

## Feature Flags

Plugins should accurately report their capabilities via `supports_feature()`:

| Feature | Description | Required |
|---------|-------------|----------|
| `language_detection` | Can detect spoken language | Yes |
| `transcription` | Can produce full text transcripts | No |
| `commentary_detection` | Can identify commentary patterns in transcripts | No |

## Plugin Registration

Plugins are discovered via Python entry points:

```toml
# In plugin's pyproject.toml
[project.entry-points."vpo.transcription"]
whisper = "vpo_whisper:WhisperTranscriptionPlugin"
```

Or via directory-based plugin loading (existing VPO plugin system).

## Usage Example

```python
from vpo.transcription import get_transcription_plugin

# Get configured plugin
plugin = get_transcription_plugin()

# Detect language from audio
audio_bytes = extract_audio_stream(file_path, track_index)
result = plugin.detect_language(audio_bytes)

print(f"Detected: {result.detected_language} ({result.confidence_score:.0%})")

# Full transcription if needed
if plugin.supports_feature("transcription"):
    result = plugin.transcribe(audio_bytes, language=result.detected_language)
    print(f"Transcript: {result.transcript_sample[:100]}...")
```

## Error Handling

Plugins should raise `TranscriptionError` for all failures:

```python
try:
    result = plugin.detect_language(audio_data)
except TranscriptionError as e:
    if e.recoverable:
        # Can retry or skip this track
        logger.warning(f"Transcription failed (recoverable): {e.message}")
    else:
        # Plugin is broken, should be disabled
        logger.error(f"Transcription failed (fatal): {e.message}")
        raise
```

## Versioning

This contract follows semantic versioning:
- **MAJOR**: Breaking changes to protocol methods
- **MINOR**: New optional methods or attributes
- **PATCH**: Documentation or type hint changes

Plugins should declare `min_api_version` and `max_api_version` for compatibility.
