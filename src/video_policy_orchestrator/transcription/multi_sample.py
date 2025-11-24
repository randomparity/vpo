"""Multi-sample audio transcription for improved language detection accuracy.

This module implements smart detection that progressively samples throughout
a video file until confidence thresholds are met, with majority voting and
incumbent language bias for final result aggregation.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from video_policy_orchestrator.transcription.audio_extractor import (
    extract_audio_stream,
)
from video_policy_orchestrator.transcription.interface import (
    TranscriptionError,
    TranscriptionPlugin,
)

logger = logging.getLogger(__name__)


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
    """
    if num_samples < 1:
        return []

    if track_duration <= 0:
        return [0.0]

    # Ensure we don't try to sample past the end
    max_start = max(0, track_duration - sample_duration)

    if num_samples == 1:
        return [0.0]

    if max_start == 0:
        # Track is shorter than sample duration, just sample from start
        return [0.0]

    # Calculate positions at regular intervals
    # For n samples: 0%, 50%, 25%, 75%, 12.5%, 37.5%, 62.5%, 87.5%, etc.
    # This ordering prioritizes beginning and middle for early exit
    positions: list[float] = []

    # Build positions in priority order
    if num_samples >= 1:
        positions.append(0.0)  # Beginning
    if num_samples >= 2:
        positions.append(max_start * 0.5)  # Middle
    if num_samples >= 3:
        positions.append(max_start * 0.25)  # Quarter
    if num_samples >= 4:
        positions.append(max_start * 0.75)  # Three-quarters

    # For more samples, fill in remaining positions
    for i in range(4, num_samples):
        # Distribute remaining positions evenly
        fraction = i / num_samples
        pos = max_start * fraction
        if pos not in positions:
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

    # Count votes per language
    votes: Counter[str] = Counter()
    for sample in valid_samples:
        if sample.language:
            votes[sample.language] += 1

    # Add incumbent bonus if it has votes
    if incumbent_language and incumbent_language in votes:
        votes[incumbent_language] += incumbent_bonus
        logger.debug(
            "Added %.2f bonus vote for incumbent language '%s'",
            incumbent_bonus,
            incumbent_language,
        )

    # Find winner
    winner = votes.most_common(1)[0][0]

    # Calculate average confidence for winning language
    winner_samples = [s for s in valid_samples if s.language == winner]
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
