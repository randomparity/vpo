"""Policy view models for API responses.

These types are used by policy services and the server UI layer.
They are defined here to avoid circular imports between policy/ and server/.
"""

from __future__ import annotations

from dataclasses import dataclass


def format_language_preferences(languages: list[str]) -> str:
    """Format language preference list for display.

    Args:
        languages: List of ISO 639-2 language codes.

    Returns:
        Formatted string (e.g., "eng, jpn" or "eng, jpn +2 more") or "-".
    """
    if not languages:
        return "\u2014"

    if len(languages) <= 3:
        return ", ".join(languages)

    return f"{', '.join(languages[:3])} +{len(languages) - 3} more"


@dataclass
class PolicyListItem:
    """Policy data for Policies API response.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename with extension.
        file_path: Absolute path to the policy file.
        last_modified: ISO-8601 UTC timestamp.
        schema_version: Policy schema version (null if parse error).
        display_name: Optional display name from YAML 'name' field.
        description: Optional policy description.
        category: Optional category for filtering/grouping.
        audio_languages: Formatted audio language preferences.
        subtitle_languages: Formatted subtitle language preferences.
        has_transcode: True if policy includes transcode settings.
        has_transcription: True if transcription enabled.
        is_default: True if this is the profile's default policy.
        parse_error: Error message if YAML invalid, else None.
    """

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int | None
    display_name: str | None
    description: str | None
    category: str | None
    audio_languages: str
    subtitle_languages: str
    has_transcode: bool
    has_transcription: bool
    is_default: bool
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "has_transcode": self.has_transcode,
            "has_transcription": self.has_transcription,
            "is_default": self.is_default,
            "parse_error": self.parse_error,
        }


@dataclass
class PolicyListResponse:
    """API response wrapper for /api/policies.

    Attributes:
        policies: List of policy items.
        total: Total number of policies found.
        policies_directory: Path to policies directory.
        default_policy_path: Configured default policy path (may be None).
        default_policy_missing: True if configured default doesn't exist.
        directory_exists: True if policies directory exists.
    """

    policies: list[PolicyListItem]
    total: int
    policies_directory: str
    default_policy_path: str | None
    default_policy_missing: bool
    directory_exists: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "policies": [p.to_dict() for p in self.policies],
            "total": self.total,
            "policies_directory": self.policies_directory,
            "default_policy_path": self.default_policy_path,
            "default_policy_missing": self.default_policy_missing,
            "directory_exists": self.directory_exists,
        }
