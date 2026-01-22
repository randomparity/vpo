"""Domain models and enums for Video Policy Orchestrator.

This package contains core domain types that are independent of the database layer:

- Domain models: TrackInfo, FileInfo, IntrospectionResult
- Domain enums: OriginalDubbedStatus, CommentaryStatus, TrackClassification,
  DetectionMethod
- Type aliases: PluginMetadataDict

Usage:
    from vpo.domain import TrackInfo, FileInfo, IntrospectionResult
    from vpo.domain import OriginalDubbedStatus, TrackClassification
"""

from .enums import (
    CommentaryStatus,
    DetectionMethod,
    OriginalDubbedStatus,
    TrackClassification,
)
from .models import (
    FileInfo,
    IntrospectionResult,
    PluginMetadataDict,
    TrackInfo,
)

__all__ = [
    # Models
    "TrackInfo",
    "FileInfo",
    "IntrospectionResult",
    # Type aliases
    "PluginMetadataDict",
    # Enums
    "OriginalDubbedStatus",
    "CommentaryStatus",
    "TrackClassification",
    "DetectionMethod",
]
