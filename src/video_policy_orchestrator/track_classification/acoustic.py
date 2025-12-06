"""Acoustic analysis for track classification.

This module provides acoustic analysis functions for detecting commentary tracks
based on audio characteristics like speech density, dynamic range, and voice count.
"""

import logging
from typing import Protocol, runtime_checkable

from .models import AcousticProfile

logger = logging.getLogger(__name__)


@runtime_checkable
class AcousticAnalyzer(Protocol):
    """Protocol for acoustic analysis providers.

    Plugins that support acoustic analysis should implement this protocol.
    """

    def get_acoustic_profile(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> AcousticProfile:
        """Extract acoustic profile from audio data.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data (default 16kHz).

        Returns:
            AcousticProfile with speech density, dynamic range, etc.

        Raises:
            TranscriptionError: If analysis fails.
        """
        ...

    def supports_acoustic_analysis(self) -> bool:
        """Check if plugin supports acoustic analysis.

        Returns:
            True if acoustic analysis is available.
        """
        ...


def extract_acoustic_profile(
    audio_data: bytes,
    sample_rate: int = 16000,
    analyzer: AcousticAnalyzer | None = None,
) -> AcousticProfile | None:
    """Extract acoustic profile from audio data.

    If an analyzer is provided and supports acoustic analysis, uses the analyzer.
    Otherwise, returns None (acoustic analysis unavailable).

    Args:
        audio_data: Raw audio bytes (WAV format, mono).
        sample_rate: Sample rate of audio data.
        analyzer: Optional acoustic analyzer implementation.

    Returns:
        AcousticProfile if analysis succeeded, None if unavailable.
    """
    if analyzer is None:
        logger.debug("No acoustic analyzer provided - skipping acoustic analysis")
        return None

    if not analyzer.supports_acoustic_analysis():
        logger.debug("Analyzer does not support acoustic analysis - skipping")
        return None

    try:
        return analyzer.get_acoustic_profile(audio_data, sample_rate)
    except Exception as e:
        logger.warning("Acoustic analysis failed: %s", e)
        return None


def is_commentary_by_acoustic(profile: AcousticProfile) -> bool:
    """Determine if acoustic profile indicates commentary track.

    Commentary tracks typically have:
    - High speech density (>0.7) - continuous talking
    - Low dynamic range (<15 dB) - consistent speech levels
    - 1-3 distinct voices - consistent speakers
    - Often have background audio (film playing underneath)

    Args:
        profile: Acoustic analysis profile.

    Returns:
        True if profile indicates commentary.
    """
    # Weighted scoring for commentary indicators
    score = 0.0

    # High speech density is strong indicator
    if profile.speech_density > 0.7:
        score += 0.4
    elif profile.speech_density > 0.5:
        score += 0.2

    # Low dynamic range typical for commentary
    if profile.dynamic_range_db < 15:
        score += 0.3
    elif profile.dynamic_range_db < 20:
        score += 0.15

    # 1-3 consistent voices typical for commentary
    if 1 <= profile.voice_count_estimate <= 3:
        score += 0.2

    # Background audio (film playing) is indicator
    if profile.has_background_audio:
        score += 0.1

    # Threshold for commentary determination
    is_commentary = score >= 0.5

    logger.debug(
        "Acoustic commentary detection: score=%.2f, speech=%.2f, "
        "dynamic_range=%.1fdB, voices=%d, bg_audio=%s -> %s",
        score,
        profile.speech_density,
        profile.dynamic_range_db,
        profile.voice_count_estimate,
        profile.has_background_audio,
        "commentary" if is_commentary else "main",
    )

    return is_commentary


def get_commentary_confidence(profile: AcousticProfile) -> float:
    """Calculate confidence score for commentary classification.

    Returns a confidence score based on how strongly the acoustic
    profile indicates commentary characteristics.

    Args:
        profile: Acoustic analysis profile.

    Returns:
        Confidence score from 0.0 to 1.0.
    """
    # Calculate weighted score
    score = 0.0

    # Speech density contribution
    if profile.speech_density > 0.8:
        score += 0.3
    elif profile.speech_density > 0.7:
        score += 0.25
    elif profile.speech_density > 0.5:
        score += 0.15

    # Dynamic range contribution
    if profile.dynamic_range_db < 12:
        score += 0.25
    elif profile.dynamic_range_db < 15:
        score += 0.2
    elif profile.dynamic_range_db < 20:
        score += 0.1

    # Voice count contribution
    if profile.voice_count_estimate == 2:
        score += 0.2  # Most common for commentary
    elif 1 <= profile.voice_count_estimate <= 3:
        score += 0.15

    # Background audio contribution
    if profile.has_background_audio:
        score += 0.1

    # Pause duration (conversational pauses typical for commentary)
    if 1.0 <= profile.avg_pause_duration <= 3.0:
        score += 0.15

    # Clamp to valid range
    return min(max(score, 0.0), 1.0)
