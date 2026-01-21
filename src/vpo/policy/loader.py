"""Policy file loading and validation.

This module provides functions to load YAML policy files and validate
them using Pydantic models. The actual Pydantic models are in pydantic_models.py
and conversion functions are in conversion.py.
"""

from pathlib import Path
from typing import Any

import yaml

from vpo.policy.conversion import _convert_to_policy_schema
from vpo.policy.pydantic_models import (
    PolicyModel,
    PolicyValidationError,
)
from vpo.policy.types import PolicySchema

# Current supported schema version (only V12 is supported)
SCHEMA_VERSION = 12

# Backward compatibility alias - DEPRECATED
# This will be removed in a future release. Use SCHEMA_VERSION directly.
MAX_SCHEMA_VERSION = SCHEMA_VERSION

# RESERVED_PHASE_NAMES is imported from pydantic_models


def load_policy(policy_path: Path) -> PolicySchema:
    """Load and validate a policy from a YAML file.

    Args:
        policy_path: Path to the YAML policy file.

    Returns:
        Validated PolicySchema object.

    Raises:
        PolicyValidationError: If the policy file is invalid.
        FileNotFoundError: If the policy file does not exist.
    """
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    try:
        with open(policy_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        # Extract line number from YAML error if available
        line_info = ""
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            mark = e.problem_mark
            line_info = f" at line {mark.line + 1}, column {mark.column + 1}"
        raise PolicyValidationError(
            f"Invalid YAML syntax in {policy_path}{line_info}: {e}"
        ) from e

    if data is None:
        raise PolicyValidationError("Policy file is empty")

    if not isinstance(data, dict):
        raise PolicyValidationError("Policy file must be a YAML mapping")

    return load_policy_from_dict(data)


def load_policy_from_dict(data: dict[str, Any]) -> PolicySchema:
    """Load and validate a policy from a dictionary.

    Args:
        data: Dictionary containing policy configuration.

    Returns:
        Validated PolicySchema object.

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    # Check schema version - only V12 is supported
    schema_version = data.get("schema_version")
    if schema_version != 12:
        raise PolicyValidationError(
            f"Only schema_version 12 is supported, got {schema_version}"
        )

    # Policies must have a 'phases' key
    if "phases" not in data:
        raise PolicyValidationError(
            "Policy must have a 'phases' key defining at least one phase.\n\n"
            "If this policy uses the old flat format, convert it by wrapping "
            "operations in a phase:\n\n"
            "phases:\n"
            "  - name: apply\n"
            "    track_order: [...]  # your existing fields\n"
            "    audio_filter: {...}\n"
            "config:\n"
            "  audio_language_preference: [...]  # move global settings here\n"
            "  subtitle_language_preference: [...]"
        )

    try:
        model = PolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_policy_schema(model)


# Backward compatibility aliases - DEPRECATED
# These will be removed in a future release. Use load_policy_from_dict directly.
load_phased_policy_from_dict = load_policy_from_dict
load_v11_policy_from_dict = load_policy_from_dict


def _format_validation_error(error: Exception) -> str:
    """Format a Pydantic validation error into a user-friendly message."""
    from pydantic import ValidationError

    if isinstance(error, ValidationError):
        # Get the first error
        errors = error.errors()
        if errors:
            first_error = errors[0]
            loc = ".".join(str(x) for x in first_error.get("loc", []))
            msg = first_error.get("msg", str(error))
            if loc:
                return f"Policy validation failed: {loc}: {msg}"
            return f"Policy validation failed: {msg}"

    return f"Policy validation failed: {error}"
