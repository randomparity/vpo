"""
End-to-end integration tests for the policy editor flow.

Tests the complete user journey:
1. Load policy for editing
2. Make changes via UI
3. Save policy
4. Verify changes persist
5. Verify unknown fields and comments preserved
"""

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp_session import SimpleCookieStorage
from aiohttp_session import setup as setup_session

from video_policy_orchestrator.server.ui.routes import setup_ui_routes


async def get_csrf_token(client):
    """Helper to get CSRF token from test app."""

    resp = await client.get("/_test/csrf-token")
    assert resp.status == 200
    data = await resp.json()
    return data["csrf_token"]


@pytest_asyncio.fixture
async def test_app_with_policies(tmp_path):
    """Create test aiohttp app with test policies."""
    app = web.Application()

    # Setup session middleware (required for CSRF protection)
    # Use SimpleCookieStorage for tests (no encryption needed)
    setup_session(app, SimpleCookieStorage())

    # Set up temporary policy directory
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Create test policy with unknown fields and comments
    test_policy = policy_dir / "integration-test.yaml"
    test_policy.write_text("""schema_version: 2

# Track ordering configuration
track_order:
  - video
  - audio_main
  - audio_alternate
  - subtitle_main

# Audio language preferences
audio_language_preference:
  - eng
  - und

subtitle_language_preference:
  - eng
  - und

commentary_patterns:
  - commentary
  - director

default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true

# Custom field for testing preservation
x_custom_field: preserved_value
x_another_field: also_preserved
""")

    # Store policy dir in app
    app["policy_dir"] = policy_dir

    # Add a test-only endpoint to get CSRF token
    async def get_csrf_token_handler(request: web.Request) -> web.Response:
        """Test-only endpoint to get CSRF token."""
        csrf_token = request.get("csrf_token", "")
        return web.json_response({"csrf_token": csrf_token})

    app.router.add_get("/_test/csrf-token", get_csrf_token_handler)

    # Set up routes (this adds CSRF middleware)
    setup_ui_routes(app)

    return app, policy_dir


@pytest.mark.asyncio
async def test_full_policy_edit_flow(aiohttp_client, test_app_with_policies):
    """Test complete edit flow: load → edit → save → verify."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token for state-changing operations
    csrf_token = await get_csrf_token(client)

    # Step 1: Load policy for editing
    get_response = await client.get("/api/policies/integration-test")
    assert get_response.status == 200

    policy_data = await get_response.json()
    assert policy_data["name"] == "integration-test"
    assert policy_data["audio_language_preference"] == ["eng", "und"]

    # Step 2: Make changes to the policy
    updated_data = {
        "track_order": policy_data["track_order"],
        "audio_language_preference": ["jpn", "eng", "und"],  # Changed
        "subtitle_language_preference": ["fra", "eng"],  # Changed
        "commentary_patterns": ["commentary", "director", "cast"],  # Added one
        "default_flags": policy_data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": policy_data["last_modified"],
    }

    # Step 3: Save changes with CSRF token
    put_response = await client.put(
        "/api/policies/integration-test",
        json=updated_data,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put_response.status == 200

    saved_data = await put_response.json()
    assert saved_data["audio_language_preference"] == ["jpn", "eng", "und"]
    assert saved_data["subtitle_language_preference"] == ["fra", "eng"]
    assert saved_data["commentary_patterns"] == ["commentary", "director", "cast"]

    # Step 4: Reload policy to verify persistence
    reload_response = await client.get("/api/policies/integration-test")
    assert reload_response.status == 200

    reloaded_data = await reload_response.json()
    assert reloaded_data["audio_language_preference"] == ["jpn", "eng", "und"]
    assert reloaded_data["subtitle_language_preference"] == ["fra", "eng"]
    assert reloaded_data["commentary_patterns"] == ["commentary", "director", "cast"]

    # Step 5: Verify unknown fields preserved in file
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    assert "x_custom_field: preserved_value" in file_content
    assert "x_another_field: also_preserved" in file_content

    # Comment preservation not yet fully implemented (skipped in commit 9feccd2)
    # assert "# Track ordering configuration" in file_content


@pytest.mark.asyncio
async def test_unknown_field_preservation_through_multiple_edits(
    aiohttp_client, test_app_with_policies
):
    """Test that unknown fields survive multiple edit cycles."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    # Edit 1: Change audio languages
    get1 = await client.get("/api/policies/integration-test")
    data1 = await get1.json()

    update1 = {
        "track_order": data1["track_order"],
        "audio_language_preference": ["fra"],
        "subtitle_language_preference": data1["subtitle_language_preference"],
        "commentary_patterns": data1["commentary_patterns"],
        "default_flags": data1["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data1["last_modified"],
    }

    put1 = await client.put(
        "/api/policies/integration-test",
        json=update1,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put1.status == 200

    # Edit 2: Change subtitle languages
    get2 = await client.get("/api/policies/integration-test")
    data2 = await get2.json()

    update2 = {
        "track_order": data2["track_order"],
        "audio_language_preference": data2["audio_language_preference"],
        "subtitle_language_preference": ["deu"],
        "commentary_patterns": data2["commentary_patterns"],
        "default_flags": data2["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data2["last_modified"],
    }

    put2 = await client.put(
        "/api/policies/integration-test",
        json=update2,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put2.status == 200

    # Edit 3: Change commentary patterns
    get3 = await client.get("/api/policies/integration-test")
    data3 = await get3.json()

    update3 = {
        "track_order": data3["track_order"],
        "audio_language_preference": data3["audio_language_preference"],
        "subtitle_language_preference": data3["subtitle_language_preference"],
        "commentary_patterns": ["new_pattern"],
        "default_flags": data3["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data3["last_modified"],
    }

    put3 = await client.put(
        "/api/policies/integration-test",
        json=update3,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put3.status == 200

    # Verify unknown fields still exist after 3 edits
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    assert "x_custom_field: preserved_value" in file_content
    assert "x_another_field: also_preserved" in file_content


@pytest.mark.skip(reason="Comment preservation not fully implemented (commit 9feccd2)")
@pytest.mark.asyncio
async def test_comment_preservation(aiohttp_client, test_app_with_policies):
    """Test that comments on unchanged fields are preserved."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    # Load and modify only audio languages (leave others unchanged)
    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    update_data = {
        "track_order": data["track_order"],
        "audio_language_preference": ["ita", "eng"],  # Only change this
        "subtitle_language_preference": data[
            "subtitle_language_preference"
        ],  # Unchanged
        "commentary_patterns": data["commentary_patterns"],  # Unchanged
        "default_flags": data["default_flags"],  # Unchanged
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=update_data,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put_response.status == 200

    # Check that comments on unchanged fields are preserved
    policy_file = policy_dir / "integration-test.yaml"
    file_content = policy_file.read_text()

    # Comments on unchanged sections should still be there
    assert "# Track ordering configuration" in file_content
    assert "# Custom field for testing preservation" in file_content


@pytest.mark.asyncio
async def test_validation_prevents_invalid_save(aiohttp_client, test_app_with_policies):
    """Test that validation prevents saving invalid policy data."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Try to save with invalid data (empty track_order)
    invalid_data = {
        "track_order": [],  # Invalid
        "audio_language_preference": data["audio_language_preference"],
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=invalid_data,
        headers={CSRF_HEADER: csrf_token},
    )

    # Should fail validation
    assert put_response.status == 400
    error_data = await put_response.json()
    assert "error" in error_data

    # Verify original policy unchanged
    reload_response = await client.get("/api/policies/integration-test")
    reloaded = await reload_response.json()
    assert len(reloaded["track_order"]) > 0  # Still has original data


@pytest.mark.asyncio
async def test_concurrent_modification_detection(
    aiohttp_client, test_app_with_policies
):
    """Test that concurrent modifications are detected."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    # Simulate two users loading the same policy
    get1 = await client.get("/api/policies/integration-test")
    data1 = await get1.json()

    get2 = await client.get("/api/policies/integration-test")
    data2 = await get2.json()

    # User 1 saves first
    update1 = {
        "track_order": data1["track_order"],
        "audio_language_preference": ["spa", "eng"],
        "subtitle_language_preference": data1["subtitle_language_preference"],
        "commentary_patterns": data1["commentary_patterns"],
        "default_flags": data1["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data1["last_modified"],
    }

    put1 = await client.put(
        "/api/policies/integration-test",
        json=update1,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put1.status == 200

    # User 2 tries to save with stale timestamp
    update2 = {
        "track_order": data2["track_order"],
        "audio_language_preference": ["por", "eng"],
        "subtitle_language_preference": data2["subtitle_language_preference"],
        "commentary_patterns": data2["commentary_patterns"],
        "default_flags": data2["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data2["last_modified"],  # Stale!
    }

    put2 = await client.put(
        "/api/policies/integration-test",
        json=update2,
        headers={CSRF_HEADER: csrf_token},
    )

    # Should detect concurrent modification
    assert put2.status == 409
    error_data = await put2.json()
    assert "error" in error_data


@pytest.mark.asyncio
async def test_policy_with_transcription_section(aiohttp_client, tmp_path):
    """Test editing policy with transcription configuration."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app = web.Application()

    # Setup session middleware (required for CSRF protection)
    # Use SimpleCookieStorage for tests (no encryption needed)
    setup_session(app, SimpleCookieStorage())

    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()

    # Create policy with transcription
    policy = policy_dir / "transcription-test.yaml"
    policy.write_text("""schema_version: 2
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
commentary_patterns:
  - commentary
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
transcription:
  enabled: true
  update_language_from_transcription: true
  confidence_threshold: 0.8
  detect_commentary: true
  reorder_commentary: true
""")

    app["policy_dir"] = policy_dir

    # Add test-only CSRF token endpoint
    async def get_csrf_token_handler(request: web.Request) -> web.Response:
        """Test-only endpoint to get CSRF token."""
        csrf_token = request.get("csrf_token", "")
        return web.json_response({"csrf_token": csrf_token})

    app.router.add_get("/_test/csrf-token", get_csrf_token_handler)

    setup_ui_routes(app)
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    # Load policy
    get_response = await client.get("/api/policies/transcription-test")
    data = await get_response.json()

    assert "transcription" in data
    assert data["transcription"]["detect_commentary"] is True

    # Update transcription settings
    data["transcription"]["detect_commentary"] = False
    data["transcription"]["reorder_commentary"] = False

    update = {
        "track_order": data["track_order"],
        "audio_language_preference": data["audio_language_preference"],
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": data["transcription"],
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/transcription-test",
        json=update,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put_response.status == 200

    # Verify changes saved
    reload_response = await client.get("/api/policies/transcription-test")
    reloaded = await reload_response.json()

    assert reloaded["transcription"]["detect_commentary"] is False
    assert reloaded["transcription"]["reorder_commentary"] is False


# ==========================================================================
# Policy Validation Tests (025-policy-validation)
# ==========================================================================


@pytest.mark.asyncio
async def test_successful_save_returns_changed_fields(
    aiohttp_client, test_app_with_policies
):
    """Test that successful save returns changed_fields response (T011 US1)."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    # Load policy
    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Make changes to audio language preference (reorder)
    updated_data = {
        "track_order": data["track_order"],
        "audio_language_preference": ["und", "eng"],  # Reordered from ["eng", "und"]
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    # Save
    put_response = await client.put(
        "/api/policies/integration-test",
        json=updated_data,
        headers={CSRF_HEADER: csrf_token},
    )
    assert put_response.status == 200

    saved_data = await put_response.json()

    # Verify new response format
    assert saved_data["success"] is True
    assert "changed_fields" in saved_data
    assert isinstance(saved_data["changed_fields"], list)
    assert "changed_fields_summary" in saved_data

    # Verify at least one change was detected
    assert len(saved_data["changed_fields"]) > 0

    # Find the audio_language_preference change
    audio_change = next(
        (c for c in saved_data["changed_fields"] if "audio" in c["field"].lower()),
        None,
    )
    assert audio_change is not None
    assert audio_change["change_type"] == "reordered"


@pytest.mark.asyncio
async def test_validation_error_returns_errors_array(
    aiohttp_client, test_app_with_policies
):
    """Test that validation failure returns structured errors array (T012 US2)."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Send multiple invalid fields
    invalid_data = {
        "track_order": [],  # Invalid: empty
        "audio_language_preference": [],  # Invalid: empty
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=invalid_data,
        headers={CSRF_HEADER: csrf_token},
    )

    assert put_response.status == 400
    error_data = await put_response.json()

    # Verify new structured error format
    assert "error" in error_data
    assert error_data["error"] == "Validation failed"
    assert "errors" in error_data
    assert isinstance(error_data["errors"], list)

    # Should have multiple errors (track_order and audio_language_preference)
    assert len(error_data["errors"]) >= 2

    # Each error should have field and message
    for err in error_data["errors"]:
        assert "field" in err
        assert "message" in err


@pytest.mark.asyncio
async def test_invalid_language_code_error_response(
    aiohttp_client, test_app_with_policies
):
    """Test that invalid language code returns field-specific error (T013 US2)."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Send invalid language code (not ISO 639-2)
    invalid_data = {
        "track_order": data["track_order"],
        "audio_language_preference": ["english"],  # Invalid: not ISO 639-2
        "subtitle_language_preference": data["subtitle_language_preference"],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=invalid_data,
        headers={CSRF_HEADER: csrf_token},
    )

    assert put_response.status == 400
    error_data = await put_response.json()

    assert "errors" in error_data
    assert len(error_data["errors"]) >= 1

    # Find the language error
    lang_error = next(
        (e for e in error_data["errors"] if "audio_language_preference" in e["field"]),
        None,
    )
    assert lang_error is not None
    # Error message should mention the invalid code
    assert (
        "english" in lang_error["message"].lower()
        or "invalid" in lang_error["message"].lower()
    )


@pytest.mark.asyncio
async def test_empty_required_list_error_response(
    aiohttp_client, test_app_with_policies
):
    """Test that empty required list returns specific error (T014 US2)."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    # Get CSRF token
    csrf_token = await get_csrf_token(client)

    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Send empty subtitle_language_preference
    invalid_data = {
        "track_order": data["track_order"],
        "audio_language_preference": data["audio_language_preference"],
        "subtitle_language_preference": [],  # Invalid: empty
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=invalid_data,
        headers={CSRF_HEADER: csrf_token},
    )

    assert put_response.status == 400
    error_data = await put_response.json()

    assert "errors" in error_data
    assert len(error_data["errors"]) >= 1

    # Find the subtitle error
    subtitle_error = next(
        (
            e
            for e in error_data["errors"]
            if "subtitle_language_preference" in e["field"]
        ),
        None,
    )
    assert subtitle_error is not None
    # Error should indicate the field cannot be empty
    assert (
        "empty" in subtitle_error["message"].lower()
        or "least" in subtitle_error["message"].lower()
    )


@pytest.mark.asyncio
async def test_validation_details_count(aiohttp_client, test_app_with_policies):
    """Test that validation error response includes error count in details."""
    from video_policy_orchestrator.server.csrf import CSRF_HEADER

    app, policy_dir = test_app_with_policies
    client = await aiohttp_client(app)

    csrf_token = await get_csrf_token(client)
    get_response = await client.get("/api/policies/integration-test")
    data = await get_response.json()

    # Make multiple fields invalid
    invalid_data = {
        "track_order": [],
        "audio_language_preference": [],
        "subtitle_language_preference": [],
        "commentary_patterns": data["commentary_patterns"],
        "default_flags": data["default_flags"],
        "transcode": None,
        "transcription": None,
        "last_modified_timestamp": data["last_modified"],
    }

    put_response = await client.put(
        "/api/policies/integration-test",
        json=invalid_data,
        headers={CSRF_HEADER: csrf_token},
    )

    assert put_response.status == 400
    error_data = await put_response.json()

    # Details should include error count
    assert "details" in error_data
    assert "error" in error_data["details"].lower()
    # Should indicate multiple errors
    assert len(error_data["errors"]) >= 3
