"""Audio track classification module.

Provides functionality to classify audio tracks as original/dubbed and detect
commentary tracks via acoustic analysis.
"""

from .acoustic import (
    AcousticAnalyzer,
    extract_acoustic_profile,
    get_commentary_confidence,
    is_commentary_by_acoustic,
)
from .metadata import (
    determine_original_track,
    get_original_language_from_metadata,
)
from .models import (
    AcousticProfile,
    ClassificationError,
    InsufficientDataError,
    TrackClassificationResult,
)
from .service import (
    classify_file_tracks,
    classify_track,
    detect_commentary,
)

__all__ = [
    # Service functions
    "classify_track",
    "classify_file_tracks",
    "detect_commentary",
    # Metadata functions
    "get_original_language_from_metadata",
    "determine_original_track",
    # Acoustic functions
    "extract_acoustic_profile",
    "is_commentary_by_acoustic",
    "get_commentary_confidence",
    "AcousticAnalyzer",
    # Models
    "AcousticProfile",
    "TrackClassificationResult",
    "ClassificationError",
    "InsufficientDataError",
]
