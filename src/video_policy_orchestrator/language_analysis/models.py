"""Domain models for multi-language audio detection.

This module defines the core data structures for language analysis results,
including language segments, percentages, and analysis metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LanguageClassification(Enum):
    """Classification of audio track language composition.

    SINGLE_LANGUAGE: 95% or more of the track is in one language.
    MULTI_LANGUAGE: Less than 95% of the track is in the primary language.
    """

    SINGLE_LANGUAGE = "SINGLE_LANGUAGE"
    MULTI_LANGUAGE = "MULTI_LANGUAGE"


@dataclass(frozen=True)
class LanguageSegment:
    """A detected language within a specific time range of an audio track.

    Represents a single language detection at a sample position.

    Attributes:
        language_code: ISO 639-2/B language code (e.g., "eng", "fre", "ger").
        start_time: Start position in seconds from beginning of track.
        end_time: End position in seconds from beginning of track.
        confidence: Detection confidence score between 0.0 and 1.0.
    """

    language_code: str
    start_time: float
    end_time: float
    confidence: float

    def __post_init__(self) -> None:
        """Validate segment constraints."""
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be greater than "
                f"start_time ({self.start_time})"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence ({self.confidence}) must be between 0.0 and 1.0"
            )

    @property
    def duration(self) -> float:
        """Return the duration of this segment in seconds."""
        return self.end_time - self.start_time


@dataclass(frozen=True)
class LanguagePercentage:
    """A language with its percentage of total speech time.

    Used to represent secondary languages in analysis results.

    Attributes:
        language_code: ISO 639-2/B language code.
        percentage: Percentage of total speech time (0.0 to 1.0).
    """

    language_code: str
    percentage: float

    def __post_init__(self) -> None:
        """Validate percentage constraints."""
        if not 0.0 <= self.percentage <= 1.0:
            raise ValueError(
                f"percentage ({self.percentage}) must be between 0.0 and 1.0"
            )


@dataclass(frozen=True)
class AnalysisMetadata:
    """Processing details for the language analysis.

    Captures information about how the analysis was performed, including
    the plugin used, model parameters, and sampling strategy.

    Attributes:
        plugin_name: Name of the plugin that performed the analysis.
        plugin_version: Version string of the plugin.
        model_name: Name of the ML model used (e.g., "whisper-base").
        sample_positions: Tuple of sample positions in seconds.
        sample_duration: Duration of each sample in seconds.
        total_duration: Total duration of the audio track in seconds.
        speech_ratio: Ratio of detected speech to silence (0.0 to 1.0).
    """

    plugin_name: str
    plugin_version: str
    model_name: str
    sample_positions: tuple[float, ...]
    sample_duration: float
    total_duration: float
    speech_ratio: float

    def __post_init__(self) -> None:
        """Validate metadata constraints."""
        if not 0.0 <= self.speech_ratio <= 1.0:
            raise ValueError(
                f"speech_ratio ({self.speech_ratio}) must be between 0.0 and 1.0"
            )
        if self.sample_duration <= 0:
            raise ValueError(
                f"sample_duration ({self.sample_duration}) must be positive"
            )
        if self.total_duration <= 0:
            raise ValueError(f"total_duration ({self.total_duration}) must be positive")


@dataclass
class LanguageAnalysisResult:
    """Complete language analysis result for an audio track.

    Aggregates individual language segments into a comprehensive result
    with primary/secondary language statistics and classification.

    Attributes:
        track_id: Database ID of the analyzed audio track.
        file_hash: Content hash of the file for cache validation.
        primary_language: ISO 639-2/B code of the primary (most common) language.
        primary_percentage: Percentage of track in primary language (0.0 to 1.0).
        secondary_languages: Tuple of secondary languages with their percentages.
        classification: SINGLE_LANGUAGE or MULTI_LANGUAGE classification.
        segments: Tuple of individual language detection segments.
        metadata: Processing details for the analysis.
        created_at: UTC timestamp when analysis was first created.
        updated_at: UTC timestamp when analysis was last updated.
    """

    track_id: int
    file_hash: str
    primary_language: str
    primary_percentage: float
    secondary_languages: tuple[LanguagePercentage, ...]
    classification: LanguageClassification
    segments: tuple[LanguageSegment, ...]
    metadata: AnalysisMetadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Threshold for classifying as single-language (95%)
    SINGLE_LANGUAGE_THRESHOLD: float = field(default=0.95, repr=False, compare=False)

    @classmethod
    def from_segments(
        cls,
        track_id: int,
        file_hash: str,
        segments: list[LanguageSegment],
        metadata: AnalysisMetadata,
        single_language_threshold: float = 0.95,
    ) -> "LanguageAnalysisResult":
        """Create an analysis result by aggregating language segments.

        Calculates primary and secondary languages from the provided segments,
        determines the classification based on the threshold.

        Args:
            track_id: Database ID of the track.
            file_hash: Content hash of the file.
            segments: List of detected language segments.
            metadata: Analysis metadata.
            single_language_threshold: Threshold for single-language classification.

        Returns:
            LanguageAnalysisResult with aggregated statistics.

        Raises:
            ValueError: If no segments are provided.
        """
        if not segments:
            raise ValueError("At least one segment is required")

        # Count total duration per language
        language_durations: dict[str, float] = {}
        for segment in segments:
            lang = segment.language_code
            duration = segment.duration
            language_durations[lang] = language_durations.get(lang, 0.0) + duration

        # Calculate total detected duration
        total_duration = sum(language_durations.values())
        if total_duration <= 0:
            raise ValueError("Total segment duration must be positive")

        # Calculate percentages
        language_percentages: dict[str, float] = {
            lang: duration / total_duration
            for lang, duration in language_durations.items()
        }

        # Determine primary language (highest percentage)
        sorted_languages = sorted(
            language_percentages.items(), key=lambda x: x[1], reverse=True
        )
        primary_language, primary_percentage = sorted_languages[0]

        # Build secondary languages tuple
        secondary_languages = tuple(
            LanguagePercentage(language_code=lang, percentage=pct)
            for lang, pct in sorted_languages[1:]
            if pct > 0.0
        )

        # Determine classification
        classification = (
            LanguageClassification.SINGLE_LANGUAGE
            if primary_percentage >= single_language_threshold
            else LanguageClassification.MULTI_LANGUAGE
        )

        now = datetime.now(timezone.utc)
        return cls(
            track_id=track_id,
            file_hash=file_hash,
            primary_language=primary_language,
            primary_percentage=primary_percentage,
            secondary_languages=secondary_languages,
            classification=classification,
            segments=tuple(segments),
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )

    @property
    def is_multi_language(self) -> bool:
        """Return True if the track is classified as multi-language."""
        return self.classification == LanguageClassification.MULTI_LANGUAGE

    def has_secondary_language_above_threshold(self, threshold: float = 0.05) -> bool:
        """Check if any secondary language exceeds the given threshold.

        Args:
            threshold: Minimum percentage threshold (default 5%).

        Returns:
            True if any secondary language percentage exceeds threshold.
        """
        return any(lang.percentage >= threshold for lang in self.secondary_languages)
