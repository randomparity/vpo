"""Formatters for language analysis results.

This module provides functions to format LanguageAnalysisResult objects
for human-readable or JSON output. These formatters are shared between
the CLI and potentially other consumers (web UI, API).
"""

from typing import Any

from vpo.language_analysis.models import (
    LanguageAnalysisResult,
    LanguageClassification,
)


def format_human(
    analysis: LanguageAnalysisResult,
    show_segments: bool = False,
) -> str:
    """Format language analysis result for human-readable output.

    Args:
        analysis: The language analysis result to format.
        show_segments: Whether to show detailed segment information.

    Returns:
        Formatted string for terminal output.
    """
    lines: list[str] = []

    # Classification header
    if analysis.classification == LanguageClassification.MULTI_LANGUAGE:
        lines.append("Language Analysis: MULTI-LANGUAGE")
    else:
        lines.append("Language Analysis: SINGLE-LANGUAGE")

    # Primary language
    lines.append(
        f"  Primary: {analysis.primary_language} "
        f"({analysis.primary_percentage * 100:.1f}%)"
    )

    # Secondary languages
    if analysis.secondary_languages:
        lines.append("  Secondary:")
        for lang_pct in analysis.secondary_languages:
            lines.append(
                f"    - {lang_pct.language_code}: {lang_pct.percentage * 100:.1f}%"
            )

    # Metadata
    lines.append(
        f"  Analysis: {len(analysis.segments)} samples, "
        f"{analysis.metadata.speech_ratio * 100:.0f}% speech detected"
    )

    # Segments detail (if requested)
    if show_segments and analysis.segments:
        lines.append("")
        lines.append("  Segments:")
        for seg in analysis.segments:
            lines.append(
                f"    {seg.start_time:.1f}s-{seg.end_time:.1f}s: "
                f"{seg.language_code} (confidence: {seg.confidence:.2f})"
            )

    return "\n".join(lines)


def format_json(analysis: LanguageAnalysisResult) -> dict[str, Any]:
    """Format language analysis result for JSON output.

    Args:
        analysis: The language analysis result to format.

    Returns:
        Dictionary representation for JSON serialization.
    """
    return {
        "classification": analysis.classification.value,
        "primary_language": analysis.primary_language,
        "primary_percentage": analysis.primary_percentage,
        "secondary_languages": [
            {"code": lp.language_code, "percentage": lp.percentage}
            for lp in analysis.secondary_languages
        ],
        "is_multi_language": analysis.is_multi_language,
        "segments": [
            {
                "language": seg.language_code,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "confidence": seg.confidence,
            }
            for seg in analysis.segments
        ],
        "metadata": {
            "plugin": analysis.metadata.plugin_name,
            "model": analysis.metadata.model_name,
            "samples": len(analysis.metadata.sample_positions),
            "speech_ratio": analysis.metadata.speech_ratio,
        },
    }
