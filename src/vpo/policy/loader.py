"""Policy file loading and validation.

This module provides functions to load YAML policy files and validate
them using Pydantic models. The actual Pydantic models are in pydantic_models.py
and conversion functions are in conversion.py.
"""

from pathlib import Path
from typing import Any

import yaml

from vpo.policy.conversion import (
    _convert_to_phased_policy_schema,
    _convert_to_policy_schema,
)
from vpo.policy.pydantic_models import (
    PhasedPolicyModel,
    PolicyModel,
    PolicyValidationError,
)
from vpo.policy.types import (
    PhasedPolicySchema,
    PolicySchema,
)

# Current supported schema version (only V12 is supported)
SCHEMA_VERSION = 12

# Backward compatibility alias (deprecated)
MAX_SCHEMA_VERSION = SCHEMA_VERSION

# RESERVED_PHASE_NAMES is imported from pydantic_models


def load_policy(policy_path: Path) -> PolicySchema | PhasedPolicySchema:
    """Load and validate a policy from a YAML file.

    Args:
        policy_path: Path to the YAML policy file.

    Returns:
        Validated PolicySchema (flat format) or PhasedPolicySchema (phased format).

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
        raise PolicyValidationError(f"Invalid YAML syntax: {e}") from e

    if data is None:
        raise PolicyValidationError("Policy file is empty")

    if not isinstance(data, dict):
        raise PolicyValidationError("Policy file must be a YAML mapping")

    return load_policy_from_dict(data)


def load_policy_from_dict(data: dict[str, Any]) -> PolicySchema | PhasedPolicySchema:
    """Load and validate a policy from a dictionary.

    Args:
        data: Dictionary containing policy configuration.

    Returns:
        Validated PolicySchema (flat format) or PhasedPolicySchema (phased format).

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    # Check schema version - only V12 is supported
    schema_version = data.get("schema_version")
    if schema_version != 12:
        raise PolicyValidationError(
            f"Only schema_version 12 is supported, got {schema_version}"
        )

    # Route to phased loader if 'phases' key is present
    has_phases = "phases" in data
    if has_phases:
        return load_phased_policy_from_dict(data)

    try:
        model = PolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_policy_schema(model)


def load_phased_policy_from_dict(data: dict[str, Any]) -> PhasedPolicySchema:
    """Load and validate a phased policy from a dictionary.

    Args:
        data: Dictionary containing phased policy configuration.

    Returns:
        Validated PhasedPolicySchema object.

    Raises:
        PolicyValidationError: If the policy data is invalid.
    """
    try:
        model = PhasedPolicyModel.model_validate(data)
    except Exception as e:
        # Transform Pydantic errors to user-friendly messages
        error_msg = _format_validation_error(e)
        raise PolicyValidationError(error_msg) from e

    return _convert_to_phased_policy_schema(model)


# Backward compatibility alias (deprecated)
load_v11_policy_from_dict = load_phased_policy_from_dict


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
