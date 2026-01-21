"""Policy validation helpers and data models.

This module provides validation utilities for the policy editor,
including structured error reporting and diff summaries.

Feature: 025-policy-validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import ValidationError as PydanticValidationError


@dataclass
class ValidationError:
    """Represents a single validation error with field context.

    Attributes:
        field: Dot-notation field path (e.g., 'audio_language_preference[0]').
        message: Human-readable error message.
        code: Optional machine-readable error type code.
    """

    field: str
    message: str
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "field": self.field,
            "message": self.message,
        }
        if self.code is not None:
            result["code"] = self.code
        return result


@dataclass
class ValidationResult:
    """Represents the complete validation outcome.

    Attributes:
        success: True if validation passed.
        errors: List of errors if validation failed.
        policy: Validated policy data if successful.
    """

    success: bool
    errors: list[ValidationError] = field(default_factory=list)
    policy: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {"success": self.success}
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        if self.policy is not None:
            result["policy"] = self.policy
        return result


@dataclass
class FieldChange:
    """Represents a single field change in the diff summary.

    Attributes:
        field: Field name that changed.
        change_type: Type of change: added, removed, modified, reordered,
            items_added, or items_removed.
        details: Human-readable change details.
    """

    field: str
    change_type: str
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "field": self.field,
            "change_type": self.change_type,
        }
        if self.details is not None:
            result["details"] = self.details
        return result


@dataclass
class DiffSummary:
    """Represents all changes between original and updated policy.

    Attributes:
        changes: List of field changes.
    """

    changes: list[FieldChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {"changes": [c.to_dict() for c in self.changes]}

    def to_summary_text(self) -> str:
        """Generate human-readable summary string.

        Returns:
            Comma-separated list of changes (e.g., 'field: reordered').
        """
        if not self.changes:
            return "No changes"

        parts = []
        for change in self.changes:
            if change.details:
                parts.append(f"{change.field}: {change.details}")
            else:
                parts.append(f"{change.field}: {change.change_type}")

        return ", ".join(parts)

    @staticmethod
    def compare_policies(
        old_data: dict[str, Any], new_data: dict[str, Any]
    ) -> DiffSummary:
        """Compare two policy dictionaries and return a diff summary.

        Supports both flat policies (fields at root level) and phased policies
        (fields inside config/phases sections).

        Args:
            old_data: Original policy data.
            new_data: Updated policy data.

        Returns:
            DiffSummary with all detected changes.
        """
        changes: list[FieldChange] = []

        # Fields to compare - these may be at root level (flat) or in config (phased)
        config_fields = [
            "audio_language_preference",
            "subtitle_language_preference",
            "commentary_patterns",
        ]

        # Fields that may be in phases (first phase for comparison)
        phase_fields = [
            "track_order",
            "default_flags",
        ]

        # Helper to get value from flat or phased structure
        def get_value(data: dict, field: str) -> Any:
            # First check root level (flat policy or explicit override)
            if field in data:
                return data[field]
            # Then check config section (phased policy)
            if field in config_fields and "config" in data:
                return data["config"].get(field)
            # Check first phase for phase-specific fields
            if field in phase_fields and "phases" in data and data["phases"]:
                return data["phases"][0].get(field)
            return None

        # Compare config fields
        for field_name in config_fields:
            old_value = get_value(old_data, field_name)
            new_value = get_value(new_data, field_name)

            change = DiffSummary._compare_field(field_name, old_value, new_value)
            if change:
                changes.append(change)

        # Compare phase fields
        for field_name in phase_fields:
            old_value = get_value(old_data, field_name)
            new_value = get_value(new_data, field_name)

            change = DiffSummary._compare_field(field_name, old_value, new_value)
            if change:
                changes.append(change)

        return DiffSummary(changes=changes)

    @staticmethod
    def _compare_field(
        field_name: str, old_value: Any, new_value: Any
    ) -> FieldChange | None:
        """Compare two field values and return the appropriate change.

        Args:
            field_name: Name of the field being compared.
            old_value: Original value.
            new_value: Updated value.

        Returns:
            FieldChange describing the difference, or None if identical.
        """
        if old_value == new_value:
            return None

        # Handle None cases
        if old_value is None and new_value is not None:
            return FieldChange(field=field_name, change_type="added")
        if old_value is not None and new_value is None:
            return FieldChange(field=field_name, change_type="removed")

        # Compare based on type
        if isinstance(old_value, list) and isinstance(new_value, list):
            return DiffSummary._compare_lists(field_name, old_value, new_value)
        elif isinstance(old_value, dict) and isinstance(new_value, dict):
            return DiffSummary._compare_dicts(field_name, old_value, new_value)
        else:
            # Scalar value changed
            return FieldChange(
                field=field_name,
                change_type="modified",
                details=f"{old_value} -> {new_value}",
            )

    @staticmethod
    def _compare_lists(
        field_name: str, old_list: list, new_list: list
    ) -> FieldChange | None:
        """Compare two lists and return the appropriate change type.

        Args:
            field_name: Name of the field being compared.
            old_list: Original list.
            new_list: Updated list.

        Returns:
            FieldChange describing the difference, or None if identical.
        """
        if old_list == new_list:
            return None

        old_set = set(old_list)
        new_set = set(new_list)

        added = new_set - old_set
        removed = old_set - new_set

        # Same items but different order
        if old_set == new_set and old_list != new_list:
            # Format as "a, b -> b, a" for readability (limit to first 3 items)
            old_preview = ", ".join(str(x) for x in old_list[:3])
            new_preview = ", ".join(str(x) for x in new_list[:3])
            if len(old_list) > 3:
                old_preview += "..."
            if len(new_list) > 3:
                new_preview += "..."
            return FieldChange(
                field=field_name,
                change_type="reordered",
                details=f"{old_preview} -> {new_preview}",
            )

        # Items added
        if added and not removed:
            count = len(added)
            items_str = ", ".join(str(x) for x in list(added)[:3])
            if count > 3:
                items_str += f" (+{count - 3} more)"
            return FieldChange(
                field=field_name,
                change_type="items_added",
                details=f"added {items_str}",
            )

        # Items removed
        if removed and not added:
            count = len(removed)
            items_str = ", ".join(str(x) for x in list(removed)[:3])
            if count > 3:
                items_str += f" (+{count - 3} more)"
            return FieldChange(
                field=field_name,
                change_type="items_removed",
                details=f"removed {items_str}",
            )

        # Both added and removed
        details_parts = []
        if added:
            details_parts.append(f"added {len(added)}")
        if removed:
            details_parts.append(f"removed {len(removed)}")
        return FieldChange(
            field=field_name,
            change_type="modified",
            details=", ".join(details_parts),
        )

    @staticmethod
    def _compare_dicts(
        field_name: str, old_dict: dict, new_dict: dict
    ) -> FieldChange | None:
        """Compare two dictionaries and return the appropriate change type.

        Args:
            field_name: Name of the field being compared.
            old_dict: Original dictionary.
            new_dict: Updated dictionary.

        Returns:
            FieldChange describing the difference, or None if identical.
        """
        if old_dict == new_dict:
            return None

        # Find changed keys
        changed_keys = []
        all_keys = set(old_dict.keys()) | set(new_dict.keys())

        for key in all_keys:
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            if old_val != new_val:
                changed_keys.append(key)

        if not changed_keys:
            return None

        # Format details
        if len(changed_keys) == 1:
            key = changed_keys[0]
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            return FieldChange(
                field=f"{field_name}.{key}",
                change_type="modified",
                details=f"{old_val} -> {new_val}",
            )

        # Multiple keys changed
        return FieldChange(
            field=field_name,
            change_type="modified",
            details=f"changed: {', '.join(changed_keys)}",
        )


def format_pydantic_errors(
    pydantic_error: PydanticValidationError,
) -> list[ValidationError]:
    """Convert Pydantic ValidationError to list of ValidationError dataclasses.

    Args:
        pydantic_error: Pydantic ValidationError instance.

    Returns:
        List of ValidationError dataclasses with field paths and messages.
    """
    errors: list[ValidationError] = []

    for error in pydantic_error.errors():
        # Format location tuple as dot-notation path with array indices
        loc = error.get("loc", ())
        field_parts = []
        for part in loc:
            if isinstance(part, int):
                # Array index - append as [n]
                if field_parts:
                    field_parts[-1] = f"{field_parts[-1]}[{part}]"
                else:
                    field_parts.append(f"[{part}]")
            else:
                field_parts.append(str(part))

        field_path = ".".join(field_parts) if field_parts else "root"
        message = error.get("msg", "Validation error")
        error_type = error.get("type")

        errors.append(
            ValidationError(
                field=field_path,
                message=message,
                code=error_type,
            )
        )

    return errors


def validate_policy_data(data: dict[str, Any]) -> ValidationResult:
    """Validate policy data using PolicyModel.

    Args:
        data: Dictionary containing policy configuration.

    Returns:
        ValidationResult with success status and errors or validated policy.
    """
    from pydantic import ValidationError as PydanticValidationError

    from vpo.policy.loader import PolicyModel

    try:
        model = PolicyModel.model_validate(data)
        # Return the validated data as dict
        return ValidationResult(
            success=True,
            errors=[],
            policy=model.model_dump(),
        )
    except PydanticValidationError as e:
        return ValidationResult(
            success=False,
            errors=format_pydantic_errors(e),
            policy=None,
        )
