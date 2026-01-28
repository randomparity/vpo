"""Multi-sample audio transcription for improved language detection accuracy.

This module implements smart detection that progressively samples throughout
a video file until confidence thresholds are met, with majority voting and
incumbent language bias for final result aggregation.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from vpo.language import languages_match, normalize_language
from vpo.transcription.audio_extractor import (
    extract_audio_stream,
)
from vpo.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)

logger = logging.getLogger(__name__)


def _position_exists(pos: float, positions: list[float], tol: float = 0.001) -> bool:
    """Check if position already exists within tolerance."""
    return any(abs(p - pos) < tol for p in positions)


@dataclass
class SampleResult:
    """Result from a single audio sample."""

    position: float  # Start position in seconds
    language: str | None
    confidence: float
    transcript_sample: str | None = None


@dataclass
class MultiSampleConfig:
    """Configuration for multi-sample detection."""

    max_samples: int = 3  # Maximum number of samples to take
    sample_duration: int = 30  # Duration of each sample in seconds
    confidence_threshold: float = 0.85  # Confidence to stop early
    incumbent_bonus: float = 0.15  # Bonus vote for track's existing language

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_samples < 1:
            raise ValueError("max_samples must be at least 1")
        if self.sample_duration < 1:
            raise ValueError("sample_duration must be at least 1 second")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        if self.incumbent_bonus < 0.0:
            raise ValueError("incumbent_bonus must be non-negative")


@dataclass
class AggregatedResult:
    """Final aggregated result from multiple samples."""

    language: str | None
    confidence: float
    samples_taken: int
    sample_results: list[SampleResult] = field(default_factory=list)
    transcript_sample: str | None = None  # Best transcript from samples


def calculate_sample_positions(
    track_duration: float,
    num_samples: int,
    sample_duration: int,
) -> list[float]:
    """Calculate evenly-distributed sample positions throughout track.

    Positions are ordered for progressive sampling: start, middle, then
    intermediate points. This allows early exit after 1-2 samples if
    confidence is sufficient.

    Args:
        track_duration: Total track duration in seconds.
        num_samples: Number of sample positions to calculate.
        sample_duration: Duration of each sample in seconds.

    Returns:
        List of start positions in seconds, ordered for progressive sampling.

    Raises:
        ValueError: If sample_duration is negative.
    """
    if sample_duration < 0:
        raise ValueError("sample_duration must be non-negative")

    if num_samples < 1:
        return []

    # Handle edge cases: short/zero duration or single sample
    max_start = max(0, track_duration - sample_duration)
    if track_duration <= 0 or max_start == 0 or num_samples == 1:
        return [0.0]

    # Priority fractions: beginning, middle, quarter, three-quarters
    priority_fractions = [0.0, 0.5, 0.25, 0.75]
    positions: list[float] = []

    # Add priority positions first
    for fraction in priority_fractions[:num_samples]:
        positions.append(max_start * fraction)

    # For more samples, fill in remaining positions evenly
    for i in range(4, num_samples):
        fraction = i / num_samples
        pos = max_start * fraction
        if not _position_exists(pos, positions):
            positions.append(pos)

    return positions[:num_samples]


def aggregate_results(
    samples: list[SampleResult],
    incumbent_language: str | None = None,
    incumbent_bonus: float = 0.15,
) -> AggregatedResult:
    """Aggregate multiple sample results using majority vote with incumbent bias.

    Args:
        samples: List of sample results to aggregate.
        incumbent_language: Track's existing language tag (gets bonus vote).
        incumbent_bonus: Fractional bonus vote for incumbent language.

    Returns:
        AggregatedResult with winning language and aggregated confidence.
    """
    if not samples:
        return AggregatedResult(
            language=None,
            confidence=0.0,
            samples_taken=0,
        )

    # Filter out samples with no detected language
    valid_samples = [s for s in samples if s.language]

    if not valid_samples:
        return AggregatedResult(
            language=None,
            confidence=0.0,
            samples_taken=len(samples),
            sample_results=samples,
        )

    # Normalize incumbent language to ensure consistent comparison
    # This allows "de" (ISO 639-1) to match "ger" (ISO 639-2/B)
    incumbent_normalized = (
        normalize_language(incumbent_language) if incumbent_language else None
    )

    # Weight votes by confidence score
    # This ensures high-confidence detections outweigh low-confidence guesses
    # All languages are normalized to ensure consistent aggregation
    votes: dict[str, float] = {}
    for sample in valid_samples:
        if sample.language:
            # Normalize to ensure "de" and "ger" are treated as the same language
            lang_normalized = normalize_language(sample.language)
            if lang_normalized not in votes:
                votes[lang_normalized] = 0.0
            votes[lang_normalized] += sample.confidence

    # Add incumbent bonus if incumbent language has votes
    # Use languages_match for comparison to handle different ISO standards
    incumbent_key = None
    if incumbent_normalized:
        for lang in votes:
            if languages_match(lang, incumbent_normalized):
                incumbent_key = lang
                break

    if incumbent_key:
        votes[incumbent_key] += incumbent_bonus
        logger.debug(
            "Added %.2f bonus vote for incumbent language '%s'",
            incumbent_bonus,
            incumbent_normalized,
        )

    # Find winner (highest weighted vote)
    winner = max(votes, key=lambda k: votes[k])

    # Calculate average confidence for winning language
    # Use languages_match to handle samples that might have different ISO formats
    winner_samples = [
        s for s in valid_samples if s.language and languages_match(s.language, winner)
    ]
    avg_confidence = sum(s.confidence for s in winner_samples) / len(winner_samples)

    # Find best transcript sample (highest confidence sample with transcript)
    best_transcript = None
    best_transcript_confidence = 0.0
    for sample in samples:
        if sample.transcript_sample and sample.confidence > best_transcript_confidence:
            best_transcript = sample.transcript_sample
            best_transcript_confidence = sample.confidence

    return AggregatedResult(
        language=winner,
        confidence=avg_confidence,
        samples_taken=len(samples),
        sample_results=samples,
        transcript_sample=best_transcript,
    )


def smart_detect(
    file_path: Path,
    track_index: int,
    track_duration: float,
    transcriber: TranscriptionPlugin,
    config: MultiSampleConfig | None = None,
    incumbent_language: str | None = None,
) -> AggregatedResult:
    """Perform smart multi-sample language detection.

    Starts with a sample from the beginning. If confidence is below
    threshold, progressively samples additional positions until
    confidence is adequate or max samples reached.

    Args:
        file_path: Path to the video file.
        track_index: Index of the audio track to analyze.
        track_duration: Total track duration in seconds.
        transcriber: Transcription plugin to use.
        config: Multi-sample configuration (uses defaults if None).
        incumbent_language: Track's existing language tag for bias.

    Returns:
        AggregatedResult with final detected language and confidence.

    Raises:
        TranscriptionError: If all sample extractions fail.
    """
    if config is None:
        config = MultiSampleConfig()

    # Calculate all potential sample positions
    positions = calculate_sample_positions(
        track_duration,
        config.max_samples,
        config.sample_duration,
    )

    samples: list[SampleResult] = []
    errors: list[str] = []

    for i, position in enumerate(positions):
        logger.info(
            "Sampling position %.1fs (sample %d/%d) for track %d",
            position,
            i + 1,
            len(positions),
            track_index,
        )

        try:
            # Extract audio at this position
            audio_data = extract_audio_stream(
                file_path,
                track_index,
                sample_duration=config.sample_duration,
                start_offset=position,
            )

            # Transcribe the sample
            result = transcriber.transcribe(audio_data)

            sample = SampleResult(
                position=position,
                language=result.detected_language,
                confidence=result.confidence_score,
                transcript_sample=result.transcript_sample,
            )
            samples.append(sample)

            logger.debug(
                "Sample at %.1fs: language=%s, confidence=%.2f",
                position,
                sample.language,
                sample.confidence,
            )

            # Check for early exit on high confidence
            if sample.confidence >= config.confidence_threshold:
                logger.info(
                    "High confidence (%.2f >= %.2f) at sample %d, stopping early",
                    sample.confidence,
                    config.confidence_threshold,
                    i + 1,
                )
                break

        except TranscriptionError as e:
            logger.warning("Failed to process sample at %.1fs: %s", position, e)
            errors.append(f"Position {position}s: {e}")
            continue

    if not samples and errors:
        raise TranscriptionError(
            f"All {len(errors)} samples failed: {'; '.join(errors)}"
        )

    return aggregate_results(
        samples,
        incumbent_language=incumbent_language,
        incumbent_bonus=config.incumbent_bonus,
    )


__all__ = [
    "AggregatedResult",
    "MultiSampleConfig",
    "SampleResult",
    "aggregate_results",
    "calculate_sample_positions",
    "smart_detect",
]
