"""Job summary text generation.

Produces human-readable summaries from job summary_json data.
This module contains domain logic for interpreting job results.
"""

from __future__ import annotations

from pathlib import Path

from vpo.core.formatting import format_file_size


def generate_summary_text(job_type: str, summary_raw: dict | None) -> str | None:
    """Generate human-readable summary text from summary_json data.

    Produces type-specific summaries based on job type and summary data.

    Args:
        job_type: Job type value (scan, apply, transcode, move).
        summary_raw: Parsed summary_json dictionary, or None.

    Returns:
        Human-readable summary string, or None if no summary available.
    """
    if summary_raw is None:
        return None

    try:
        if job_type == "scan":
            # Scan job summary: "Scanned X files, Y new, Z errors"
            # Fields from cli/scan.py: total_discovered, scanned, skipped,
            # added, removed, errors
            scanned = summary_raw.get("scanned", 0)
            added = summary_raw.get("added", 0)
            removed = summary_raw.get("removed", 0)
            skipped = summary_raw.get("skipped", 0)
            errors = summary_raw.get("errors", 0)

            parts = [f"Scanned {scanned} files"]
            if added > 0:
                parts.append(f"{added} new")
            if removed > 0:
                parts.append(f"{removed} removed")
            if skipped > 0:
                parts.append(f"{skipped} unchanged")
            if errors > 0:
                parts.append(f"{errors} error{'s' if errors != 1 else ''}")

            return ", ".join(parts)

        elif job_type == "apply":
            # Apply job summary: "Applied policy 'name' to X files"
            policy_name = summary_raw.get("policy_name", "unknown")
            files_affected = summary_raw.get("files_affected", 0)
            actions = summary_raw.get("actions_applied", [])

            summary = f"Applied policy '{policy_name}' to {files_affected} files"
            if actions:
                summary += f" ({', '.join(actions)})"
            return summary

        elif job_type == "transcode":
            # Transcode job summary: "Transcoded input -> output (compression ratio)"
            input_file = summary_raw.get("input_file", "")
            output_file = summary_raw.get("output_file", "")
            input_size = summary_raw.get("input_size_bytes", 0)
            output_size = summary_raw.get("output_size_bytes", 0)

            # Extract just filenames for cleaner display
            input_name = Path(input_file).name if input_file else "input"
            output_name = Path(output_file).name if output_file else "output"

            summary = f"Transcoded {input_name} \u2192 {output_name}"
            if input_size > 0 and output_size > 0:
                ratio = output_size / input_size
                summary += f" ({ratio:.0%} of original size)"
            return summary

        elif job_type == "move":
            # Move job summary: "Moved source -> destination"
            source = summary_raw.get("source_path", "")
            dest = summary_raw.get("destination_path", "")
            size = summary_raw.get("size_bytes", 0)

            # Extract just filenames
            source_name = Path(source).name if source else "source"
            dest_path = dest if dest else "destination"

            summary = f"Moved {source_name} \u2192 {dest_path}"
            if size > 0:
                summary += f" ({format_file_size(size)})"
            return summary

        else:
            # Unknown job type - return None
            return None

    except (TypeError, AttributeError):
        # Handle malformed summary_json gracefully
        return None
