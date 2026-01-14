"""Safe JSON utilities with consistent error handling.

This module provides type-safe JSON parsing functions with optional
Pydantic schema validation. Functions return Result types rather than
raising exceptions, making error handling explicit and consistent.

Example usage:
    # Simple parsing with default on error
    result = parse_json_safe(raw_json, context="plugin_metadata")
    if result.success:
        data = result.value
    else:
        logger.warning("Parse failed: %s", result.error)

    # Parsing with Pydantic schema validation
    result = parse_json_with_schema(raw_json, JobSummarySchema)
    if result.success:
        summary = result.value  # Type: JobSummarySchema
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Sentinel value for unset default parameter
_UNSET: object = object()


@dataclass(frozen=True)
class JsonParseResult(Generic[T]):
    """Result of a JSON parsing operation.

    Attributes:
        success: True if parsing succeeded, False otherwise.
        value: The parsed value if successful, None otherwise.
        error: Error message if parsing failed, None otherwise.
    """

    success: bool
    value: T | None
    error: str | None = None


def parse_json_safe(
    raw: str | None,
    *,
    default: dict | list | None | object = _UNSET,
    context: str = "",
) -> JsonParseResult[dict | list]:
    """Parse JSON string with error handling.

    Args:
        raw: JSON string to parse. None or empty string returns default.
        default: Default value to return if raw is empty or parsing fails.
            Can be None to explicitly return None as the default value.
            If not provided, returns None on empty input but fails on parse errors.
        context: Context string for error messages (e.g., field name).

    Returns:
        JsonParseResult with parsed value or error information.
        If raw is None/empty and default is provided, returns success with default.

    Example:
        result = parse_json_safe(job.summary_json, context="summary_json")
        if result.success:
            summary = result.value
    """
    if raw is None or raw == "":
        if default is not _UNSET:
            return JsonParseResult(success=True, value=default, error=None)
        return JsonParseResult(success=True, value=None, error=None)

    try:
        value = json.loads(raw)
        return JsonParseResult(success=True, value=value, error=None)
    except json.JSONDecodeError as e:
        context_prefix = f"{context}: " if context else ""
        error_msg = f"{context_prefix}Invalid JSON at position {e.pos}: {e.msg}"
        logger.warning(error_msg)
        if default is not _UNSET:
            return JsonParseResult(success=True, value=default, error=error_msg)
        return JsonParseResult(success=False, value=None, error=error_msg)
    except TypeError as e:
        context_prefix = f"{context}: " if context else ""
        error_msg = f"{context_prefix}TypeError during JSON parsing: {e}"
        logger.warning(error_msg)
        if default is not _UNSET:
            return JsonParseResult(success=True, value=default, error=error_msg)
        return JsonParseResult(success=False, value=None, error=error_msg)


def parse_json_with_schema(
    raw: str | None,
    schema: type[BaseModel],
    *,
    context: str = "",
) -> JsonParseResult[BaseModel]:
    """Parse JSON and validate against a Pydantic schema.

    Args:
        raw: JSON string to parse.
        schema: Pydantic model class for validation.
        context: Context string for error messages.

    Returns:
        JsonParseResult with validated model instance or error information.
        If raw is None/empty, returns success with None value.

    Example:
        from vpo.db.json_schemas import JobProgressSchema

        result = parse_json_with_schema(job.progress_json, JobProgressSchema)
        if result.success and result.value:
            progress = result.value  # Type: JobProgressSchema
            print(f"Progress: {progress.percent}%")
    """
    from pydantic import ValidationError

    if raw is None or raw == "":
        return JsonParseResult(success=True, value=None, error=None)

    # First parse the JSON
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        context_prefix = f"{context}: " if context else ""
        error_msg = f"{context_prefix}Invalid JSON at position {e.pos}: {e.msg}"
        logger.warning(error_msg)
        return JsonParseResult(success=False, value=None, error=error_msg)
    except TypeError as e:
        context_prefix = f"{context}: " if context else ""
        error_msg = f"{context_prefix}TypeError during JSON parsing: {e}"
        logger.warning(error_msg)
        return JsonParseResult(success=False, value=None, error=error_msg)

    # Then validate against schema
    try:
        validated = schema.model_validate(data)
        return JsonParseResult(success=True, value=validated, error=None)
    except ValidationError as e:
        context_prefix = f"{context}: " if context else ""
        error_count = len(e.errors())
        first_error = e.errors()[0] if e.errors() else {}
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        msg = first_error.get("msg", "validation error")
        error_msg = (
            f"{context_prefix}Schema validation failed "
            f"({error_count} error(s)): {field}: {msg}"
        )
        logger.warning(error_msg)
        return JsonParseResult(success=False, value=None, error=error_msg)


def serialize_json_safe(
    data: dict | list | None,
    *,
    context: str = "",
) -> str | None:
    """Serialize data to JSON string with error handling.

    Args:
        data: Data to serialize. None returns None.
        context: Context string for error messages.

    Returns:
        JSON string or None if data is None.

    Raises:
        TypeError: If data is not JSON-serializable.
    """
    if data is None:
        return None

    try:
        return json.dumps(data)
    except TypeError as e:
        context_prefix = f"{context}: " if context else ""
        error_msg = f"{context_prefix}Cannot serialize to JSON: {e}"
        logger.error(error_msg)
        raise TypeError(error_msg) from e
