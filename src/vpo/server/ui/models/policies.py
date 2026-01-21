"""Policy view models.

This module defines models for policy list, editor, and validation views.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
        track_order: List of track type strings.
        audio_language_preference: List of ISO 639-2 codes.
        subtitle_language_preference: List of ISO 639-2 codes.
        commentary_patterns: List of regex patterns.
        default_flags: Default flags configuration dict.
        transcode: Transcode configuration dict, or None.
        transcription: Transcription configuration dict, or None.
        audio_filter: Audio filter configuration (V3+), or None.
        subtitle_filter: Subtitle filter configuration (V3+), or None.
        attachment_filter: Attachment filter configuration (V3+), or None.
        container: Container configuration (V3+), or None.
        conditional: Conditional rules list (V4+), or None.
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
    audio_language_preference: list[str]
    subtitle_language_preference: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    # V3+ fields (036-v9-policy-editor)
    audio_filter: dict | None = None
    subtitle_filter: dict | None = None
    attachment_filter: dict | None = None
    container: dict | None = None
    # V4+ fields
    conditional: list | None = None
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
            "track_order": self.track_order,
            "audio_language_preference": self.audio_language_preference,
            "subtitle_language_preference": self.subtitle_language_preference,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
            "transcode": self.transcode,
            "transcription": self.transcription,
            # V3+ fields
            "audio_filter": self.audio_filter,
            "subtitle_filter": self.subtitle_filter,
            "attachment_filter": self.attachment_filter,
            "container": self.container,
            # V4+ fields
            "conditional": self.conditional,
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
        audio_language_preference: Updated audio language preferences.
        subtitle_language_preference: Updated subtitle language preferences.
        commentary_patterns: Updated commentary detection patterns.
        default_flags: Updated default flags configuration.
        transcode: Updated transcode settings, or None.
        transcription: Updated transcription settings, or None.
        audio_filter: Audio filter configuration (V3+), or None.
        subtitle_filter: Subtitle filter configuration (V3+), or None.
        attachment_filter: Attachment filter configuration (V3+), or None.
        container: Container configuration (V3+), or None.
        conditional: Conditional rules list (V4+), or None.
        audio_synthesis: Audio synthesis config list (V5+), or None.
        workflow: Workflow configuration (V9+), or None.
        last_modified_timestamp: ISO-8601 UTC timestamp for optimistic locking.
    """

    track_order: list[str]
    audio_language_preference: list[str]
    subtitle_language_preference: list[str]
    commentary_patterns: list[str]
    default_flags: dict
    transcode: dict | None
    transcription: dict | None
    # V3+ fields (036-v9-policy-editor)
    audio_filter: dict | None
    subtitle_filter: dict | None
    attachment_filter: dict | None
    container: dict | None
    # V4+ fields
    conditional: list | None
    # V5+ fields
    audio_synthesis: list | None
    # V9+ fields
    workflow: dict | None
    # Phased policy fields (user-defined phases)
    phases: list | None
    config: dict | None
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
                "audio_language_preference",
                config.get("audio_language_preference", []),
            )
            subtitle_lang = data.get(
                "subtitle_language_preference",
                config.get("subtitle_language_preference", []),
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
                audio_language_preference=audio_lang,
                subtitle_language_preference=subtitle_lang,
                commentary_patterns=commentary,
                default_flags=default_flags,
                transcode=data.get("transcode"),
                transcription=data.get("transcription"),
                audio_filter=data.get("audio_filter"),
                subtitle_filter=data.get("subtitle_filter"),
                attachment_filter=data.get("attachment_filter"),
                container=data.get("container"),
                conditional=data.get("conditional"),
                audio_synthesis=data.get("audio_synthesis"),
                workflow=data.get("workflow"),
                phases=phases,
                config=config,
                last_modified_timestamp=data["last_modified_timestamp"],
            )

        # Legacy format: flat fields required (still needs phases though)
        required_fields = [
            "track_order",
            "audio_language_preference",
            "subtitle_language_preference",
            "commentary_patterns",
            "default_flags",
        ]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return cls(
            track_order=data["track_order"],
            audio_language_preference=data["audio_language_preference"],
            subtitle_language_preference=data["subtitle_language_preference"],
            commentary_patterns=data["commentary_patterns"],
            default_flags=data["default_flags"],
            transcode=data.get("transcode"),
            transcription=data.get("transcription"),
            # V3+ fields
            audio_filter=data.get("audio_filter"),
            subtitle_filter=data.get("subtitle_filter"),
            attachment_filter=data.get("attachment_filter"),
            container=data.get("container"),
            # V4+ fields
            conditional=data.get("conditional"),
            # V5+ fields
            audio_synthesis=data.get("audio_synthesis"),
            # V9+ fields
            workflow=data.get("workflow"),
            # Phased policy fields
            phases=phases,
            config=config,
            last_modified_timestamp=data["last_modified_timestamp"],
        )

    def to_policy_dict(self) -> dict:
        """Convert to dictionary for policy validation and saving.

        Returns:
            Dictionary in PolicyModel format or PhasedPolicySchema format.
        """
        # Phased policies have a different structure
        if self.phases is not None:
            return self._to_phased_policy_dict()
        return self._to_legacy_policy_dict()

    def _to_phased_policy_dict(self) -> dict:
        """Convert to phased policy dictionary format.

        Returns:
            Dictionary in PhasedPolicySchema format.
        """
        result: dict = {
            "schema_version": 12,
            "phases": self.phases,
        }
        if self.config is not None:
            result["config"] = self.config
        else:
            # Build config from legacy fields
            result["config"] = {
                "audio_language_preference": self.audio_language_preference,
                "subtitle_language_preference": self.subtitle_language_preference,
                "commentary_patterns": self.commentary_patterns,
                "on_error": "continue",  # Default
            }
        return result

    def _to_legacy_policy_dict(self) -> dict:
        """Convert to flat policy dictionary format.

        Returns:
            Dictionary in PolicyModel format.
        """
        # Always use schema_version 12
        result = {
            "schema_version": 12,
            "track_order": self.track_order,
            "audio_language_preference": self.audio_language_preference,
            "subtitle_language_preference": self.subtitle_language_preference,
            "commentary_patterns": self.commentary_patterns,
            "default_flags": self.default_flags,
        }

        if self.transcode is not None:
            result["transcode"] = self.transcode

        if self.transcription is not None:
            result["transcription"] = self.transcription

        # V3+ fields
        if self.audio_filter is not None:
            result["audio_filter"] = self.audio_filter

        if self.subtitle_filter is not None:
            result["subtitle_filter"] = self.subtitle_filter

        if self.attachment_filter is not None:
            result["attachment_filter"] = self.attachment_filter

        if self.container is not None:
            result["container"] = self.container

        # V4+ fields
        if self.conditional is not None:
            result["conditional"] = self.conditional

        # V5+ fields
        if self.audio_synthesis is not None:
            result["audio_synthesis"] = self.audio_synthesis

        # V9+ fields
        if self.workflow is not None:
            result["workflow"] = self.workflow

        return result


@dataclass
class ValidationErrorItem:
    """A single field-level validation error.

    Attributes:
        field: Dot-notation field path (e.g., 'audio_language_preference[0]').
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
        errors: List of field-level validation errors.
        details: Optional additional context.
    """

    error: str
    errors: list[ValidationErrorItem]
    details: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "error": self.error,
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
