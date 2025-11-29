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
import subprocess  # nosec B404
import sys
from dataclasses import dataclass, field
from pathlib import Path


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

        # Analyze output
        has_changes = "Summary:" in output or "Tracks to create" in output
        synthesis_planned = "Tracks to create" in output
        synthesis_skipped = "SKIPPED" in output

        # Extract skip reason if present
        skip_reason = None
        if synthesis_skipped:
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
        # Print relevant parts of output
        lines = result.output.strip().split("\n")
        in_relevant_section = False

        for line in lines:
            # Skip log lines unless they contain useful info
            if " - INFO - " in line:
                if "Skipped synthesis" in line or "Planned synthesis" in line:
                    # Extract just the message part
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
