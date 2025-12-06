# Contract: Classification Service

**Feature**: 044-audio-track-classification
**Date**: 2025-12-05
**Module**: `track_classification/service.py`

## Overview

The classification service provides the core API for classifying audio tracks as original/dubbed and detecting commentary tracks.

---

## Public Functions

### classify_track

Classify a single audio track.

```python
def classify_track(
    track: TrackInfo,
    file_hash: str,
    plugin_metadata: dict | None = None,
    acoustic_analysis: bool = True,
    conn: sqlite3.Connection | None = None,
) -> TrackClassificationResult:
    """
    Classify an audio track as original/dubbed and commentary/main.

    Args:
        track: Track information from introspection.
        file_hash: Content hash of the file for cache validation.
        plugin_metadata: Optional Radarr/Sonarr metadata.
        acoustic_analysis: Whether to perform acoustic analysis.
        conn: Database connection for caching.

    Returns:
        TrackClassificationResult with classification and confidence.

    Raises:
        ClassificationError: If classification fails.
        InsufficientDataError: If track has insufficient data.
    """
```

**Caching Behavior**:
- Checks `track_classification_results` table for existing result
- Returns cached result if `file_hash` matches
- Re-analyzes if `file_hash` changed or no cached result

---

### classify_file_tracks

Classify all audio tracks in a file.

```python
def classify_file_tracks(
    file_path: Path,
    conn: sqlite3.Connection,
    plugin_metadata: dict | None = None,
    acoustic_analysis: bool = True,
) -> list[TrackClassificationResult]:
    """
    Classify all audio tracks in a media file.

    Args:
        file_path: Path to the media file.
        conn: Database connection.
        plugin_metadata: Optional Radarr/Sonarr metadata.
        acoustic_analysis: Whether to perform acoustic analysis.

    Returns:
        List of classification results, one per audio track.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ClassificationError: If classification fails.
    """
```

---

### get_track_classification

Retrieve cached classification result.

```python
def get_track_classification(
    track_id: int,
    conn: sqlite3.Connection,
) -> TrackClassificationResult | None:
    """
    Get cached classification result for a track.

    Args:
        track_id: Database ID of the track.
        conn: Database connection.

    Returns:
        Cached result or None if not classified.
    """
```

---

### invalidate_classification

Invalidate cached classification.

```python
def invalidate_classification(
    track_id: int,
    conn: sqlite3.Connection,
) -> bool:
    """
    Remove cached classification result for a track.

    Args:
        track_id: Database ID of the track.
        conn: Database connection.

    Returns:
        True if result was deleted, False if not found.
    """
```

---

## Error Types

### ClassificationError

Raised when classification cannot be completed.

```python
class ClassificationError(Exception):
    """Classification operation failed."""
    pass
```

### InsufficientDataError

Raised when track has insufficient data for classification.

```python
class InsufficientDataError(ClassificationError):
    """Track has insufficient data for reliable classification."""
    pass
```

---

## Usage Example

```python
from video_policy_orchestrator.track_classification.service import (
    classify_file_tracks,
    get_track_classification,
)
from video_policy_orchestrator.db import get_db_connection

# Classify all tracks
with get_db_connection() as conn:
    results = classify_file_tracks(
        Path("/path/to/movie.mkv"),
        conn,
        plugin_metadata={"radarr": {"original_language": "ja"}},
    )

    for result in results:
        print(f"Track {result.track_id}: {result.original_dubbed_status.value}")
        print(f"  Confidence: {result.confidence:.1%}")
        print(f"  Method: {result.detection_method.value}")
```

---

## Integration Points

### Policy Evaluator

```python
# In policy/evaluator.py
from track_classification.service import get_track_classification

def evaluate_with_classification(
    tracks: list[TrackInfo],
    conn: sqlite3.Connection,
) -> dict[int, TrackClassificationResult]:
    """Load classification results for tracks."""
    return {
        track.id: get_track_classification(track.id, conn)
        for track in tracks
        if track.id is not None
    }
```

### CLI Commands

```python
# In cli/inspect.py
from track_classification.service import classify_file_tracks

@click.option("--classify-tracks", is_flag=True)
def inspect(file_path, classify_tracks):
    if classify_tracks:
        results = classify_file_tracks(Path(file_path), conn)
        display_classification_results(results)
```
