"""Transcription view models.

This module defines models for transcription list and detail views,
including helper functions for formatting and highlighting.
"""

from __future__ import annotations

from dataclasses import dataclass

# Max characters to display before truncation
TRANSCRIPT_DISPLAY_LIMIT = 10000

# Max characters for regex highlighting (ReDoS protection)
# Skip highlighting for very long transcripts to prevent CPU exhaustion
TRANSCRIPT_HIGHLIGHT_LIMIT = 50000


def get_confidence_level(confidence: float | None) -> str | None:
    """Map confidence score to categorical level.

    Args:
        confidence: Average confidence score (0.0-1.0), or None.

    Returns:
        "high" if >= 0.8
        "medium" if >= 0.5 and < 0.8
        "low" if < 0.5
        None if confidence is None
    """
    if confidence is None:
        return None
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def format_detected_languages(languages_csv: str | None) -> list[str]:
    """Parse CSV language codes into list.

    Args:
        languages_csv: Comma-separated language codes from GROUP_CONCAT.

    Returns:
        List of unique language codes, or empty list.
    """
    if not languages_csv:
        return []
    return list(set(lang.strip() for lang in languages_csv.split(",") if lang.strip()))


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
    import re

    from vpo.transcription.models import (
        COMMENTARY_KEYWORDS,
        COMMENTARY_TRANSCRIPT_PATTERNS,
        is_commentary_by_metadata,
    )

    if track_type != "commentary":
        return None, []

    matched = []

    # Check metadata first
    if track_title and is_commentary_by_metadata(track_title):
        title_lower = track_title.casefold()
        for keyword in COMMENTARY_KEYWORDS:
            if keyword in title_lower:
                matched.append(f"Title contains: '{keyword}'")
        return "metadata", matched

    # Check transcript patterns
    if transcript_sample:
        sample_lower = transcript_sample.casefold()
        for pattern in COMMENTARY_TRANSCRIPT_PATTERNS:
            if re.search(pattern, sample_lower, re.IGNORECASE):
                # Convert regex to readable form
                readable = pattern.replace(r"\b", "").replace("\\", "")
                matched.append(f"Pattern: {readable}")
        if matched:
            return "transcript", matched

    return None, []


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

    Note:
        ReDoS protection: Regex highlighting is skipped for transcripts
        exceeding TRANSCRIPT_HIGHLIGHT_LIMIT to prevent CPU exhaustion.
    """
    import html
    import re

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

    # ReDoS protection: skip highlighting for very long transcripts
    if len(transcript) > TRANSCRIPT_HIGHLIGHT_LIMIT:
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
        except (re.error, RecursionError):
            continue  # Skip invalid patterns or catastrophic backtracking

    return escaped, is_truncated


@dataclass
class TranscriptionFilterParams:
    """Query parameters for /api/transcriptions.

    Attributes:
        show_all: If False (default), show only files with transcriptions.
                  If True, show all files.
        limit: Page size (1-100, default 50).
        offset: Pagination offset (>= 0, default 0).
    """

    show_all: bool = False
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, query: dict) -> TranscriptionFilterParams:
        """Create from request query dict with validation.

        Args:
            query: Query parameters from request.

        Returns:
            Validated TranscriptionFilterParams instance.
        """
        show_all = query.get("show_all", "").casefold() == "true"
        try:
            limit = max(1, min(100, int(query.get("limit", 50))))
        except (ValueError, TypeError):
            limit = 50
        try:
            offset = max(0, int(query.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0
        return cls(show_all=show_all, limit=limit, offset=offset)


@dataclass
class TranscriptionListItem:
    """File data for Transcriptions list.

    Attributes:
        id: Database file ID.
        filename: Short filename for display.
        path: Full file path (for tooltip).
        has_transcription: Whether file has any transcription results.
        detected_languages: List of detected language codes.
        confidence_level: Categorical level ("high", "medium", "low", or None).
        confidence_avg: Average confidence score (0.0-1.0), or None.
        transcription_count: Number of tracks with transcription results.
        scan_status: "ok" or "error".
    """

    id: int
    filename: str
    path: str
    has_transcription: bool
    detected_languages: list[str]
    confidence_level: str | None
    confidence_avg: float | None
    transcription_count: int
    scan_status: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "path": self.path,
            "has_transcription": self.has_transcription,
            "detected_languages": self.detected_languages,
            "confidence_level": self.confidence_level,
            "confidence_avg": self.confidence_avg,
            "transcription_count": self.transcription_count,
            "scan_status": self.scan_status,
        }


@dataclass
class TranscriptionListResponse:
    """API response for /api/transcriptions.

    Attributes:
        files: File items for current page.
        total: Total files matching filters.
        limit: Page size used.
        offset: Current offset.
        has_filters: True if show_all filter is active.
    """

    files: list[TranscriptionListItem]
    total: int
    limit: int
    offset: int
    has_filters: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": [f.to_dict() for f in self.files],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_filters": self.has_filters,
        }


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
        track_index: Track index within file (0-based).
        track_codec: Audio codec name.
        original_language: Original language tag from track.
        track_title: Track title (may indicate commentary).
        channels: Number of audio channels.
        channel_layout: Human-readable layout (e.g., "5.1").
        is_default: Whether track is marked as default.
        is_forced: Whether track is marked as forced.
        is_commentary: True if classified as commentary.
        classification_source: "metadata" | "transcript" | None.
        matched_keywords: List of matched commentary keywords/patterns.
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

    @staticmethod
    def _is_safe_back_url(url: str) -> bool:
        """Validate URL is safe for back navigation (prevent open redirect).

        Args:
            url: URL path to validate.

        Returns:
            True if URL is a safe internal path.
        """
        if not url or not isinstance(url, str):
            return False
        # Only allow relative paths starting with known safe prefixes
        safe_prefixes = ("/library/", "/library", "/transcriptions", "/")
        return url.startswith(safe_prefixes) and "//" not in url

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

        Note:
            Referer is validated to prevent open redirect attacks.
            Only paths starting with /library/ or /transcriptions are allowed.
        """
        # Default: back to parent file detail
        back_url = f"/library/{transcription.file_id}"
        back_label = "File Detail"

        # If came from transcriptions list, go back there
        if referer:
            # Extract path portion from referer (handles full URLs)
            extracted_path = None
            if referer.startswith("/"):
                extracted_path = referer
            else:
                idx = referer.find("/transcriptions")
                if idx != -1:
                    extracted_path = referer[idx:]

            # Validate and use if safe
            if (
                extracted_path
                and cls._is_safe_back_url(extracted_path)
                and "/transcriptions" in extracted_path
                and f"/transcriptions/{transcription.id}" not in extracted_path
            ):
                back_url = extracted_path
                back_label = "Transcriptions"

        return cls(
            transcription=transcription,
            back_url=back_url,
            back_label=back_label,
        )


def build_transcription_detail_item(data: dict) -> TranscriptionDetailItem:
    """Build TranscriptionDetailItem from database query result.

    This is a shared builder used by both HTML and API handlers.

    Args:
        data: Dictionary from get_transcription_detail() query.

    Returns:
        TranscriptionDetailItem ready for API/template use.
    """
    track_type = data["track_type"]
    transcript = data["transcript_sample"]

    # Get classification reasoning
    classification_source, matched_keywords = get_classification_reasoning(
        data["title"],
        transcript,
        track_type,
    )

    # Generate highlighted HTML
    transcript_html, transcript_truncated = highlight_keywords_in_transcript(
        transcript,
        track_type,
    )

    return TranscriptionDetailItem(
        id=data["id"],
        track_id=data["track_id"],
        detected_language=data["detected_language"],
        confidence_score=data["confidence_score"],
        confidence_level=get_confidence_level(data["confidence_score"]),
        track_classification=track_type,
        transcript_sample=transcript,
        transcript_html=transcript_html,
        transcript_truncated=transcript_truncated,
        plugin_name=data["plugin_name"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        track_index=data["track_index"],
        track_codec=data["codec"],
        original_language=data["original_language"],
        track_title=data["title"],
        channels=data["channels"],
        channel_layout=data["channel_layout"],
        is_default=bool(data["is_default"]),
        is_forced=bool(data["is_forced"]),
        is_commentary=track_type == "commentary",
        classification_source=classification_source,
        matched_keywords=matched_keywords,
        file_id=data["file_id"],
        filename=data["filename"],
        file_path=data["path"],
    )
