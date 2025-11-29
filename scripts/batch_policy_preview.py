#!/usr/bin/env python3
"""Batch policy preview tool.

Recursively scans a directory for video files and previews policy application
results for each file found.

Usage:
    python scripts/batch_policy_preview.py /videos --policy policy.yaml
    python scripts/batch_policy_preview.py /videos --policy policy.yaml -e mkv,mp4
    python scripts/batch_policy_preview.py /videos --policy policy.yaml --summary-only
    python scripts/batch_policy_preview.py /videos --policy policy.yaml -o results.txt
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TrackInfo:
    """Information about a track in the final output."""

    index: int
    track_type: str
    codec: str | None = None
    language: str | None = None
    title: str | None = None
    channels: int | None = None
    resolution: str | None = None
    action: str = "KEEP"  # KEEP or REMOVE


@dataclass
class ScanResult:
    """Result of scanning a single file."""

    file_path: Path
    success: bool
    output: str
    error: str | None = None
    has_changes: bool = False
    synthesis_planned: bool = False
    synthesis_skipped: bool = False
    skip_reason: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
    json_data: dict | None = None


@dataclass
class ScanSummary:
    """Summary of all scan results."""

    total_files: int = 0
    successful: int = 0
    failed: int = 0
    with_changes: int = 0
    synthesis_planned: int = 0
    synthesis_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def find_video_files(
    directory: Path,
    extensions: tuple[str, ...] = (".mkv", ".mp4", ".avi", ".m4v", ".webm"),
) -> list[Path]:
    """Recursively find all video files in a directory.

    Args:
        directory: Root directory to search.
        extensions: Tuple of file extensions to include.

    Returns:
        List of paths to video files, sorted alphabetically.
    """
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))
    return sorted(files)


def run_policy_preview(file_path: Path, policy_path: Path) -> ScanResult:
    """Run vpo apply --dry-run on a single file.

    Args:
        file_path: Path to the video file.
        policy_path: Path to the policy YAML file.

    Returns:
        ScanResult with the output and analysis.
    """
    cmd = [
        "uv",
        "run",
        "vpo",
        "apply",
        "--policy",
        str(policy_path),
        str(file_path),
        "--dry-run",
        "--json",
    ]

    try:
        result = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout + result.stderr
        success = result.returncode == 0

        # Parse JSON output
        json_data = None
        tracks: list[TrackInfo] = []
        has_changes = False
        synthesis_planned = False
        synthesis_skipped = False
        skip_reason = None

        if success and result.stdout.strip():
            try:
                json_data = json.loads(result.stdout)

                # Extract track dispositions
                plan = json_data.get("plan", {})
                track_dispositions = plan.get("track_dispositions", [])

                for disp in track_dispositions:
                    tracks.append(
                        TrackInfo(
                            index=disp.get("track_index", 0),
                            track_type=disp.get("track_type", "unknown"),
                            codec=disp.get("codec"),
                            language=disp.get("language"),
                            title=disp.get("title"),
                            channels=disp.get("channels"),
                            resolution=disp.get("resolution"),
                            action=disp.get("action", "KEEP"),
                        )
                    )

                # Determine if there are changes
                actions = plan.get("actions", [])
                tracks_removed = plan.get("tracks_removed", 0)
                has_changes = len(actions) > 0 or tracks_removed > 0

            except json.JSONDecodeError:
                # Fall back to text parsing if JSON fails
                pass

        # Fall back to text-based detection for synthesis info
        # (synthesis plan is not yet in JSON output)
        if "Tracks to create" in output:
            synthesis_planned = True
            has_changes = True
        if "SKIPPED" in output:
            synthesis_skipped = True
            if "Already exists" in output:
                skip_reason = "Already exists"
            elif "Condition not met" in output:
                skip_reason = "Condition not met"
            elif "No source track" in output:
                skip_reason = "No source track"
            elif "Would require upmix" in output:
                skip_reason = "Would require upmix"
            elif "Encoder not available" in output:
                skip_reason = "Encoder not available"

        return ScanResult(
            file_path=file_path,
            success=success,
            output=output,
            has_changes=has_changes,
            synthesis_planned=synthesis_planned,
            synthesis_skipped=synthesis_skipped,
            skip_reason=skip_reason,
            tracks=tracks,
            json_data=json_data,
        )

    except subprocess.TimeoutExpired:
        return ScanResult(
            file_path=file_path,
            success=False,
            output="",
            error="Timeout after 60 seconds",
        )
    except Exception as e:
        return ScanResult(
            file_path=file_path,
            success=False,
            output="",
            error=str(e),
        )


def _channels_to_layout(channels: int | None) -> str:
    """Convert channel count to layout description."""
    if channels is None:
        return ""
    layouts = {
        1: "mono",
        2: "stereo",
        6: "5.1",
        8: "7.1",
    }
    return layouts.get(channels, f"{channels}ch")


def _print_track_comparison(tracks: list[TrackInfo]) -> None:
    """Print BEFORE and AFTER track comparison as separate tables.

    Args:
        tracks: List of all tracks with disposition info.
    """
    if not tracks:
        return

    # Sort all tracks by original index
    all_tracks_sorted = sorted(tracks, key=lambda t: t.index)

    # Build mapping of original index to new index for kept tracks
    kept_tracks = [t for t in all_tracks_sorted if t.action == "KEEP"]
    new_index_map = {t.index: i for i, t in enumerate(kept_tracks)}

    # Type abbreviations
    type_abbrev = {
        "video": "V",
        "audio": "A",
        "subtitle": "S",
        "attachment": "X",
    }

    def get_track_details(track: TrackInfo) -> tuple[str, str, str, str, str]:
        """Extract common track details."""
        track_type = type_abbrev.get(track.track_type, "?")
        codec = (track.codec or "").upper()

        if track.track_type == "video" and track.resolution:
            details = track.resolution
        elif track.track_type == "audio" and track.channels:
            details = _channels_to_layout(track.channels)
        else:
            details = ""

        lang = track.language or ""

        title = ""
        if track.title:
            title = track.title[:25] + "..." if len(track.title) > 25 else track.title

        return (track_type, codec, lang, details, title)

    def print_table(
        headers: tuple[str, ...],
        rows: list[tuple[str, ...]],
    ) -> None:
        """Print a formatted table."""
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def print_row(cells: tuple[str, ...]) -> None:
            formatted = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))
            print(f"    {formatted}")

        print_row(headers)
        print(f"    {'-' * (sum(widths) + 2 * (len(widths) - 1))}")
        for row in rows:
            print_row(row)

    # Build BEFORE table rows
    before_rows: list[tuple[str, ...]] = []
    for track in all_tracks_sorted:
        idx = f"[T:{track.index}]"
        action = "KEEP" if track.action == "KEEP" else "DELETE"
        track_type, codec, lang, details, title = get_track_details(track)

        if track.action == "KEEP":
            after_idx = f"[T:{new_index_map[track.index]}]"
        else:
            after_idx = "-"

        before_rows.append(
            (idx, action, track_type, codec, lang, details, title, after_idx)
        )

    # Print BEFORE table
    print("\n  BEFORE:")
    before_headers = (
        "TRACK",
        "ACTION",
        "TYPE",
        "CODEC",
        "LANG",
        "DETAILS",
        "TITLE",
        "AFTER",
    )
    print_table(before_headers, before_rows)

    # Build AFTER table rows (only kept tracks)
    after_rows: list[tuple[str, ...]] = []
    for track in kept_tracks:
        idx = f"[T:{new_index_map[track.index]}]"
        track_type, codec, lang, details, title = get_track_details(track)
        after_rows.append((idx, track_type, codec, lang, details, title))

    # Print AFTER table
    print("\n  AFTER:")
    after_headers = ("TRACK", "TYPE", "CODEC", "LANG", "DETAILS", "TITLE")
    print_table(after_headers, after_rows)

    # Print summary of changes
    removed_tracks = [t for t in tracks if t.action != "KEEP"]
    if removed_tracks:
        removed_types: dict[str, int] = {}
        for t in removed_tracks:
            removed_types[t.track_type] = removed_types.get(t.track_type, 0) + 1
        removed_summary = ", ".join(
            f"{count} {ttype}" for ttype, count in sorted(removed_types.items())
        )
        print(
            f"\n    Summary: {len(kept_tracks)} kept, "
            f"{len(removed_tracks)} removed ({removed_summary})"
        )


def print_result(result: ScanResult, verbose: bool = True) -> None:
    """Print a single scan result.

    Args:
        result: The scan result to print.
        verbose: If True, print full output; otherwise just summary.
    """
    print(f"\n{'=' * 80}")
    print(f"File: {result.file_path.name}")
    print(f"Path: {result.file_path.parent}")
    print("-" * 80)

    if not result.success:
        print(f"ERROR: {result.error or 'Unknown error'}")
        return

    if verbose:
        # Print status summary
        status_parts = []
        if result.synthesis_planned:
            status_parts.append("WILL CREATE EAC3")
        if result.synthesis_skipped:
            status_parts.append(f"SKIPPED ({result.skip_reason or 'unknown'})")
        if result.has_changes and not result.synthesis_planned:
            status_parts.append("METADATA CHANGES")
        if not status_parts:
            status_parts.append("NO CHANGES")
        print(f"  Status: {', '.join(status_parts)}")

        # Print track comparison if we have track info
        if result.tracks:
            _print_track_comparison(result.tracks)
        else:
            # Fall back to parsing text output for synthesis info
            lines = result.output.strip().split("\n")
            in_relevant_section = False

            for line in lines:
                # Skip log lines unless they contain useful info
                if " - INFO - " in line:
                    if "Skipped synthesis" in line or "Planned synthesis" in line:
                        msg = line.split(" - INFO - ")[-1]
                        print(f"  {msg}")
                    continue

                # Start printing from "Audio Synthesis Plan" or "Proposed changes"
                if "Audio Synthesis Plan" in line or "Proposed changes:" in line:
                    in_relevant_section = True

                if in_relevant_section:
                    print(line)

                # Stop at "To apply these changes"
                if "To apply these changes" in line:
                    break
    else:
        # Summary only
        status_parts = []
        if result.synthesis_planned:
            status_parts.append("WILL CREATE EAC3")
        if result.synthesis_skipped:
            status_parts.append(f"SKIPPED ({result.skip_reason or 'unknown'})")
        if result.has_changes and not result.synthesis_planned:
            status_parts.append("METADATA CHANGES")
        if not status_parts:
            status_parts.append("NO CHANGES")

        print(f"  Status: {', '.join(status_parts)}")


def print_summary(summary: ScanSummary) -> None:
    """Print the final summary of all scans.

    Args:
        summary: The summary to print.
    """
    print("\n")
    print("=" * 80)
    print("SCAN SUMMARY")
    print("=" * 80)
    print(f"Total files scanned:    {summary.total_files}")
    print(f"Successful:             {summary.successful}")
    print(f"Failed:                 {summary.failed}")
    print()
    print(f"Files with changes:     {summary.with_changes}")
    print(f"Synthesis planned:      {summary.synthesis_planned}")
    print(f"Synthesis skipped:      {summary.synthesis_skipped}")

    if summary.skip_reasons:
        print()
        print("Skip reasons breakdown:")
        for reason, count in sorted(summary.skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    if summary.errors:
        print()
        print("Errors:")
        for path, error in summary.errors:
            print(f"  {path.name}: {error}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch preview policy application on video files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/videos --policy examples/policies/media-normalization.yaml
  %(prog)s /path/to/videos --policy policy.yaml --extensions mkv,mp4
  %(prog)s /path/to/videos --policy policy.yaml --summary-only
  %(prog)s /path/to/videos --policy policy.yaml --output results.txt
        """,
    )

    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan for video files",
    )
    parser.add_argument(
        "--policy",
        "-p",
        type=Path,
        required=True,
        help="Path to the policy YAML file",
    )
    parser.add_argument(
        "--extensions",
        "-e",
        type=str,
        default="mkv,mp4,avi,m4v,webm",
        help="Comma-separated extensions (default: mkv,mp4,avi,m4v,webm)",
    )
    parser.add_argument(
        "--summary-only",
        "-s",
        action="store_true",
        help="Only show summary line for each file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Limit number of files to scan",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.directory.exists():
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        return 1

    if not args.policy.exists():
        print(f"Error: Policy file not found: {args.policy}", file=sys.stderr)
        return 1

    # Parse extensions
    extensions = tuple(
        f".{ext.strip().lstrip('.')}" for ext in args.extensions.split(",")
    )

    # Find video files
    print(f"Scanning {args.directory} for video files...")
    files = find_video_files(args.directory, extensions)

    if args.limit:
        files = files[: args.limit]

    if not files:
        print("No video files found.")
        return 0

    print(f"Found {len(files)} video file(s)")
    print(f"Using policy: {args.policy}")

    # Redirect output if requested
    output_file = None
    if args.output:
        output_file = open(args.output, "w")
        original_stdout = sys.stdout
        sys.stdout = output_file

    try:
        # Process each file
        summary = ScanSummary()

        for i, file_path in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] Processing: {file_path.name}")

            result = run_policy_preview(file_path, args.policy)
            summary.total_files += 1

            if result.success:
                summary.successful += 1
                if result.has_changes:
                    summary.with_changes += 1
                if result.synthesis_planned:
                    summary.synthesis_planned += 1
                if result.synthesis_skipped:
                    summary.synthesis_skipped += 1
                    if result.skip_reason:
                        summary.skip_reasons[result.skip_reason] = (
                            summary.skip_reasons.get(result.skip_reason, 0) + 1
                        )
            else:
                summary.failed += 1
                summary.errors.append((file_path, result.error or "Unknown error"))

            print_result(result, verbose=not args.summary_only)

        # Print summary
        print_summary(summary)

    finally:
        if output_file:
            sys.stdout = original_stdout
            output_file.close()
            print(f"Results written to: {args.output}")

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
