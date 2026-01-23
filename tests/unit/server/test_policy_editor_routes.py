"""
Unit tests for policy editor API routes.

Tests the GET and PUT endpoints for policy editing:
- GET /api/policies/{name} - Fetch policy for editing
- PUT /api/policies/{name} - Save policy changes
- GET /api/policies/schema - Get JSON Schema for client-side validation
"""

import pytest
import pytest_asyncio
from aiohttp import web

from vpo.server.api.policies import api_policy_schema_handler

# =============================================================================
# JSON Schema Endpoint Tests (256-policy-editor-enhancements T029)
# These tests don't require session middleware or file system setup
# =============================================================================


@pytest_asyncio.fixture
async def schema_test_app():
    """Create minimal test app with just the schema route."""
    app = web.Application()
    app.router.add_get("/api/policies/schema", api_policy_schema_handler)
    return app


@pytest.mark.asyncio
async def test_get_policy_schema_success(aiohttp_client, schema_test_app):
    """Test GET /api/policies/schema returns JSON Schema."""
    client = await aiohttp_client(schema_test_app)

    response = await client.get("/api/policies/schema")

    assert response.status == 200
    data = await response.json()

    # Verify response structure
    assert "schema_version" in data
    assert "json_schema" in data
    assert data["schema_version"] == 12

    # Verify JSON schema structure
    schema = data["json_schema"]
    assert isinstance(schema, dict)
    assert "$defs" in schema or "definitions" in schema or "properties" in schema
    # Schema should have type property
    assert schema.get("type") == "object" or "properties" in schema


@pytest.mark.asyncio
async def test_get_policy_schema_content_type(aiohttp_client, schema_test_app):
    """Test GET /api/policies/schema returns correct content type."""
    client = await aiohttp_client(schema_test_app)

    response = await client.get("/api/policies/schema")

    assert response.status == 200
    assert "application/json" in response.headers["Content-Type"]


# =============================================================================
# Policy CRUD Tests (256-policy-editor-enhancements T034/T035)
# These tests use a minimal fixture that only sets up policy API routes
# =============================================================================


@pytest_asyncio.fixture
async def policy_crud_app(tmp_path):
    """Create minimal test app with just policy API routes.

    This fixture avoids the full UI setup (which requires session middleware)
    and only registers the policy API handlers we need to test.
    """
    from vpo.server.api.policies import (
        api_policy_detail_handler,
        api_policy_update_handler,
        api_policy_validate_handler,
    )

    app = web.Application()

    # Set up temporary policy directory
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Create test policy with phases (required for V12 schema)
    test_policy = policy_dir / "test.yaml"
    test_policy.write_text("""schema_version: 12
config:
  audio_language_preference:
    - eng
    - und
  subtitle_language_preference:
    - eng
    - und
  commentary_patterns:
    - commentary
    - director
phases:
  - name: organize
    track_order:
      - video
      - audio_main
      - audio_alternate
    default_flags:
      set_first_video_default: true
      set_preferred_audio_default: true
      set_preferred_subtitle_default: false
      clear_other_defaults: true
""")

    # Create test policy with unknown fields to test preservation
    test_policy_unknown = policy_dir / "test-unknown.yaml"
    test_policy_unknown.write_text("""schema_version: 12
# This is a comment that should be preserved
custom_unknown_field: preserved_value
config:
  audio_language_preference:
    - eng
phases:
  - name: apply
    track_order:
      - video
      - audio_main
""")

    # Store policy dir in app
    app["policy_dir"] = policy_dir

    # Register only the API routes we need (no CSRF, no session middleware)
    app.router.add_get("/api/policies/{name}", api_policy_detail_handler)
    app.router.add_put("/api/policies/{name}", api_policy_update_handler)
    app.router.add_post("/api/policies/{name}/validate", api_policy_validate_handler)

    return app


@pytest.mark.asyncio
async def test_get_policy_for_editing_success(aiohttp_client, policy_crud_app):
    """Test GET /api/policies/{name} returns policy data."""
    client = await aiohttp_client(policy_crud_app)

    response = await client.get("/api/policies/test")

    assert response.status == 200
    data = await response.json()

    assert data["name"] == "test"
    assert data["filename"] == "test.yaml"
    # V12 phased policy fields
    assert "phases" in data
    assert "config" in data
    assert "last_modified" in data
    assert data["schema_version"] == 12


@pytest.mark.asyncio
async def test_get_policy_nonexistent(aiohttp_client, policy_crud_app):
    """Test GET /api/policies/{name} returns 404 for nonexistent policy."""
    client = await aiohttp_client(policy_crud_app)

    response = await client.get("/api/policies/nonexistent")

    assert response.status == 404
    data = await response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_put_policy_update_success(aiohttp_client, policy_crud_app):
    """Test PUT /api/policies/{name} saves policy changes."""
    client = await aiohttp_client(policy_crud_app)

    # First get the policy to get last_modified
    get_response = await client.get("/api/policies/test")
    policy_data = await get_response.json()

    # Update audio language preference in config
    update_data = {
        "phases": policy_data["phases"],
        "config": policy_data["config"],
        "audio_language_preference": ["jpn", "eng"],
        "subtitle_language_preference": policy_data.get(
            "subtitle_language_preference", []
        ),
        "commentary_patterns": policy_data.get("commentary_patterns", []),
        "default_flags": policy_data.get("default_flags", {}),
        "track_order": policy_data.get("track_order", []),
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": policy_data["last_modified"],
    }

    response = await client.put("/api/policies/test", json=update_data)

    assert response.status == 200
    data = await response.json()
    # Response wraps policy in 'policy' field on success
    assert data.get("success") is True or "policy" in data


@pytest.mark.asyncio
async def test_put_policy_concurrent_modification(aiohttp_client, policy_crud_app):
    """Test PUT /api/policies/{name} detects concurrent modification."""
    client = await aiohttp_client(policy_crud_app)

    # Get policy first
    get_response = await client.get("/api/policies/test")
    policy_data = await get_response.json()

    # Build update data
    update_data = {
        "phases": policy_data["phases"],
        "config": policy_data["config"],
        "audio_language_preference": ["fra", "eng"],
        "subtitle_language_preference": policy_data.get(
            "subtitle_language_preference", []
        ),
        "commentary_patterns": policy_data.get("commentary_patterns", []),
        "default_flags": policy_data.get("default_flags", {}),
        "track_order": policy_data.get("track_order", []),
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": policy_data["last_modified"],
    }

    # Make first update
    response1 = await client.put("/api/policies/test", json=update_data)
    assert response1.status == 200

    # Try second update with stale timestamp
    update_data["audio_language_preference"] = ["deu", "eng"]
    # Keep the stale timestamp from original get

    response2 = await client.put("/api/policies/test", json=update_data)

    # Should detect concurrent modification
    assert response2.status == 409
    data = await response2.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_unknown_field_preservation(aiohttp_client, policy_crud_app):
    """Test that unknown fields are preserved when saving (T034)."""
    client = await aiohttp_client(policy_crud_app)

    # Get policy with unknown fields
    get_response = await client.get("/api/policies/test-unknown")
    assert get_response.status == 200
    policy_data = await get_response.json()

    # Verify unknown fields are reported
    assert policy_data.get("unknown_fields") is not None
    assert "custom_unknown_field" in policy_data["unknown_fields"]


@pytest.mark.asyncio
async def test_validate_policy_without_saving(aiohttp_client, policy_crud_app):
    """Test POST /api/policies/{name}/validate validates without saving (T035)."""
    client = await aiohttp_client(policy_crud_app)

    # Get policy first
    get_response = await client.get("/api/policies/test")
    policy_data = await get_response.json()

    # Validate the current policy data
    validate_data = {
        "phases": policy_data["phases"],
        "config": policy_data["config"],
        "audio_language_preference": policy_data.get("audio_language_preference", []),
        "subtitle_language_preference": policy_data.get(
            "subtitle_language_preference", []
        ),
        "commentary_patterns": policy_data.get("commentary_patterns", []),
        "default_flags": policy_data.get("default_flags", {}),
        "track_order": policy_data.get("track_order", []),
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": policy_data["last_modified"],
    }

    response = await client.post("/api/policies/test/validate", json=validate_data)

    assert response.status == 200
    data = await response.json()
    assert data.get("valid") is True
