"""Filename parsing for metadata extraction.

This module provides regex-based parsing of media filenames to extract
metadata like title, year, series, season, episode, resolution, etc.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedMetadata:
    """Metadata parsed from filename.

    Contains all fields that can be extracted from a media filename,
    with confidence scoring to indicate parsing quality.
    """

    original_filename: str

    # Parsed fields (None if not found)
    title: str | None = None
    year: int | None = None
    series: str | None = None
    season: int | None = None
    episode: int | None = None
    resolution: str | None = None
    codec: str | None = None
    source: str | None = None

    # Parsing metadata
    pattern_matched: str | None = None  # Pattern name that matched
    confidence: float = 0.0  # 0.0-1.0

    @property
    def is_tv_show(self) -> bool:
        """True if parsed as a TV show (has season/episode)."""
        return self.season is not None or self.episode is not None

    @property
    def is_movie(self) -> bool:
        """True if parsed as a movie (has year, no season/episode)."""
        return self.year is not None and not self.is_tv_show

    def as_dict(self) -> dict[str, str]:
        """Convert to dictionary for template rendering.

        Returns:
            Dictionary with string values for all available fields.
        """
        result = {}
        if self.title:
            result["title"] = self.title
        if self.year:
            result["year"] = str(self.year)
        if self.series:
            result["series"] = self.series
        if self.season is not None:
            result["season"] = f"{self.season:02d}"
        if self.episode is not None:
            result["episode"] = f"{self.episode:02d}"
        if self.resolution:
            result["resolution"] = self.resolution
        if self.codec:
            result["codec"] = self.codec
        if self.source:
            result["source"] = self.source
        return result


# Movie patterns
# Movie.Name.2023.1080p.BluRay.x264-GROUP.mkv
# Movie Name (2023) [1080p].mkv
# Movie.Name.2023.mkv
MOVIE_PATTERNS = [
    # Standard scene naming: Movie.Name.2023.1080p.BluRay.x264-GROUP
    (
        r"^(?P<title>.+?)\.(?P<year>\d{4})"
        r"(?:\.(?P<resolution>\d{3,4}p))?"
        r"(?:\.(?P<source>BluRay|WEB-DL|WEBRip|HDRip|DVDRip|BDRip|HDTV))?"
        r"(?:\.(?P<codec>x264|x265|h264|h265|HEVC|AV1))?",
        "scene_movie",
    ),
    # Movie Name (2023) [1080p] format
    (
        r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*"
        r"(?:\[(?P<resolution>\d{3,4}p)\])?",
        "paren_movie",
    ),
    # Simple: Movie.Name.2023.mkv
    (r"^(?P<title>.+?)\.(?P<year>\d{4})(?:\.|\s|$)", "simple_movie"),
    # Title with year in middle
    (r"^(?P<title>.+?)\s*-?\s*(?P<year>\d{4})(?:\s|$)", "dash_movie"),
]

# TV Show patterns
# Series.Name.S01E02.Episode.Title.720p.WEB-DL.mkv
# Series Name - S01E02 - Episode Title.mkv
# Series Name 1x02 Episode Title.mkv
TV_PATTERNS = [
    # Series Name - S01E02 - Episode Title format (more specific, check first)
    (
        r"^(?P<series>.+?)\s+-\s+"
        r"S(?P<season>\d{1,2})E(?P<episode>\d{1,3})"
        r"(?:\s+-\s+(?P<title>[^.]+))?",
        "dash_sxxexx",
    ),
    # Standard S01E02 format with optional episode title
    (
        r"^(?P<series>.+?)[.\s]+"
        r"S(?P<season>\d{1,2})E(?P<episode>\d{1,3})"
        r"(?:[.\s]+(?P<title>[^.\d][^.]*?))?"
        r"(?:[.\s]+(?P<resolution>\d{3,4}p))?"
        r"(?:[.\s]+(?P<source>WEB-DL|WEBRip|HDTV|BluRay|DVDRip))?"
        r"(?:[.\s]+(?P<codec>x264|x265|h264|h265|HEVC))?",
        "sxxexx",
    ),
    # 1x02 format (with space or dot before season)
    (
        r"^(?P<series>.+?)[.\s]"
        r"(?P<season>\d{1,2})x(?P<episode>\d{1,3})"
        r"(?:[.\s]+(?P<title>.+?))?(?=[.\s]+\d{3,4}p|$)",
        "nxnn",
    ),
    # Season Episode (no S prefix): Series Name 102.mkv or Series.Name.102.mkv
    (
        r"^(?P<series>.+?)[.\s]+"
        r"(?P<season>\d)(?P<episode>\d{2})(?:[.\s]|$)",
        "combined",
    ),
]

# Resolution patterns
RESOLUTION_PATTERN = re.compile(r"(\d{3,4}p|4K|8K)", re.IGNORECASE)

# Source patterns
SOURCE_PATTERN = re.compile(
    r"(BluRay|BDRip|WEB-DL|WEBRip|HDRip|DVDRip|HDTV|PDTV|DVDScr|CAM|TS)",
    re.IGNORECASE,
)

# Codec patterns
CODEC_PATTERN = re.compile(r"(x264|x265|h\.?264|h\.?265|HEVC|AV1|VP9)", re.IGNORECASE)


def _clean_title(title: str) -> str:
    """Clean up a title by replacing dots/underscores with spaces.

    Args:
        title: Raw title string.

    Returns:
        Cleaned title string.
    """
    # Replace dots and underscores with spaces
    cleaned = re.sub(r"[._]+", " ", title)
    # Remove trailing/leading whitespace
    cleaned = cleaned.strip()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_additional_metadata(
    filename: str, metadata: ParsedMetadata
) -> ParsedMetadata:
    """Extract resolution, source, codec if not already found.

    Args:
        filename: Original filename.
        metadata: Partially filled metadata.

    Returns:
        Updated metadata with additional fields.
    """
    # Try to extract resolution if not found
    if not metadata.resolution:
        match = RESOLUTION_PATTERN.search(filename)
        if match:
            metadata.resolution = match.group(1).casefold()
            if metadata.resolution in ("4k", "8k"):
                metadata.resolution = metadata.resolution.upper()

    # Try to extract source if not found
    if not metadata.source:
        match = SOURCE_PATTERN.search(filename)
        if match:
            metadata.source = match.group(1)

    # Try to extract codec if not found
    if not metadata.codec:
        match = CODEC_PATTERN.search(filename)
        if match:
            codec = match.group(1).casefold()
            # Normalize codec names
            if codec in ("h264", "h.264"):
                metadata.codec = "h264"
            elif codec in ("h265", "h.265", "hevc"):
                metadata.codec = "hevc"
            else:
                metadata.codec = codec

    return metadata


def parse_movie_filename(filename: str) -> ParsedMetadata | None:
    """Try to parse filename as a movie.

    Args:
        filename: Filename without extension.

    Returns:
        ParsedMetadata if matched, None otherwise.
    """
    for pattern, pattern_name in MOVIE_PATTERNS:
        match = re.match(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groupdict()
            res = groups.get("resolution")
            metadata = ParsedMetadata(
                original_filename=filename,
                title=_clean_title(groups.get("title", "")),
                year=int(groups["year"]) if groups.get("year") else None,
                resolution=res.casefold() if res else None,
                source=groups.get("source"),
                codec=groups.get("codec"),
                pattern_matched=pattern_name,
                confidence=0.8 if groups.get("year") else 0.5,
            )
            return _extract_additional_metadata(filename, metadata)
    return None


def parse_tv_filename(filename: str) -> ParsedMetadata | None:
    """Try to parse filename as a TV show episode.

    Args:
        filename: Filename without extension.

    Returns:
        ParsedMetadata if matched, None otherwise.
    """
    for pattern, pattern_name in TV_PATTERNS:
        match = re.match(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groupdict()
            res = groups.get("resolution")
            # Handle title that might be None from regex group
            raw_title = groups.get("title")
            title = _clean_title(raw_title) if raw_title else None
            metadata = ParsedMetadata(
                original_filename=filename,
                series=_clean_title(groups.get("series") or ""),
                season=int(groups["season"]) if groups.get("season") else None,
                episode=int(groups["episode"]) if groups.get("episode") else None,
                title=title or None,
                resolution=res.casefold() if res else None,
                source=groups.get("source"),
                codec=groups.get("codec"),
                pattern_matched=pattern_name,
                confidence=(
                    0.9 if groups.get("season") and groups.get("episode") else 0.6
                ),
            )
            return _extract_additional_metadata(filename, metadata)
    return None


def parse_filename(path: Path | str) -> ParsedMetadata:
    """Parse a media filename to extract metadata.

    Tries TV show patterns first, then movie patterns.
    Returns a ParsedMetadata object even if parsing fails
    (with confidence=0).

    Args:
        path: Path to media file or filename string.

    Returns:
        ParsedMetadata with extracted information.
    """
    if isinstance(path, Path):
        filename = path.stem  # Filename without extension
    else:
        # Handle string path
        filename = Path(path).stem

    # Try TV show patterns first (more specific)
    result = parse_tv_filename(filename)
    if result:
        return result

    # Try movie patterns
    result = parse_movie_filename(filename)
    if result:
        return result

    # No pattern matched - return basic metadata
    return ParsedMetadata(
        original_filename=filename,
        title=_clean_title(filename),
        confidence=0.0,
    )
