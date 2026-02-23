"""Policy view models.

This module defines models for policy list, editor, and validation views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vpo.policy.loader import SCHEMA_VERSION


@dataclass
class PoliciesContext:
    """Template context for policies.html.

    Attributes:
        policies_directory: Path to policies directory for display.
    """

    policies_directory: str

    @classmethod
    def default(cls) -> PoliciesContext:
        """Create default context."""
        return cls(
            policies_directory=str(Path.home() / ".vpo" / "policies"),
        )


@dataclass
class PolicyEditorContext:
    """Context passed to policy_editor.html template.

    Attributes:
        name: Policy name (filename without extension).
        filename: Full filename with extension.
        file_path: Absolute path to the policy file.
        last_modified: ISO-8601 UTC timestamp for concurrency check.
        schema_version: Policy schema version (read-only).
        display_name: Optional display name from YAML 'name' field.
        description: Optional policy description.
        category: Optional category for filtering/grouping.
        track_order: List of track type strings.
        audio_languages: List of ISO 639-2 codes.
        subtitle_languages: List of ISO 639-2 codes.
        commentary_patterns: List of regex patterns.
        default_flags: Default flags configuration dict.
        transcode: Transcode configuration dict, or None.
        transcription: Transcription configuration dict, or None.
        keep_audio: Audio filter configuration, or None.
        keep_subtitles: Subtitle filter configuration, or None.
        filter_attachments: Attachment filter configuration, or None.
        container: Container configuration, or None.
        rules: Conditional rules config (match/items), or None.
        audio_synthesis: Audio synthesis config list (V5+), or None.
        workflow: Workflow configuration (V9+), or None.
        unknown_fields: List of field names not in known schema.
        parse_error: Error message if policy invalid, else None.
    """

    name: str
    filename: str
    file_path: str
    last_modified: str
    schema_version: int
    track_order: list[str]
    audio_languages: list[str]
    subtitle_languages: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    # Policy metadata fields
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    # Track filtering fields
    keep_audio: dict | None = None
    keep_subtitles: dict | None = None
    filter_attachments: dict | None = None
    container: dict | None = None
    # Conditional rules
    rules: dict | None = None
    # V5+ fields
    audio_synthesis: list | None = None
    # V9+ fields
    workflow: dict | None = None
    # Phased policy fields (user-defined phases)
    phases: list | None = None
    config: dict | None = None
    # Unknown fields for warning banner
    unknown_fields: list[str] | None = None
    parse_error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "filename": self.filename,
            "file_path": self.file_path,
            "last_modified": self.last_modified,
            "schema_version": self.schema_version,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "track_order": self.track_order,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
            "transcode": self.transcode,
            "transcription": self.transcription,
            # Track filtering fields
            "keep_audio": self.keep_audio,
            "keep_subtitles": self.keep_subtitles,
            "filter_attachments": self.filter_attachments,
            "container": self.container,
            # Conditional rules
            "rules": self.rules,
            # V5+ fields
            "audio_synthesis": self.audio_synthesis,
            # V9+ fields
            "workflow": self.workflow,
            # Phased policy fields
            "phases": self.phases,
            "config": self.config,
            # Meta
            "unknown_fields": self.unknown_fields,
            "parse_error": self.parse_error,
        }
        # Add convenience field for phased policies
        if self.phases is not None:
            result["phase_names"] = [
                p.get("name", "") for p in self.phases if isinstance(p, dict)
            ]
        return result


@dataclass
class PolicyEditorRequest:
    """Request payload for saving policy changes via PUT /api/policies/{name}.

    Attributes:
        track_order: Updated track ordering.
        audio_languages: Updated audio language preferences.
        subtitle_languages: Updated subtitle language preferences.
        commentary_patterns: Updated commentary detection patterns.
        default_flags: Updated default flags configuration.
        transcode: Updated transcode settings, or None.
        transcription: Updated transcription settings, or None.
        keep_audio: Audio filter configuration, or None.
        keep_subtitles: Subtitle filter configuration, or None.
        filter_attachments: Attachment filter configuration, or None.
        container: Container configuration, or None.
        rules: Conditional rules config (match/items), or None.
        audio_synthesis: Audio synthesis config list (V5+), or None.
        workflow: Workflow configuration (V9+), or None.
        last_modified_timestamp: ISO-8601 UTC timestamp for optimistic locking.
    """

    track_order: list[str]
    audio_languages: list[str]
    subtitle_languages: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    # Track filtering fields
    keep_audio: dict | None
    keep_subtitles: dict | None
    filter_attachments: dict | None
    container: dict | None
    # Conditional rules
    rules: dict | None
    # V5+ fields
    audio_synthesis: list | None
    # V9+ fields
    workflow: dict | None
    # Phased policy fields (user-defined phases)
    phases: list | None
    config: dict | None
    # Policy metadata fields
    display_name: str | None
    description: str | None
    category: str | None
    last_modified_timestamp: str

    @classmethod
    def from_dict(cls, data: dict) -> PolicyEditorRequest:
        """Create PolicyEditorRequest from request payload.

        Supports two input formats:
        1. Phased format: `phases` and `config` fields provided. Flat fields
           are extracted from config/phases.
        2. Legacy format: Flat fields provided (for backwards compat in tests).
           Must also provide `phases` field since flat-only policies removed.

        Args:
            data: JSON request payload.

        Returns:
            Validated PolicyEditorRequest instance.

        Raises:
            ValueError: If required fields are missing.
        """
        # last_modified_timestamp is always required for optimistic locking
        if "last_modified_timestamp" not in data:
            raise ValueError("Missing required field: last_modified_timestamp")

        phases = data.get("phases")
        config = data.get("config", {})

        # If phases provided, extract flat fields from config/phases
        if phases is not None:
            # Extract flat fields from config with defaults
            # These are used for validation and backwards compat
            first_phase = phases[0] if phases else {}
            track_order = data.get("track_order", first_phase.get("track_order", []))
            audio_lang = data.get(
                "audio_languages",
                config.get("audio_languages", []),
            )
            subtitle_lang = data.get(
                "subtitle_languages",
                config.get("subtitle_languages", []),
            )
            commentary = data.get(
                "commentary_patterns",
                config.get("commentary_patterns", []),
            )
            default_flags = data.get(
                "default_flags", first_phase.get("default_flags", {})
            )

            return cls(
                track_order=track_order,
                audio_languages=audio_lang,
                subtitle_languages=subtitle_lang,
                commentary_patterns=commentary,
                default_flags=default_flags,
                transcode=data.get("transcode"),
                transcription=data.get("transcription"),
                keep_audio=data.get("keep_audio"),
                keep_subtitles=data.get("keep_subtitles"),
                filter_attachments=data.get("filter_attachments"),
                container=data.get("container"),
                rules=data.get("rules"),
                audio_synthesis=data.get("audio_synthesis"),
                workflow=data.get("workflow"),
                phases=phases,
                config=config,
                display_name=data.get("display_name"),
                description=data.get("description"),
                category=data.get("category"),
                last_modified_timestamp=data["last_modified_timestamp"],
            )

        # Legacy format: flat fields required (still needs phases though)
        required_fields = [
            "track_order",
            "audio_languages",
            "subtitle_languages",
            "commentary_patterns",
            "default_flags",
        ]

        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")

        return cls(
            track_order=data["track_order"],
            audio_languages=data["audio_languages"],
            subtitle_languages=data["subtitle_languages"],
            commentary_patterns=data["commentary_patterns"],
            default_flags=data["default_flags"],
            transcode=data.get("transcode"),
            transcription=data.get("transcription"),
            # Track filtering fields
            keep_audio=data.get("keep_audio"),
            keep_subtitles=data.get("keep_subtitles"),
            filter_attachments=data.get("filter_attachments"),
            container=data.get("container"),
            # Conditional rules
            rules=data.get("rules"),
            # V5+ fields
            audio_synthesis=data.get("audio_synthesis"),
            # V9+ fields
            workflow=data.get("workflow"),
            # Phased policy fields
            phases=phases,
            config=config,
            # Policy metadata fields
            display_name=data.get("display_name"),
            description=data.get("description"),
            category=data.get("category"),
            last_modified_timestamp=data["last_modified_timestamp"],
        )

    def to_policy_dict(self) -> dict:
        """Convert to dictionary for policy validation and saving.

        Returns:
            Dictionary in PolicyModel format.
        """
        # Phased policies have a different structure
        if self.phases is not None:
            return self._to_phased_policy_dict()
        return self._to_legacy_policy_dict()

    def _to_phased_policy_dict(self) -> dict:
        """Convert to phased policy dictionary format.

        Returns:
            Dictionary in PolicySchema format with phases.
        """
        result: dict = {
            "schema_version": SCHEMA_VERSION,
            "phases": self.phases,
        }
        if self.config is not None:
            result["config"] = self.config
        else:
            # Build config from legacy fields
            result["config"] = {
                "audio_languages": self.audio_languages,
                "subtitle_languages": self.subtitle_languages,
                "commentary_patterns": self.commentary_patterns,
                "on_error": "continue",  # Default
            }
        self._add_metadata_fields(result)
        return result

    def _to_legacy_policy_dict(self) -> dict:
        """Convert to flat policy dictionary format.

        Note: V13 requires phased format. This method wraps flat fields
        into a single phase for forward compatibility.

        Returns:
            Dictionary in PolicyModel format with phases wrapper.
        """
        result = {
            "schema_version": SCHEMA_VERSION,
            "track_order": self.track_order,
            "audio_languages": self.audio_languages,
            "subtitle_languages": self.subtitle_languages,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
        }

        if self.transcode is not None:
            result["transcode"] = self.transcode

        if self.transcription is not None:
            result["transcription"] = self.transcription

        # Track filtering fields
        if self.keep_audio is not None:
            result["keep_audio"] = self.keep_audio

        if self.keep_subtitles is not None:
            result["keep_subtitles"] = self.keep_subtitles

        if self.filter_attachments is not None:
            result["filter_attachments"] = self.filter_attachments

        if self.container is not None:
            result["container"] = self.container

        # Conditional rules
        if self.rules is not None:
            result["rules"] = self.rules

        # V5+ fields
        if self.audio_synthesis is not None:
            result["audio_synthesis"] = self.audio_synthesis

        # V9+ fields
        if self.workflow is not None:
            result["workflow"] = self.workflow

        self._add_metadata_fields(result)

        return result

    def _add_metadata_fields(self, result: dict) -> None:
        """Add non-None metadata fields to a policy dict.

        Maps display_name to the YAML key 'name'.
        """
        if self.display_name is not None:
            result["name"] = self.display_name
        if self.description is not None:
            result["description"] = self.description
        if self.category is not None:
            result["category"] = self.category


@dataclass
class ValidationErrorItem:
    """A single field-level validation error.

    Attributes:
        field: Dot-notation field path (e.g., 'audio_languages[0]').
        message: Human-readable error message.
        code: Optional machine-readable error type code.
    """

    field: str
    message: str
    code: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "field": self.field,
            "message": self.message,
        }
        if self.code is not None:
            result["code"] = self.code
        return result


@dataclass
class ValidationErrorResponse:
    """API response for validation errors (HTTP 400).

    Attributes:
        error: Generic error message summary.
        code: Machine-readable error code.
        errors: List of field-level validation errors.
        details: Optional additional context.
    """

    error: str
    code: str = "VALIDATION_FAILED"
    errors: list[ValidationErrorItem] = field(default_factory=list)
    details: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "error": self.error,
            "code": self.code,
            "errors": [e.to_dict() for e in self.errors],
        }
        if self.details is not None:
            result["details"] = self.details
        return result


@dataclass
class ChangedFieldItem:
    """A single field change in the diff summary.

    Attributes:
        field: Field name that changed.
        change_type: Type of change (reordered, items_added, items_removed, modified).
        details: Human-readable description of the change.
    """

    field: str
    change_type: str
    details: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "field": self.field,
            "change_type": self.change_type,
        }
        if self.details is not None:
            result["details"] = self.details
        return result


@dataclass
class PolicySaveSuccessResponse:
    """API response for successful policy save (HTTP 200).

    Attributes:
        success: Always True for success responses.
        changed_fields: List of fields that were modified.
        changed_fields_summary: Human-readable summary of changes.
        policy: Updated policy data in PolicyEditorContext format.
    """

    success: bool
    changed_fields: list[ChangedFieldItem]
    changed_fields_summary: str
    policy: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "changed_fields": [f.to_dict() for f in self.changed_fields],
            "changed_fields_summary": self.changed_fields_summary,
            **self.policy,  # Spread policy data at top level for backward compat
        }


@dataclass
class PolicyValidateResponse:
    """API response for policy validation endpoint (T030).

    Attributes:
        valid: True if policy data is valid.
        errors: List of validation errors if invalid.
        message: Human-readable status message.
    """

    valid: bool
    errors: list[ValidationErrorItem]
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "valid": self.valid,
            "message": self.message,
        }
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        return result
