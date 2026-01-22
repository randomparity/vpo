"""Domain enums for Video Policy Orchestrator.

This module contains domain enums that are used across multiple VPO modules
for track classification and detection status.
"""

from enum import Enum


class TrackClassification(Enum):
    """Classification of audio track purpose.

    Detection priority:
    1. MUSIC/SFX: Identified by metadata keywords (title)
    2. NON_SPEECH: Detected via transcription analysis (no speech/low confidence)
    3. COMMENTARY: Identified by metadata keywords or transcript content
    4. ALTERNATE: Identified as non-main dialog track
    5. MAIN: Default for dialog tracks
    """

    MAIN = "main"  # Primary audio track with dialog
    COMMENTARY = "commentary"  # Director/cast commentary
    ALTERNATE = "alternate"  # Alternate mix with dialog
    MUSIC = "music"  # Score, soundtrack (metadata-identified)
    SFX = "sfx"  # Sound effects, ambient (metadata-identified)
    NON_SPEECH = "non_speech"  # Unlabeled track detected as no speech


class OriginalDubbedStatus(Enum):
    """Classification of audio track as original or dubbed.

    Determined by detection priority:
    1. External metadata (Radarr/Sonarr production country, TMDB)
    2. Track position heuristic (first audio track often original)
    3. Acoustic analysis (quality comparison)
    """

    ORIGINAL = "original"  # Track is the original theatrical audio
    DUBBED = "dubbed"  # Track is a dubbed version
    UNKNOWN = "unknown"  # Cannot determine original/dubbed status


class CommentaryStatus(Enum):
    """Classification of audio track as commentary or main content.

    Determined by:
    1. Metadata keywords (title contains "commentary")
    2. Acoustic analysis (speech density, dynamic range, voice count)
    """

    COMMENTARY = "commentary"  # Track contains commentary
    MAIN = "main"  # Track contains main audio content
    UNKNOWN = "unknown"  # Cannot determine commentary status


class DetectionMethod(Enum):
    """Method used to determine track classification.

    Indicates the signal source that determined the classification result.
    """

    METADATA = "metadata"  # Determined from external metadata (Radarr/Sonarr/TMDB)
    ACOUSTIC = "acoustic"  # Determined from acoustic analysis
    COMBINED = "combined"  # Multiple signals combined
    POSITION = "position"  # Determined from track position heuristic
