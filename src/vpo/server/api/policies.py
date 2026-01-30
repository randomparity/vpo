"""API handlers for policy endpoints.

Endpoints:
    GET /api/policies - List policies
    POST /api/policies - Create new policy
    GET /api/policies/{name} - Get policy detail
    PUT /api/policies/{name} - Update policy
    POST /api/policies/{name}/validate - Validate policy
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from aiohttp import web

from vpo.server.ui.routes import shutdown_check_middleware

logger = logging.getLogger(__name__)


@shutdown_check_middleware
async def api_policy_schema_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies/schema - JSON Schema for policy validation.

    Returns:
        JSON response with schema_version and json_schema for client-side validation.
    """
    from vpo.policy.loader import SCHEMA_VERSION
    from vpo.policy.pydantic_models import PolicyModel

    schema = PolicyModel.model_json_schema()
    return web.json_response(
        {
            "schema_version": SCHEMA_VERSION,
            "json_schema": schema,
        }
    )


@shutdown_check_middleware
async def policies_api_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies - JSON API for policy files listing.

    Returns:
        JSON response with PolicyListResponse payload.
    """
    from vpo.policy.services import list_policies

    response = await asyncio.to_thread(list_policies)

    return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_detail_handler(request: web.Request) -> web.Response:
    """Handle GET /api/policies/{name} - JSON API for policy detail.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with policy data or error.
    """
    from vpo.policy.discovery import DEFAULT_POLICIES_DIR
    from vpo.policy.editor import KNOWN_POLICY_FIELDS, PolicyRoundTripEditor
    from vpo.policy.loader import PolicyValidationError
    from vpo.server.ui.models import PolicyEditorContext

    policy_name = request.match_info["name"]

    # Validate policy name
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Construct policy file path
    policy_path = policies_dir / f"{policy_name}.yaml"
    if not policy_path.exists():
        policy_path = policies_dir / f"{policy_name}.yml"

    if not policy_path.exists():
        return web.json_response(
            {"error": "Policy not found"},
            status=404,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Load policy
    def _load_policy():
        try:
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            data = editor.load()
            stat = policy_path.stat()
            last_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
            return data, last_modified, None
        except PolicyValidationError as e:
            return None, None, str(e)
        except Exception as e:
            logger.error(f"Failed to load policy {policy_name}: {e}")
            return None, None, f"Failed to load policy: {e}"

    policy_data, last_modified, parse_error = await asyncio.to_thread(_load_policy)

    if policy_data is None and parse_error:
        return web.json_response(
            {"error": parse_error},
            status=400,
        )

    # Build response with V3-V10 fields (036-v9-policy-editor T010)
    # Get unknown fields for warning banner
    unknown_fields = [k for k in policy_data.keys() if k not in KNOWN_POLICY_FIELDS]

    response = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=policy_data.get("schema_version", 2),
        track_order=policy_data.get("track_order", []),
        audio_language_preference=policy_data.get("audio_language_preference", []),
        subtitle_language_preference=policy_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=policy_data.get("commentary_patterns", []),
        default_flags=policy_data.get("default_flags", {}),
        transcode=policy_data.get("transcode"),
        transcription=policy_data.get("transcription"),
        # Policy metadata fields
        description=policy_data.get("description"),
        category=policy_data.get("category"),
        # V3+ fields (036-v9-policy-editor)
        audio_filter=policy_data.get("audio_filter"),
        subtitle_filter=policy_data.get("subtitle_filter"),
        attachment_filter=policy_data.get("attachment_filter"),
        container=policy_data.get("container"),
        # V4+ fields
        conditional=policy_data.get("conditional"),
        # V5+ fields
        audio_synthesis=policy_data.get("audio_synthesis"),
        # V9+ fields
        workflow=policy_data.get("workflow"),
        # Phased policy fields (user-defined phases)
        phases=policy_data.get("phases"),
        config=policy_data.get("config"),
        # Meta
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=parse_error,
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_update_handler(request: web.Request) -> web.Response:
    """Handle PUT /api/policies/{name} - Save policy changes.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with updated policy data or structured validation errors.
    """
    from vpo.policy.discovery import DEFAULT_POLICIES_DIR
    from vpo.policy.editor import KNOWN_POLICY_FIELDS, PolicyRoundTripEditor
    from vpo.policy.validation import DiffSummary, validate_policy_data
    from vpo.server.ui.models import (
        ChangedFieldItem,
        PolicyEditorContext,
        PolicyEditorRequest,
        PolicySaveSuccessResponse,
        ValidationErrorItem,
        ValidationErrorResponse,
    )

    policy_name = request.match_info["name"]

    # Validate policy name
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Parse request body
    try:
        request_data = await request.json()
        editor_request = PolicyEditorRequest.from_dict(request_data)
    except ValueError as e:
        return web.json_response(
            {"error": f"Invalid request: {e}"},
            status=400,
        )
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Construct policy file path
    policy_path = policies_dir / f"{policy_name}.yaml"
    if not policy_path.exists():
        policy_path = policies_dir / f"{policy_name}.yml"

    if not policy_path.exists():
        return web.json_response(
            {"error": "Policy not found"},
            status=404,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Validate policy data BEFORE attempting save (T015)
    policy_dict = editor_request.to_policy_dict()
    validation_result = validate_policy_data(policy_dict)

    if not validation_result.success:
        # Return structured validation errors (T016)
        error_items = [
            ValidationErrorItem(
                field=err.field,
                message=err.message,
                code=err.code,
            )
            for err in validation_result.errors
        ]
        error_response = ValidationErrorResponse(
            error="Validation failed",
            errors=error_items,
            details=f"{len(error_items)} validation error(s) found",
        )
        return web.json_response(error_response.to_dict(), status=400)

    # Load original policy data for diff calculation
    def _load_original():
        try:
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            return editor.load()
        except Exception:
            return None

    original_data = await asyncio.to_thread(_load_original)

    # Check concurrency and save (optimistic locking)
    def _check_and_save():
        try:
            stat = policy_path.stat()
            file_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            # Compare timestamps
            if file_modified != editor_request.last_modified_timestamp:
                return None, None, "concurrent_modification"

            # Save (validation already passed above)
            editor = PolicyRoundTripEditor(policy_path, allowed_dir=policies_dir)
            editor.save(policy_dict)

            # Reload to get updated data
            data = editor.load()
            new_stat = policy_path.stat()
            new_modified = datetime.fromtimestamp(
                new_stat.st_mtime, tz=timezone.utc
            ).isoformat()

            return data, new_modified, None
        except Exception as e:
            logger.error(f"Failed to save policy {policy_name}: {e}")
            return None, None, f"Failed to save policy: {e}"

    policy_data, last_modified, error = await asyncio.to_thread(_check_and_save)

    if error == "concurrent_modification":
        return web.json_response(
            {
                "error": "Concurrent modification detected",
                "details": (
                    "Policy was modified since you loaded it. "
                    "Please reload and try again."
                ),
            },
            status=409,
        )

    if error:
        return web.json_response(
            {"error": "Save failed", "details": error},
            status=500,
        )

    # Calculate diff summary (T017)
    changed_fields: list[ChangedFieldItem] = []
    changed_fields_summary = "No changes"

    if original_data:
        diff = DiffSummary.compare_policies(original_data, policy_data)
        changed_fields = [
            ChangedFieldItem(
                field=change.field,
                change_type=change.change_type,
                details=change.details,
            )
            for change in diff.changes
        ]
        changed_fields_summary = diff.to_summary_text()

    # Build response with policy editor context (T011)
    # Get unknown fields
    unknown_fields = [k for k in policy_data.keys() if k not in KNOWN_POLICY_FIELDS]

    policy_context = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=policy_data.get("schema_version", 2),
        track_order=policy_data.get("track_order", []),
        audio_language_preference=policy_data.get("audio_language_preference", []),
        subtitle_language_preference=policy_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=policy_data.get("commentary_patterns", []),
        default_flags=policy_data.get("default_flags", {}),
        transcode=policy_data.get("transcode"),
        transcription=policy_data.get("transcription"),
        # Policy metadata fields
        description=policy_data.get("description"),
        category=policy_data.get("category"),
        # V3+ fields (036-v9-policy-editor)
        audio_filter=policy_data.get("audio_filter"),
        subtitle_filter=policy_data.get("subtitle_filter"),
        attachment_filter=policy_data.get("attachment_filter"),
        container=policy_data.get("container"),
        # V4+ fields
        conditional=policy_data.get("conditional"),
        # V5+ fields
        audio_synthesis=policy_data.get("audio_synthesis"),
        # V9+ fields
        workflow=policy_data.get("workflow"),
        # Phased policy fields (user-defined phases)
        phases=policy_data.get("phases"),
        config=policy_data.get("config"),
        # Meta
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=None,
    )

    response = PolicySaveSuccessResponse(
        success=True,
        changed_fields=changed_fields,
        changed_fields_summary=changed_fields_summary,
        policy=policy_context.to_dict(),
    )

    return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_validate_handler(request: web.Request) -> web.Response:
    """Handle POST /api/policies/{name}/validate - Validate without saving.

    Validates the policy data against the schema without persisting changes.
    This allows users to "test" their policy configuration before committing.

    Args:
        request: aiohttp Request object.

    Returns:
        JSON response with validation result (valid/errors).
    """
    from vpo.policy.validation import validate_policy_data
    from vpo.server.ui.models import (
        PolicyEditorRequest,
        PolicyValidateResponse,
        ValidationErrorItem,
    )

    policy_name = request.match_info["name"]

    # Validate policy name format
    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {"error": "Invalid policy name format"},
            status=400,
        )

    # Parse request body
    try:
        request_data = await request.json()
        editor_request = PolicyEditorRequest.from_dict(request_data)
    except ValueError as e:
        return web.json_response(
            {"error": f"Invalid request: {e}"},
            status=400,
        )
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Validate policy data (does NOT save)
    policy_dict = editor_request.to_policy_dict()
    validation_result = validate_policy_data(policy_dict)

    if validation_result.success:
        response = PolicyValidateResponse(
            valid=True,
            errors=[],
            message="Policy configuration is valid",
        )
        return web.json_response(response.to_dict())
    else:
        error_items = [
            ValidationErrorItem(
                field=err.field,
                message=err.message,
                code=err.code,
            )
            for err in validation_result.errors
        ]
        response = PolicyValidateResponse(
            valid=False,
            errors=error_items,
            message=f"{len(error_items)} validation error(s) found",
        )
        return web.json_response(response.to_dict())


@shutdown_check_middleware
async def api_policy_create_handler(request: web.Request) -> web.Response:
    """Handle POST /api/policies - Create a new policy file.

    Creates a new policy file with the given name and default settings.
    Returns 409 Conflict if a policy with that name already exists.

    Request body:
        {
            "name": "policy-name",  // Required: alphanumeric, dash, underscore
            "description": "..."    // Optional: policy description
        }

    Returns:
        JSON response with created policy data or error.
    """
    from ruamel.yaml import YAML

    from vpo.policy.discovery import DEFAULT_POLICIES_DIR
    from vpo.policy.editor import KNOWN_POLICY_FIELDS
    from vpo.policy.loader import SCHEMA_VERSION
    from vpo.server.ui.models import PolicyEditorContext

    # Parse request body
    try:
        request_data = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    # Extract and validate policy name
    policy_name = request_data.get("name", "").strip()
    if not policy_name:
        return web.json_response(
            {"error": "Policy name is required"},
            status=400,
        )

    if not re.match(r"^[a-zA-Z0-9_-]+$", policy_name):
        return web.json_response(
            {
                "error": (
                    "Invalid policy name format. "
                    "Use only letters, numbers, dashes, and underscores."
                )
            },
            status=400,
        )

    # Get policy directory (allow test override)
    policies_dir = request.app.get("policy_dir", DEFAULT_POLICIES_DIR)

    # Ensure policies directory exists
    policies_dir.mkdir(parents=True, exist_ok=True)

    # Check if policy already exists (409 Conflict)
    policy_path = policies_dir / f"{policy_name}.yaml"
    alt_path = policies_dir / f"{policy_name}.yml"

    if policy_path.exists() or alt_path.exists():
        return web.json_response(
            {"error": f"Policy '{policy_name}' already exists"},
            status=409,
        )

    # Verify resolved path is within allowed directory (prevent path traversal)
    try:
        resolved_path = policy_path.resolve()
        resolved_dir = policies_dir.resolve()
        resolved_path.relative_to(resolved_dir)
    except (ValueError, OSError):
        return web.json_response(
            {"error": "Invalid policy path"},
            status=400,
        )

    # Create default policy data with current schema version (phased format)
    policy_data = {
        "schema_version": SCHEMA_VERSION,
        "config": {
            "audio_language_preference": ["eng"],
            "subtitle_language_preference": ["eng"],
        },
        "phases": [
            {
                "name": "organize",
                "track_order": ["video", "audio", "subtitle"],
                "default_flags": {
                    "set_first_video_default": True,
                    "set_preferred_audio_default": True,
                    "set_preferred_subtitle_default": False,
                    "clear_other_defaults": True,
                },
            }
        ],
    }

    # Add optional description and category if provided
    description = request_data.get("description", "").strip()
    if description:
        policy_data["description"] = description

    category = request_data.get("category", "").strip()
    if category:
        policy_data["category"] = category

    # Write new policy file
    def _create_policy():
        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False
            yaml.indent(mapping=2, sequence=4, offset=2)

            with open(policy_path, "w", encoding="utf-8") as f:
                yaml.dump(policy_data, f)

            # Get file timestamp
            stat = policy_path.stat()
            last_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            return policy_data, last_modified, None
        except Exception as e:
            logger.error(f"Failed to create policy {policy_name}: {e}")
            return None, None, str(e)

    created_data, last_modified, error = await asyncio.to_thread(_create_policy)

    if error:
        return web.json_response(
            {"error": "Failed to create policy", "details": error},
            status=500,
        )

    # Build response with policy editor context
    unknown_fields = [k for k in created_data.keys() if k not in KNOWN_POLICY_FIELDS]

    policy_context = PolicyEditorContext(
        name=policy_name,
        filename=policy_path.name,
        file_path=str(policy_path),
        last_modified=last_modified,
        schema_version=created_data.get("schema_version", SCHEMA_VERSION),
        track_order=created_data.get("track_order", []),
        audio_language_preference=created_data.get("audio_language_preference", []),
        subtitle_language_preference=created_data.get(
            "subtitle_language_preference", []
        ),
        commentary_patterns=created_data.get("commentary_patterns", []),
        default_flags=created_data.get("default_flags", {}),
        transcode=created_data.get("transcode"),
        transcription=created_data.get("transcription"),
        # Policy metadata fields
        description=created_data.get("description"),
        category=created_data.get("category"),
        audio_filter=created_data.get("audio_filter"),
        subtitle_filter=created_data.get("subtitle_filter"),
        attachment_filter=created_data.get("attachment_filter"),
        container=created_data.get("container"),
        conditional=created_data.get("conditional"),
        audio_synthesis=created_data.get("audio_synthesis"),
        workflow=created_data.get("workflow"),
        # Phased policy fields
        phases=created_data.get("phases"),
        config=created_data.get("config"),
        unknown_fields=unknown_fields if unknown_fields else None,
        parse_error=None,
    )

    logger.info(
        "Policy created",
        extra={
            "policy_name": policy_name,
            "policy_path": str(policy_path),
        },
    )

    return web.json_response(
        {
            "success": True,
            "message": f"Policy '{policy_name}' created successfully",
            "policy": policy_context.to_dict(),
        },
        status=201,
    )


def setup_policy_routes(app: web.Application) -> None:
    """Register policy API routes with the application.

    Args:
        app: aiohttp Application to configure.
    """
    # Policies API route (023-policies-list-view)
    app.router.add_get("/api/policies", policies_api_handler)
    # Create new policy endpoint (036-v9-policy-editor T068)
    app.router.add_post("/api/policies", api_policy_create_handler)
    # JSON Schema endpoint (256-policy-editor-enhancements T029)
    # Must be before {name} route to avoid matching "schema" as a name
    app.router.add_get("/api/policies/schema", api_policy_schema_handler)
    # Policy detail routes (024-policy-editor)
    app.router.add_get("/api/policies/{name}", api_policy_detail_handler)
    app.router.add_put("/api/policies/{name}", api_policy_update_handler)
    # Policy validation endpoint (025-policy-validation T029)
    app.router.add_post("/api/policies/{name}/validate", api_policy_validate_handler)
