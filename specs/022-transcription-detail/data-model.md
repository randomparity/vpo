# Data Model: Transcription Detail View

**Feature**: 022-transcription-detail
**Date**: 2025-11-24

## Overview

This feature uses existing database tables without schema changes. New UI models are added for API responses and template rendering. The design extends the patterns established in 020-file-detail-view and 021-transcriptions-list.

## Existing Database Entities (No Changes)

### transcription_results (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Result identifier (used as URL parameter) |
| track_id | INTEGER FK UNIQUE | Reference to tracks.id |
| detected_language | TEXT | Detected language code (ISO 639) |
| confidence_score | REAL | 0.0-1.0 confidence value |
| track_type | TEXT | "main", "commentary", "alternate" |
| transcript_sample | TEXT | Transcription text sample |
| plugin_name | TEXT | Plugin that performed detection |
| created_at | TEXT | ISO-8601 UTC timestamp |
| updated_at | TEXT | ISO-8601 UTC timestamp |

### tracks (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Track identifier |
| file_id | INTEGER FK | Reference to files.id |
| track_index | INTEGER | Index within file (0-based) |
| track_type | TEXT | "video", "audio", "subtitle" |
| codec | TEXT | Codec name (e.g., "aac") |
| language | TEXT | Original language tag (ISO 639-2/B) |
| title | TEXT | Track title (may contain commentary keywords) |
| channels | INTEGER | Number of audio channels |
| channel_layout | TEXT | Channel layout string |
| is_default | INTEGER | 1 if default track |
| is_forced | INTEGER | 1 if forced track |

### files (existing)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | File identifier |
| path | TEXT UNIQUE | Full file path |
| filename | TEXT | Filename only |

## New UI Models

### TranscriptionDetailItem

Full transcription data for the detail view API response.

```python
@dataclass
class TranscriptionDetailItem:
    """Full transcription data for detail view.

    Attributes:
        id: Transcription result ID (used in URL).
        track_id: Associated track ID.
        detected_language: Detected language code.
        confidence_score: Confidence as float (0.0-1.0).
        confidence_level: Categorical level ("high", "medium", "low").
        track_classification: Track type ("main", "commentary", "alternate").
        transcript_sample: The transcription text.
        transcript_html: HTML with keyword highlighting (for commentary).
        transcript_truncated: True if text exceeds display threshold.
        plugin_name: Name of transcription plugin.
        created_at: ISO-8601 UTC timestamp.
        updated_at: ISO-8601 UTC timestamp.
        # Track metadata
        track_index: Track index within file (0-based).
        track_codec: Audio codec name.
        original_language: Original language tag from track.
        track_title: Track title (may indicate commentary).
        channels: Number of audio channels.
        channel_layout: Human-readable layout (e.g., "5.1").
        is_default: Whether track is marked as default.
        is_forced: Whether track is marked as forced.
        # Classification reasoning
        is_commentary: True if classified as commentary.
        classification_source: "metadata" | "transcript" | None.
        matched_keywords: List of matched commentary keywords/patterns.
        # Parent file info
        file_id: Parent file ID.
        filename: Parent filename.
        file_path: Parent file path.
    """
    # Transcription data
    id: int
    track_id: int
    detected_language: str | None
    confidence_score: float
    confidence_level: str  # "high", "medium", "low"
    track_classification: str  # "main", "commentary", "alternate"
    transcript_sample: str | None
    transcript_html: str | None  # HTML with keyword highlighting
    transcript_truncated: bool
    plugin_name: str
    created_at: str
    updated_at: str
    # Track metadata
    track_index: int
    track_codec: str | None
    original_language: str | None
    track_title: str | None
    channels: int | None
    channel_layout: str | None
    is_default: bool
    is_forced: bool
    # Classification reasoning
    is_commentary: bool
    classification_source: str | None  # "metadata", "transcript", or None
    matched_keywords: list[str]
    # Parent file
    file_id: int
    filename: str
    file_path: str

    @property
    def confidence_percent(self) -> int:
        """Return confidence as integer percentage (0-100)."""
        return int(self.confidence_score * 100)

    @property
    def is_low_confidence(self) -> bool:
        """Return True if confidence < 0.3 (warning threshold)."""
        return self.confidence_score < 0.3

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "track_id": self.track_id,
            "detected_language": self.detected_language,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "confidence_percent": self.confidence_percent,
            "is_low_confidence": self.is_low_confidence,
            "track_classification": self.track_classification,
            "transcript_sample": self.transcript_sample,
            "transcript_html": self.transcript_html,
            "transcript_truncated": self.transcript_truncated,
            "plugin_name": self.plugin_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "track_index": self.track_index,
            "track_codec": self.track_codec,
            "original_language": self.original_language,
            "track_title": self.track_title,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "is_default": self.is_default,
            "is_forced": self.is_forced,
            "is_commentary": self.is_commentary,
            "classification_source": self.classification_source,
            "matched_keywords": self.matched_keywords,
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
        }
```

### TranscriptionDetailResponse

API response wrapper for JSON endpoint.

```python
@dataclass
class TranscriptionDetailResponse:
    """API response for /api/transcriptions/{id}.

    Attributes:
        transcription: The transcription detail data.
    """
    transcription: TranscriptionDetailItem

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"transcription": self.transcription.to_dict()}
```

### TranscriptionDetailContext

Template context for server-side rendering.

```python
@dataclass
class TranscriptionDetailContext:
    """Template context for transcription_detail.html.

    Attributes:
        transcription: The transcription detail item.
        back_url: URL to return to previous page.
        back_label: Label for back link ("File Detail" or "Transcriptions").
    """
    transcription: TranscriptionDetailItem
    back_url: str
    back_label: str

    @classmethod
    def from_transcription_and_request(
        cls,
        transcription: TranscriptionDetailItem,
        referer: str | None,
    ) -> TranscriptionDetailContext:
        """Create context preserving navigation state.

        Args:
            transcription: The transcription detail item.
            referer: HTTP Referer header value, if present.

        Returns:
            TranscriptionDetailContext with appropriate back URL.
        """
        # Default: back to parent file detail
        back_url = f"/library/{transcription.file_id}"
        back_label = "File Detail"

        # If came from transcriptions list, go back there
        if referer:
            if "/transcriptions" in referer and f"/transcriptions/{transcription.id}" not in referer:
                if referer.startswith("/"):
                    back_url = referer
                else:
                    idx = referer.find("/transcriptions")
                    if idx != -1:
                        back_url = referer[idx:]
                back_label = "Transcriptions"

        return cls(
            transcription=transcription,
            back_url=back_url,
            back_label=back_label,
        )
```

## New Database Query Function

### get_transcription_detail()

Query function to retrieve full transcription data with track and file info.

```python
def get_transcription_detail(
    conn: sqlite3.Connection,
    transcription_id: int,
) -> dict | None:
    """Get transcription detail with track and file info.

    Args:
        conn: Database connection.
        transcription_id: ID of transcription_results record.

    Returns:
        Dictionary with transcription, track, and file data:
        {
            "id": int,
            "track_id": int,
            "detected_language": str | None,
            "confidence_score": float,
            "track_type": str,
            "transcript_sample": str | None,
            "plugin_name": str,
            "created_at": str,
            "updated_at": str,
            "track_index": int,
            "track_media_type": str,
            "codec": str | None,
            "original_language": str | None,
            "title": str | None,
            "channels": int | None,
            "channel_layout": str | None,
            "is_default": int,
            "is_forced": int,
            "file_id": int,
            "filename": str,
            "path": str,
        }
        Returns None if transcription not found.
    """
    cursor = conn.execute(
        """
        SELECT
            tr.id,
            tr.track_id,
            tr.detected_language,
            tr.confidence_score,
            tr.track_type,
            tr.transcript_sample,
            tr.plugin_name,
            tr.created_at,
            tr.updated_at,
            t.track_index,
            t.track_type AS track_media_type,
            t.codec,
            t.language AS original_language,
            t.title,
            t.channels,
            t.channel_layout,
            t.is_default,
            t.is_forced,
            f.id AS file_id,
            f.filename,
            f.path
        FROM transcription_results tr
        JOIN tracks t ON tr.track_id = t.id
        JOIN files f ON t.file_id = f.id
        WHERE tr.id = ?
        """,
        (transcription_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None
```

## Helper Functions

### get_classification_reasoning()

Determine how a track was classified as commentary.

```python
def get_classification_reasoning(
    track_title: str | None,
    transcript_sample: str | None,
    track_type: str,
) -> tuple[str | None, list[str]]:
    """Determine classification source and matched keywords.

    Args:
        track_title: Track title from metadata.
        transcript_sample: Transcription text sample.
        track_type: Track classification ("main", "commentary", "alternate").

    Returns:
        Tuple of (classification_source, matched_keywords):
        - classification_source: "metadata", "transcript", or None
        - matched_keywords: List of matched keywords/patterns
    """
    from vpo.transcription.models import (
        COMMENTARY_KEYWORDS,
        COMMENTARY_TRANSCRIPT_PATTERNS,
        is_commentary_by_metadata,
    )
    import re

    if track_type != "commentary":
        return None, []

    matched = []

    # Check metadata first
    if track_title and is_commentary_by_metadata(track_title):
        title_lower = track_title.lower()
        for keyword in COMMENTARY_KEYWORDS:
            if keyword in title_lower:
                matched.append(f"Title contains: '{keyword}'")
        return "metadata", matched

    # Check transcript patterns
    if transcript_sample:
        sample_lower = transcript_sample.lower()
        for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
            if re.search(pattern, sample_lower, re.IGNORECASE):
                # Convert regex to readable form
                readable = pattern.replace(r"\b", "").replace("\\", "")
                matched.append(f"Pattern: {readable}")
        if matched:
            return "transcript", matched

    return None, []
```

### highlight_keywords_in_transcript()

Generate HTML with highlighted keywords for commentary tracks.

```python
import html
import re

# Max characters to display before truncation
TRANSCRIPT_DISPLAY_LIMIT = 10000

def highlight_keywords_in_transcript(
    transcript: str | None,
    track_type: str,
) -> tuple[str | None, bool]:
    """Generate HTML with highlighted commentary keywords.

    Args:
        transcript: Raw transcript text.
        track_type: Track classification.

    Returns:
        Tuple of (html_content, is_truncated):
        - html_content: HTML-escaped text with <mark> tags, or None
        - is_truncated: True if text was truncated
    """
    if not transcript:
        return None, False

    from vpo.transcription.models import (
        COMMENTARY_TRANSCRIPT_PATTERNS,
    )

    # Truncate if too long
    is_truncated = len(transcript) > TRANSCRIPT_DISPLAY_LIMIT
    display_text = transcript[:TRANSCRIPT_DISPLAY_LIMIT] if is_truncated else transcript

    # Escape HTML first
    escaped = html.escape(display_text)

    # Only highlight if commentary track
    if track_type != "commentary":
        return escaped, is_truncated

    # Apply highlighting for each pattern
    for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
        try:
            # Find matches and wrap with <mark>
            escaped = re.sub(
                f"({pattern})",
                r'<mark class="commentary-match">\1</mark>',
                escaped,
                flags=re.IGNORECASE,
            )
        except re.error:
            continue  # Skip invalid patterns

    return escaped, is_truncated
```

## Relationships

```
files (1) ─── (N) tracks (1) ─── (0..1) transcription_results
              │
              └── This feature displays one transcription_result
                  with its associated track and parent file info
```

## Validation Rules

1. **ID validation**: transcription_id must be a positive integer
2. **Confidence bounds**: 0.0 <= confidence_score <= 1.0 (enforced by DB constraint)
3. **Track type values**: "main", "commentary", "alternate" (enforced by DB constraint)

## State Transitions

No state transitions - this is a read-only view of existing data.

## Indexes Used

The query uses existing indexes:
- `transcription_results.id` (PK) - transcription lookup
- `tracks.id` (PK) - track join
- `files.id` (PK) - file join

No new indexes required.
