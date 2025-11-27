# Contract: Language Analysis Plugin Extension

**Feature**: 035-multi-language-audio-detection
**Version**: 1.0.0
**Date**: 2025-11-26

## Overview

Extension to the TranscriptionPlugin protocol to support multi-language audio detection through segment-based sampling.

---

## Protocol Extension

### Method: `detect_multi_language`

Analyzes audio at multiple sample positions to detect language variation throughout the track.

**Signature**:
```python
def detect_multi_language(
    self,
    audio_data: bytes,
    sample_positions: list[float],
    sample_duration: float = 5.0,
    sample_rate: int = 16000,
) -> MultiLanguageDetectionResult
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio_data` | bytes | Yes | Raw audio bytes (WAV format, mono, 16kHz) |
| `sample_positions` | list[float] | Yes | Positions in seconds to sample |
| `sample_duration` | float | No | Duration of each sample (default: 5.0) |
| `sample_rate` | int | No | Audio sample rate (default: 16000) |

**Returns**: `MultiLanguageDetectionResult`

**Raises**:
- `TranscriptionError`: If analysis fails
- `InsufficientAudioError`: If audio is shorter than first sample position
- `PluginDependencyError`: If required model is unavailable

---

### Feature Flag

```python
def supports_feature(self, feature: str) -> bool:
    """Check if plugin supports a feature.

    Extended features:
    - "multi_language_detection": Supports detect_multi_language method
    """
```

---

## Data Structures

### MultiLanguageDetectionResult

```python
@dataclass
class MultiLanguageDetectionResult:
    """Result of multi-language detection analysis."""

    primary_language: str
    """ISO 639-2/B code of primary language (e.g., 'eng')."""

    primary_percentage: float
    """Percentage of samples in primary language (0.0-1.0)."""

    segments: list[LanguageSegment]
    """Individual language detections with timestamps."""

    classification: LanguageClassification
    """SINGLE_LANGUAGE (>=95% primary) or MULTI_LANGUAGE."""

    speech_ratio: float
    """Ratio of speech to silence/music in analyzed samples."""

    model_name: str
    """Name of model used for detection."""
```

### LanguageSegment

```python
@dataclass
class LanguageSegment:
    """Language detection for a specific time range."""

    language_code: str
    """ISO 639-2/B code (e.g., 'eng', 'fre', 'ger')."""

    start_time: float
    """Start position in seconds."""

    end_time: float
    """End position in seconds."""

    confidence: float
    """Detection confidence (0.0-1.0)."""
```

### LanguageClassification

```python
class LanguageClassification(Enum):
    """Track classification based on language composition."""

    SINGLE_LANGUAGE = "SINGLE_LANGUAGE"
    """95%+ of samples are same language."""

    MULTI_LANGUAGE = "MULTI_LANGUAGE"
    """Less than 95% of samples are same language."""
```

---

## Sampling Strategy

### Default Strategy

For typical film content (90-180 minutes):

| Track Duration | Sample Interval | Samples Count |
|----------------|-----------------|---------------|
| < 30 min | 5 minutes | 6 |
| 30-60 min | 7 minutes | 8-9 |
| 60-120 min | 10 minutes | 6-12 |
| > 120 min | 10 minutes | 12+ |

### Sample Position Calculation

```python
def calculate_sample_positions(
    duration: float,
    interval_seconds: float = 600.0,  # 10 minutes
    min_samples: int = 6,
) -> list[float]:
    """Calculate sample positions for multi-language detection.

    Args:
        duration: Track duration in seconds
        interval_seconds: Interval between samples
        min_samples: Minimum number of samples

    Returns:
        List of sample positions in seconds
    """
    if duration < 30:
        # Very short content: single sample at middle
        return [duration / 2]

    # Calculate positions at regular intervals
    positions = []
    current = 30.0  # Skip first 30 seconds (credits/logos)

    while current < duration - 30:  # Skip last 30 seconds (end credits)
        positions.append(current)
        current += interval_seconds

    # Ensure minimum samples
    if len(positions) < min_samples and duration > 60:
        interval = (duration - 60) / min_samples
        positions = [30.0 + i * interval for i in range(min_samples)]

    return positions
```

---

## Error Handling

### Error Types

| Error | Condition | Recovery |
|-------|-----------|----------|
| `TranscriptionError` | General analysis failure | Skip track, log warning |
| `InsufficientAudioError` | Audio shorter than first sample | Use full audio if >5s, else skip |
| `PluginDependencyError` | Model unavailable | Fail with user-friendly message |
| `InsufficientSpeechError` | Not enough speech detected | Mark as "unknown", log reason |

### Graceful Degradation

1. If sample fails: Skip that sample, continue with others
2. If >50% samples fail: Mark analysis as failed
3. If speech ratio < 10%: Mark as "insufficient_speech"

---

## Implementation Notes

### Whisper Integration

```python
def detect_multi_language(
    self,
    audio_data: bytes,
    sample_positions: list[float],
    sample_duration: float = 5.0,
    sample_rate: int = 16000,
) -> MultiLanguageDetectionResult:
    """Detect language variation using Whisper sampling."""

    segments = []

    for position in sample_positions:
        # Extract sample at position
        sample = self._extract_sample(
            audio_data, position, sample_duration, sample_rate
        )

        if sample is None:
            continue  # Skip if position beyond audio

        # Run Whisper language detection on sample
        try:
            result = self._detect_language_sample(sample)
            segments.append(LanguageSegment(
                language_code=result.language,
                start_time=position,
                end_time=position + sample_duration,
                confidence=result.confidence,
            ))
        except InsufficientSpeechError:
            # No speech in this sample, skip
            continue

    # Aggregate results
    return self._aggregate_segments(segments)
```

### Performance Considerations

- Use smallest viable Whisper model (tiny or base) for language-only detection
- Batch process samples when possible
- Cache audio file loading between samples
- Target: <3 seconds per sample on CPU

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-26 | Initial contract definition |
