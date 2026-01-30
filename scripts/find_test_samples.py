#!/usr/bin/env python3
"""Find a minimal set of video files from the VPO library covering maximum diversity.

Uses a greedy set-cover algorithm to select files that span the widest range
of containers, codecs, channel layouts, resolutions, and other VPO-relevant
characteristics. Optionally copies selected files to a test directory.

Usage:
    python scripts/find_test_samples.py [OPTIONS]

Options:
    --db PATH          Database path (default: ~/.vpo/library.db)
    --copy-to DIR      Copy selected files to this directory
    --max-files N      Maximum number of files to select
    --max-size SIZE    Maximum total size (e.g., "10GB", "500MB")
    --verbose          Show detailed per-file track listing
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src/ to path so we can import vpo modules when running from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vpo.core import (
    AUDIO_CODEC_ALIASES,
    SUBTITLE_CODEC_ALIASES,
    VIDEO_CODEC_ALIASES,
    format_file_size,
    get_resolution_label,
    normalize_codec,
)
from vpo.db.connection import get_connection, get_default_db_path
from vpo.policy.parsing import parse_file_size

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryTag:
    group: str  # e.g., "container", "video_codec"
    value: str  # e.g., "mkv", "hevc"


@dataclass(frozen=True)
class FileCandidate:
    file_id: int
    path: str
    filename: str
    size_bytes: int
    tags: frozenset[CategoryTag]


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

CATEGORY_GROUPS: dict[str, list[str]] = {
    "container": ["mkv", "mp4", "avi", "mov", "webm", "m2ts", "ts", "wmv", "flv"],
    "video_codec": ["h264", "hevc", "vp9", "av1", "mpeg4", "mpeg2video", "vc1"],
    "audio_codec": [
        "aac",
        "ac3",
        "eac3",
        "truehd",
        "dts",
        "dts-hd",
        "flac",
        "opus",
        "mp3",
        "pcm",
        "vorbis",
        "alac",
    ],
    "audio_channels": ["mono", "stereo", "5.1", "7.1"],
    "subtitle_codec": ["subrip", "ass", "pgs", "dvdsub", "mov_text", "webvtt"],
    "resolution": ["480p", "720p", "1080p", "1440p", "4K"],
    "hdr": ["hdr"],
    "multi_audio": ["3+_audio_tracks", "5+_audio_tracks"],
    "multi_subtitle": ["3+_subtitle_tracks", "5+_subtitle_tracks"],
    "multi_audio_language": ["3+_audio_languages", "5+_audio_languages"],
    "multi_subtitle_language": ["3+_subtitle_languages"],
    "attachment_type": ["image", "font"],
    "non_english_video": ["non_eng_video_language"],
}


def _build_reverse_alias_map(
    aliases: dict[str, frozenset[str]],
) -> dict[str, str]:
    """Build a map from every alias variant to its canonical name.

    For example, {"h265": "hevc", "h.265": "hevc", "hvc1": "hevc", ...}
    """
    reverse: dict[str, str] = {}
    seen_canonical: set[str] = set()
    for canonical, variants in aliases.items():
        if canonical in seen_canonical:
            continue
        seen_canonical.update(variants)
        for variant in variants:
            reverse[variant] = canonical
    return reverse


_VIDEO_REVERSE = _build_reverse_alias_map(VIDEO_CODEC_ALIASES)
_AUDIO_REVERSE = _build_reverse_alias_map(AUDIO_CODEC_ALIASES)
_SUBTITLE_REVERSE = _build_reverse_alias_map(SUBTITLE_CODEC_ALIASES)

# Container format normalization
_CONTAINER_ALIASES: dict[str, str] = {
    "matroska": "mkv",
    "matroska,webm": "mkv",
    "mov,mp4,m4a,3gp,3g2,mj2": "mp4",
    "mpegts": "ts",
    "mpeg-ts": "ts",
}

# Channel count to label
_CHANNEL_LABELS: dict[int, str] = {
    1: "mono",
    2: "stereo",
    6: "5.1",
    8: "7.1",
}

# Patterns for attachment classification
_FONT_EXTENSIONS = {"ttf", "otf", "woff", "woff2"}
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp"}
_FONT_CODECS = {"ttf", "otf", "application/x-truetype-font", "application/x-font-ttf"}
_IMAGE_CODECS = {"mjpeg", "png", "bmp", "gif", "image/jpeg", "image/png"}


# ---------------------------------------------------------------------------
# Tagging logic
# ---------------------------------------------------------------------------


def _normalize_container(
    container_format: str | None, extension: str | None
) -> str | None:
    """Normalize a container format string to a short label."""
    raw = (container_format or "").casefold().strip()
    if raw in _CONTAINER_ALIASES:
        return _CONTAINER_ALIASES[raw]
    # Try the raw value if it's in our known list
    if raw in {v for v in CATEGORY_GROUPS["container"]}:
        return raw
    # Fall back to extension
    ext = (extension or "").casefold().strip().lstrip(".")
    if ext in {v for v in CATEGORY_GROUPS["container"]}:
        return ext
    # Last resort: return raw if non-empty
    return raw if raw else ext if ext else None


def _classify_attachment(codec: str | None, title: str | None) -> str | None:
    """Classify an attachment track as 'image', 'font', or None."""
    codec_lower = (codec or "").casefold().strip()
    title_lower = (title or "").casefold().strip()

    if codec_lower in _FONT_CODECS:
        return "font"
    if codec_lower in _IMAGE_CODECS:
        return "image"

    # Check title/filename for extension hints
    for ext in _FONT_EXTENSIONS:
        if title_lower.endswith(f".{ext}"):
            return "font"
    for ext in _IMAGE_EXTENSIONS:
        if title_lower.endswith(f".{ext}"):
            return "image"

    return None


def _tag_file(
    file_row: sqlite3.Row,
    tracks: list[sqlite3.Row],
) -> frozenset[CategoryTag]:
    """Assign category tags to a file based on its metadata and tracks."""
    tags: set[CategoryTag] = set()

    # Container
    container = _normalize_container(
        file_row["container_format"], file_row["extension"]
    )
    if container:
        tags.add(CategoryTag("container", container))

    audio_tracks = [t for t in tracks if t["track_type"] == "audio"]
    video_tracks = [t for t in tracks if t["track_type"] == "video"]
    subtitle_tracks = [t for t in tracks if t["track_type"] == "subtitle"]
    attachment_tracks = [t for t in tracks if t["track_type"] == "attachment"]

    # Video codec
    for t in video_tracks:
        raw = normalize_codec(t["codec"])
        canonical = _VIDEO_REVERSE.get(raw, raw)
        if canonical and canonical in CATEGORY_GROUPS["video_codec"]:
            tags.add(CategoryTag("video_codec", canonical))

    # Audio codec
    for t in audio_tracks:
        raw = normalize_codec(t["codec"])
        canonical = _AUDIO_REVERSE.get(raw, raw)
        if canonical and canonical in CATEGORY_GROUPS["audio_codec"]:
            tags.add(CategoryTag("audio_codec", canonical))

    # Audio channels
    for t in audio_tracks:
        ch = t["channels"]
        if ch and ch in _CHANNEL_LABELS:
            tags.add(CategoryTag("audio_channels", _CHANNEL_LABELS[ch]))

    # Subtitle codec
    for t in subtitle_tracks:
        raw = normalize_codec(t["codec"])
        canonical = _SUBTITLE_REVERSE.get(raw, raw)
        if canonical and canonical in CATEGORY_GROUPS["subtitle_codec"]:
            tags.add(CategoryTag("subtitle_codec", canonical))

    # Resolution
    for t in video_tracks:
        label = get_resolution_label(t["width"], t["height"])
        if label != "\u2014" and label in CATEGORY_GROUPS["resolution"]:
            tags.add(CategoryTag("resolution", label))

    # HDR
    for t in video_tracks:
        ct = (t["color_transfer"] or "").casefold()
        if "smpte2084" in ct or "arib-std-b67" in ct:
            tags.add(CategoryTag("hdr", "hdr"))
            break

    # Multi-audio track counts
    if len(audio_tracks) >= 5:
        tags.add(CategoryTag("multi_audio", "5+_audio_tracks"))
        tags.add(CategoryTag("multi_audio", "3+_audio_tracks"))
    elif len(audio_tracks) >= 3:
        tags.add(CategoryTag("multi_audio", "3+_audio_tracks"))

    # Multi-subtitle track counts
    if len(subtitle_tracks) >= 5:
        tags.add(CategoryTag("multi_subtitle", "5+_subtitle_tracks"))
        tags.add(CategoryTag("multi_subtitle", "3+_subtitle_tracks"))
    elif len(subtitle_tracks) >= 3:
        tags.add(CategoryTag("multi_subtitle", "3+_subtitle_tracks"))

    # Multi-audio languages
    audio_langs = {
        t["language"] for t in audio_tracks if t["language"] and t["language"] != "und"
    }
    if len(audio_langs) >= 5:
        tags.add(CategoryTag("multi_audio_language", "5+_audio_languages"))
        tags.add(CategoryTag("multi_audio_language", "3+_audio_languages"))
    elif len(audio_langs) >= 3:
        tags.add(CategoryTag("multi_audio_language", "3+_audio_languages"))

    # Multi-subtitle languages
    sub_langs = {
        t["language"]
        for t in subtitle_tracks
        if t["language"] and t["language"] != "und"
    }
    if len(sub_langs) >= 3:
        tags.add(CategoryTag("multi_subtitle_language", "3+_subtitle_languages"))

    # Attachment types
    for t in attachment_tracks:
        kind = _classify_attachment(t["codec"], t["title"])
        if kind:
            tags.add(CategoryTag("attachment_type", kind))

    # Non-English video language
    for t in video_tracks:
        lang = (t["language"] or "").casefold().strip()
        if lang and lang not in ("", "und", "eng"):
            tags.add(CategoryTag("non_english_video", "non_eng_video_language"))
            break

    return frozenset(tags)


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------


def _fetch_all_candidates(conn: sqlite3.Connection) -> list[FileCandidate]:
    """Fetch all scanned files and their tracks, returning tagged candidates."""
    # Query 1: all successfully scanned files
    files_cursor = conn.execute(
        "SELECT id, path, filename, size_bytes, container_format, extension "
        "FROM files WHERE scan_status = 'ok'"
    )
    files = files_cursor.fetchall()

    if not files:
        return []

    # Query 2: all tracks for those files
    tracks_cursor = conn.execute(
        "SELECT file_id, track_type, codec, language, channels, "
        "width, height, color_transfer, title "
        "FROM tracks WHERE file_id IN (SELECT id FROM files WHERE scan_status = 'ok') "
        "ORDER BY file_id, track_index"
    )
    all_tracks = tracks_cursor.fetchall()

    # Group tracks by file_id
    tracks_by_file: dict[int, list[sqlite3.Row]] = {}
    for track in all_tracks:
        fid = track["file_id"]
        tracks_by_file.setdefault(fid, []).append(track)

    # Tag each file
    candidates = []
    for f in files:
        file_tracks = tracks_by_file.get(f["id"], [])
        tags = _tag_file(f, file_tracks)
        candidates.append(
            FileCandidate(
                file_id=f["id"],
                path=f["path"],
                filename=f["filename"],
                size_bytes=f["size_bytes"],
                tags=tags,
            )
        )

    return candidates


# ---------------------------------------------------------------------------
# Greedy set-cover selection
# ---------------------------------------------------------------------------


def _greedy_select(
    candidates: list[FileCandidate],
    max_files: int | None,
    max_size_bytes: int | None,
) -> list[FileCandidate]:
    """Select a minimal set of files covering the most category tags."""
    # Build the universe of all tags that appear in at least one file
    universe: set[CategoryTag] = set()
    for c in candidates:
        universe.update(c.tags)

    covered: set[CategoryTag] = set()
    selected: list[FileCandidate] = []
    remaining = set(range(len(candidates)))
    total_size = 0

    while universe - covered:
        if max_files is not None and len(selected) >= max_files:
            break

        best_idx: int | None = None
        best_new_count = 0
        best_total_tags = 0

        for idx in remaining:
            c = candidates[idx]

            # Check size constraint
            if (
                max_size_bytes is not None
                and total_size + c.size_bytes > max_size_bytes
            ):
                continue

            new_tags = c.tags - covered
            new_count = len(new_tags)

            if new_count > best_new_count or (
                new_count == best_new_count and len(c.tags) > best_total_tags
            ):
                best_idx = idx
                best_new_count = new_count
                best_total_tags = len(c.tags)

        if best_idx is None:
            # No file fits constraints or all remaining add zero new tags
            break

        c = candidates[best_idx]
        selected.append(c)
        covered.update(c.tags)
        remaining.discard(best_idx)
        total_size += c.size_bytes

    return selected


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _count_files_with_tag(
    tag: CategoryTag,
    candidates: list[FileCandidate],
) -> int:
    """Count how many candidates have a given tag."""
    return sum(1 for c in candidates if tag in c.tags)


def _format_report(
    candidates: list[FileCandidate],
    selected: list[FileCandidate],
    verbose: bool,
) -> str:
    """Build the full text report."""
    lines: list[str] = []

    # All tags present in any candidate
    all_tags: set[CategoryTag] = set()
    for c in candidates:
        all_tags.update(c.tags)

    # All defined tags (from CATEGORY_GROUPS)
    defined_tags: set[CategoryTag] = set()
    for group, values in CATEGORY_GROUPS.items():
        for v in values:
            defined_tags.add(CategoryTag(group, v))

    covered_tags = {tag for s in selected for tag in s.tags}
    total_defined = len(defined_tags)
    total_covered = len(covered_tags)
    total_size = sum(s.size_bytes for s in selected)

    # Header
    lines.append("=== VPO Test Sample Finder ===")
    lines.append(
        f"Files scanned: {len(candidates):,} | "
        f"Categories defined: {total_defined} | "
        f"Covered: {total_covered} ({100 * total_covered / total_defined:.1f}%)"
        if total_defined > 0
        else f"Files scanned: {len(candidates):,} | Categories defined: 0"
    )
    lines.append("")

    # Build a map from tag -> first selected file that covers it
    tag_to_selected: dict[CategoryTag, FileCandidate] = {}
    for s in selected:
        for tag in s.tags:
            if tag not in tag_to_selected:
                tag_to_selected[tag] = s

    # Category coverage
    lines.append("=== Category Coverage ===")
    for group, values in CATEGORY_GROUPS.items():
        lines.append(f"{group}:")
        for v in values:
            tag = CategoryTag(group, v)
            if tag in covered_tags:
                src = tag_to_selected[tag]
                match_count = _count_files_with_tag(tag, candidates)
                lines.append(
                    f"  [x] {v:<24} <- {src.filename} ({match_count} files match)"
                )
            elif tag in all_tags:
                match_count = _count_files_with_tag(tag, candidates)
                lines.append(f"  [ ] {v:<24} (available, {match_count} files match)")
            else:
                lines.append(f"  [ ] {v:<24} (not in library)")
        lines.append("")

    # Selected files
    size_str = format_file_size(total_size)
    lines.append(f"=== Selected Files ({len(selected)} files, {size_str}) ===")
    for i, s in enumerate(selected, 1):
        tag_labels = sorted(t.value for t in s.tags)
        lines.append(f"  {i}. {s.filename} ({format_file_size(s.size_bytes)})")
        lines.append(f"     {s.path}")
        lines.append(f"     Tags: {', '.join(tag_labels)}")

        if verbose:
            lines.append(f"     file_id={s.file_id}")

        lines.append("")

    # Missing categories
    missing_by_group: dict[str, list[str]] = {}
    for group, values in CATEGORY_GROUPS.items():
        missing = [v for v in values if CategoryTag(group, v) not in covered_tags]
        if missing:
            missing_by_group[group] = missing

    if missing_by_group:
        lines.append("=== Missing Categories ===")
        for group, missing in missing_by_group.items():
            lines.append(f"  {group}: {', '.join(missing)}")
        lines.append("")

    return "\n".join(lines)


def _format_verbose_tracks(
    conn: sqlite3.Connection,
    selected: list[FileCandidate],
) -> str:
    """Fetch and format detailed track info for selected files."""
    lines: list[str] = []
    file_ids = [s.file_id for s in selected]
    if not file_ids:
        return ""

    placeholders = ",".join("?" * len(file_ids))
    cursor = conn.execute(
        f"SELECT file_id, track_index, track_type, codec, language, "
        f"channels, width, height, color_transfer, title "
        f"FROM tracks WHERE file_id IN ({placeholders}) "
        f"ORDER BY file_id, track_index",
        file_ids,
    )
    tracks = cursor.fetchall()

    tracks_by_file: dict[int, list[sqlite3.Row]] = {}
    for t in tracks:
        tracks_by_file.setdefault(t["file_id"], []).append(t)

    lines.append("=== Detailed Track Listing ===")
    for s in selected:
        lines.append(f"  {s.filename}:")
        for t in tracks_by_file.get(s.file_id, []):
            parts = [f"#{t['track_index']}", t["track_type"]]
            if t["codec"]:
                parts.append(t["codec"])
            if t["language"]:
                parts.append(t["language"])
            if t["channels"]:
                parts.append(f"{t['channels']}ch")
            if t["width"] and t["height"]:
                parts.append(f"{t['width']}x{t['height']}")
            if t["color_transfer"]:
                parts.append(f"ct={t['color_transfer']}")
            if t["title"]:
                title = t["title"]
                if len(title) > 40:
                    title = title[:37] + "..."
                parts.append(f'"{title}"')
            lines.append(f"    {' | '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File copy
# ---------------------------------------------------------------------------


def _copy_files(selected: list[FileCandidate], target_dir: Path) -> None:
    """Copy selected files to target directory with progress output."""
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Copying {len(selected)} files to {target_dir} ===")
    for i, s in enumerate(selected, 1):
        src = Path(s.path)
        dst = target_dir / s.filename

        if not src.exists():
            print(f"  [{i}/{len(selected)}] SKIP (missing): {s.filename}")
            continue

        # Handle filename collisions
        if dst.exists():
            stem = dst.stem
            suffix = dst.suffix
            counter = 1
            while dst.exists():
                dst = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        size_label = format_file_size(s.size_bytes)
        print(
            f"  [{i}/{len(selected)}] {s.filename} ({size_label})...",
            end="",
            flush=True,
        )
        try:
            shutil.copy2(str(src), str(dst))
            print(" done")
        except OSError as e:
            print(f" ERROR: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find a minimal set of video files covering maximum diversity.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: ~/.vpo/library.db)",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        default=None,
        help="Copy selected files to this directory",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to select",
    )
    parser.add_argument(
        "--max-size",
        type=str,
        default=None,
        help='Maximum total size (e.g., "10GB", "500MB")',
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed per-file track listing",
    )
    args = parser.parse_args()

    db_path = args.db or get_default_db_path()

    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        return 1

    # Parse --max-size
    max_size_bytes: int | None = None
    if args.max_size:
        max_size_bytes = parse_file_size(args.max_size)
        if max_size_bytes is None:
            print(
                f'Error: invalid size format "{args.max_size}". '
                f"Use e.g. 500MB, 10GB, 1TB.",
                file=sys.stderr,
            )
            return 2

    try:
        with get_connection(db_path) as conn:
            candidates = _fetch_all_candidates(conn)

            if not candidates:
                print("No scanned files found in the database.")
                return 0

            selected = _greedy_select(candidates, args.max_files, max_size_bytes)

            report = _format_report(candidates, selected, args.verbose)
            print(report)

            if args.verbose and selected:
                detail = _format_verbose_tracks(conn, selected)
                print(detail)

    except sqlite3.OperationalError as e:
        if "locked" in str(e).casefold():
            print(
                "Error: database is locked. Another process may be using it.",
                file=sys.stderr,
            )
            return 1
        raise

    if args.copy_to and selected:
        _copy_files(selected, args.copy_to)

    return 0


if __name__ == "__main__":
    sys.exit(main())
