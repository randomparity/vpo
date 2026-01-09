"""Pydantic schemas for JSON database fields.

These models validate JSON stored in database columns like
plugin_metadata, summary_json, and progress_json. They provide
runtime type checking and field constraints.

Usage:
    from vpo.core import parse_json_with_schema
    from vpo.db.json_schemas import ScanJobSummary

    result = parse_json_with_schema(job.summary_json, ScanJobSummary)
    if result.success and result.value:
        summary = result.value
        print(f"Scanned {summary.scanned} files")
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PluginMetadataEntry(BaseModel):
    """Metadata entry from a single plugin.

    Plugin metadata values must be scalar types only.
    Nested structures (lists, dicts) are not supported to
    simplify querying and reduce corruption risk.
    """

    model_config = ConfigDict(extra="allow")

    # All fields are dynamic - plugins can add any scalar fields
    # The model_config allows extra fields


class PluginMetadataSchema(BaseModel):
    """Root schema for plugin_metadata JSON field.

    Structure: {"plugin_name": {"field": value, ...}, ...}

    Example:
        {
            "radarr": {"movie_id": 123, "title": "Movie Name"},
            "sonarr": {"series_id": 456}
        }
    """

    model_config = ConfigDict(extra="allow")

    # Plugin entries are dynamic - any plugin name is valid


# Job Summary Schemas (per job type)


class ScanJobSummary(BaseModel):
    """Summary for scan jobs.

    Fields from cli/scan.py: total_discovered, scanned, skipped,
    added, removed, errors.
    """

    model_config = ConfigDict(extra="forbid")

    total_discovered: int = Field(default=0, ge=0)
    scanned: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    added: int = Field(default=0, ge=0)
    removed: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)


class ApplyJobSummary(BaseModel):
    """Summary for apply jobs.

    Fields: policy_name, files_affected, actions_applied.
    """

    model_config = ConfigDict(extra="forbid")

    policy_name: str
    files_affected: int = Field(default=0, ge=0)
    actions_applied: list[str] = Field(default_factory=list)


class TranscodeJobSummary(BaseModel):
    """Summary for transcode jobs.

    Fields: input_file, output_file, input_size_bytes, output_size_bytes.
    """

    model_config = ConfigDict(extra="forbid")

    input_file: str = ""
    output_file: str = ""
    input_size_bytes: int = Field(default=0, ge=0)
    output_size_bytes: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    video_codec: str | None = None
    audio_tracks_processed: int = Field(default=0, ge=0)


class MoveJobSummary(BaseModel):
    """Summary for move jobs.

    Fields: source_path, destination_path, size_bytes.
    """

    model_config = ConfigDict(extra="forbid")

    source_path: str = ""
    destination_path: str = ""
    size_bytes: int = Field(default=0, ge=0)


# Job Progress Schema


class JobProgressSchema(BaseModel):
    """Schema for progress_json field.

    Matches the JobProgress dataclass in db/types.py.
    """

    model_config = ConfigDict(extra="forbid")

    percent: float = Field(ge=0.0, le=100.0)

    # Transcoding-specific
    frame_current: int | None = Field(default=None, ge=0)
    frame_total: int | None = Field(default=None, ge=0)
    time_current: float | None = Field(default=None, ge=0.0)
    time_total: float | None = Field(default=None, ge=0.0)
    fps: float | None = Field(default=None, ge=0.0)
    bitrate: str | None = None
    size_current: int | None = Field(default=None, ge=0)

    # Estimates
    eta_seconds: int | None = Field(default=None, ge=0)


# Mapping from job type to summary schema
JOB_SUMMARY_SCHEMAS: dict[str, type[BaseModel]] = {
    "scan": ScanJobSummary,
    "apply": ApplyJobSummary,
    "transcode": TranscodeJobSummary,
    "move": MoveJobSummary,
}


def get_summary_schema(job_type: str) -> type[BaseModel] | None:
    """Get the summary schema for a given job type.

    Args:
        job_type: Job type value (scan, apply, transcode, move).

    Returns:
        Pydantic model class for the summary, or None if unknown type.
    """
    return JOB_SUMMARY_SCHEMAS.get(job_type)
