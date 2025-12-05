"""Audio track classification module.

Provides functionality to classify audio tracks as original/dubbed and detect
commentary tracks via acoustic analysis.
"""

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
)

__all__ = [
    # Service functions
    "classify_track",
    "classify_file_tracks",
    # Metadata functions
    "get_original_language_from_metadata",
    "determine_original_track",
    # Models
    "AcousticProfile",
    "TrackClassificationResult",
    "ClassificationError",
    "InsufficientDataError",
]
