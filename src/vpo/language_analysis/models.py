"""Domain models for multi-language audio detection.

This module defines the core data structures for language analysis results,
including language segments, percentages, and analysis metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from vpo.core import parse_iso_timestamp

if TYPE_CHECKING:
    from vpo.db.types import (
        LanguageAnalysisResultRecord,
        LanguageSegmentRecord,
    )
    from vpo.transcription.interface import (
        MultiLanguageDetectionResult,
    )


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

    @classmethod
    def from_record(cls, record: LanguageSegmentRecord) -> LanguageSegment:
        """Create a LanguageSegment from a database record.

        Args:
            record: Database record from language_segments table.

        Returns:
            LanguageSegment domain model.
        """
        return cls(
            language_code=record.language_code,
            start_time=record.start_time,
            end_time=record.end_time,
            confidence=record.confidence,
        )

    @classmethod
    def from_detection_result(
        cls,
        detection: MultiLanguageDetectionResult,
        sample_duration: float,
    ) -> LanguageSegment | None:
        """Create a LanguageSegment from a detection result.

        Args:
            detection: Detection result from transcription plugin.
            sample_duration: Duration of the sample in seconds.

        Returns:
            LanguageSegment if speech was detected, None otherwise.
        """
        if not detection.has_speech or not detection.language:
            return None

        return cls(
            language_code=detection.language,
            start_time=detection.position,
            end_time=detection.position + sample_duration,
            confidence=detection.confidence,
        )


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

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisMetadata:
        """Create AnalysisMetadata from a dictionary.

        Args:
            data: Dictionary with metadata fields. Missing fields use defaults.

        Returns:
            AnalysisMetadata instance.
        """
        return cls(
            plugin_name=data.get("plugin_name", "unknown"),
            plugin_version=data.get("plugin_version", "0.0.0"),
            model_name=data.get("model_name", "unknown"),
            sample_positions=tuple(data.get("sample_positions", [])),
            sample_duration=data.get("sample_duration", 30.0),
            total_duration=data.get("total_duration", 1.0),
            speech_ratio=data.get("speech_ratio", 0.0),
        )

    @classmethod
    def from_json(cls, json_str: str | None) -> AnalysisMetadata:
        """Create AnalysisMetadata from a JSON string.

        Args:
            json_str: JSON string or None for defaults.

        Returns:
            AnalysisMetadata instance.
        """
        if not json_str:
            return cls.from_dict({})
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "model_name": self.model_name,
            "sample_positions": list(self.sample_positions),
            "sample_duration": self.sample_duration,
            "total_duration": self.total_duration,
            "speech_ratio": self.speech_ratio,
        }

    def to_json(self) -> str:
        """Convert to JSON string for database storage.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict())


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
    ) -> LanguageAnalysisResult:
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

    @classmethod
    def from_record(
        cls,
        record: LanguageAnalysisResultRecord,
        segment_records: list[LanguageSegmentRecord],
    ) -> LanguageAnalysisResult:
        """Create a LanguageAnalysisResult from database records.

        Args:
            record: Database record from language_analysis_results table.
            segment_records: List of segment records from language_segments table.

        Returns:
            LanguageAnalysisResult domain model.
        """
        # Convert segment records to domain models
        segments = tuple(LanguageSegment.from_record(seg) for seg in segment_records)

        # Parse metadata from JSON
        metadata = AnalysisMetadata.from_json(record.analysis_metadata)

        # Calculate secondary languages from segments
        secondary_languages = cls._calculate_secondary_languages(
            segments, record.primary_language
        )

        return cls(
            track_id=record.track_id,
            file_hash=record.file_hash,
            primary_language=record.primary_language,
            primary_percentage=record.primary_percentage,
            secondary_languages=secondary_languages,
            classification=LanguageClassification(record.classification),
            segments=segments,
            metadata=metadata,
            created_at=parse_iso_timestamp(record.created_at),
            updated_at=parse_iso_timestamp(record.updated_at),
        )

    @staticmethod
    def _calculate_secondary_languages(
        segments: tuple[LanguageSegment, ...],
        primary_language: str,
    ) -> tuple[LanguagePercentage, ...]:
        """Calculate secondary language percentages from segments.

        Args:
            segments: All language segments.
            primary_language: The primary language code.

        Returns:
            Tuple of LanguagePercentage for secondary languages.
        """
        if not segments:
            return ()

        # Count duration per language using segment's duration property
        language_durations: dict[str, float] = {}
        for seg in segments:
            language_durations[seg.language_code] = (
                language_durations.get(seg.language_code, 0.0) + seg.duration
            )

        total_duration = sum(language_durations.values())
        if total_duration <= 0:
            return ()

        # Build secondary languages sorted by percentage descending
        secondary = sorted(
            (
                LanguagePercentage(lang, duration / total_duration)
                for lang, duration in language_durations.items()
                if lang != primary_language and duration > 0
            ),
            key=lambda lp: lp.percentage,
            reverse=True,
        )
        return tuple(secondary)

    def to_records(
        self,
    ) -> tuple[LanguageAnalysisResultRecord, list[LanguageSegmentRecord]]:
        """Convert to database records for persistence.

        Returns:
            Tuple of (main record, list of segment records).
            The main record has id=None (for insert) and segment records
            have analysis_id=0 (to be filled after main record insert).
        """
        from vpo.db.types import (
            LanguageAnalysisResultRecord,
            LanguageSegmentRecord,
        )

        now = datetime.now(timezone.utc).isoformat()

        main_record = LanguageAnalysisResultRecord(
            id=None,
            track_id=self.track_id,
            file_hash=self.file_hash,
            primary_language=self.primary_language,
            primary_percentage=self.primary_percentage,
            classification=self.classification.value,
            analysis_metadata=self.metadata.to_json(),
            created_at=self.created_at.isoformat(),
            updated_at=now,
        )

        segment_records = [
            LanguageSegmentRecord(
                id=None,
                analysis_id=0,  # To be set after main record insert
                language_code=seg.language_code,
                start_time=seg.start_time,
                end_time=seg.end_time,
                confidence=seg.confidence,
            )
            for seg in self.segments
        ]

        return main_record, segment_records
